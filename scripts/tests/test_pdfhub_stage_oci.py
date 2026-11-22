"""Small synthetic OCI/SLSA fixtures; does not build images or access Docker."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pdfhub_stage_oci", ROOT / "scripts/pdfhub-stage-oci.py")
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def as_json(value: dict) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def descriptor(blob: bytes) -> dict:
    return {"mediaType": "application/vnd.oci.image.manifest.v1+json",
            "digest": "sha256:" + hashlib.sha256(blob).hexdigest(), "size": len(blob)}


def fixture(path: Path, *, with_attest: bool = True, bad_subject: bool = False,
            wrong_label: bool = False, broken_layer: bool = False,
            predicate_type: str = stage.SLSA_TYPE, nested: bool = False,
            corrupt_index: bool = False, extra_image: bool = False) -> None:
    blobs = {}

    def put(blob: bytes, media_type: str) -> dict:
        d = descriptor(blob)
        d["mediaType"] = media_type
        blobs[d["digest"].removeprefix("sha256:")] = blob
        return d

    config = put(as_json({"config": {"Labels": {
        "org.opencontainers.image.revision": "bad" if wrong_label else stage.SOURCE_SHA,
        "org.opencontainers.image.source": stage.SOURCE_REPO,
    }}}), "application/vnd.oci.image.config.v1+json")
    layer = put(b"valid-image-layer-bytes", "application/vnd.oci.image.layer.v1.tar+gzip")
    manifest = put(as_json({"schemaVersion": 2, "config": config, "layers": [layer]}),
                   "application/vnd.oci.image.manifest.v1+json")
    manifest["platform"] = {"os": "linux", "architecture": "amd64"}
    descriptors = [manifest]
    if with_attest:
        slsa = put(as_json({
            "_type": "https://in-toto.io/Statement/v1",
            "predicateType": predicate_type,
            "subject": [{"name": "_", "digest": {
                "sha256": "0" * 64 if bad_subject else manifest["digest"].removeprefix("sha256:")
            }}],
            "predicate": {"buildDefinition": {"buildType": "https://mobyproject.org/buildkit@v1"}},
        }), "application/vnd.in-toto+json")
        attconfig = put(b"{}", "application/vnd.oci.empty.v1+json")
        attest = put(as_json({"schemaVersion": 2, "config": attconfig, "layers": [slsa],
                              "subject": {"digest": manifest["digest"]}}),
                     "application/vnd.oci.image.manifest.v1+json")
        attest["platform"] = {"os": "unknown", "architecture": "unknown"}
        attest["annotations"] = {
            "vnd.docker.reference.type": "attestation-manifest",
            "vnd.docker.reference.digest": manifest["digest"],
        }
        descriptors.append(attest)
    if extra_image:
        descriptors.append(manifest)
    if nested:
        wrapper = put(as_json({"schemaVersion": 2, "manifests": descriptors}),
                      "application/vnd.oci.image.index.v1+json")
        descriptors = [wrapper]
        if corrupt_index:
            blobs[wrapper["digest"].removeprefix("sha256:")] = b"x" * wrapper["size"]
    with tarfile.open(path, "w") as tf:
        objects = {"index.json": as_json({"schemaVersion": 2, "manifests": descriptors}),
                   "oci-layout": b'{"imageLayoutVersion":"1.0.0"}'}
        objects.update({"blobs/sha256/" + key: value for key, value in blobs.items()})
        if broken_layer:
            objects["blobs/sha256/" + layer["digest"].removeprefix("sha256:")] = b"bad!"
        for name, value in objects.items():
            member = tarfile.TarInfo(name)
            member.size = len(value)
            tf.addfile(member, io.BytesIO(value))


class StagingOciTests(unittest.TestCase):
    def test_complete_oci_image_and_buildkit_in_toto_provenance_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.oci.tar"
            fixture(path)
            record = stage.inspect_archive(path)
            self.assertEqual(record["image_source_sha"], stage.SOURCE_SHA)
            self.assertTrue(record["buildkit_slsa_v1_blob_digest"].startswith("sha256:"))
            self.assertFalse(record["registry_published"])
            self.assertFalse(record["production_deployed"])

    def test_buildkit_nested_index_binds_image_and_attestation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.oci.tar"
            fixture(path, nested=True)
            record = stage.inspect_archive(path)
            self.assertEqual(record["image_source_sha"], stage.SOURCE_SHA)
            self.assertEqual(record["image_platform"], "linux/amd64")

    def test_nested_index_digest_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.oci.tar"
            fixture(path, nested=True, corrupt_index=True)
            with self.assertRaisesRegex(stage.EvidenceError, "SHA-256 mismatch"):
                stage.inspect_archive(path)

    def test_nested_index_extra_image_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.oci.tar"
            fixture(path, nested=True, extra_image=True)
            with self.assertRaisesRegex(stage.EvidenceError, "exactly one"):
                stage.inspect_archive(path)

    def test_nested_index_wrong_subject_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.oci.tar"
            fixture(path, nested=True, bad_subject=True)
            with self.assertRaisesRegex(stage.EvidenceError, "does not bind"):
                stage.inspect_archive(path)

    def test_absent_attestation_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "web.oci.tar"
            fixture(path, with_attest=False)
            with self.assertRaisesRegex(stage.EvidenceError, "attestation"):
                stage.inspect_archive(path)

    def test_builder_requests_the_verifier_required_slsa_v1(self):
        script = (ROOT / "scripts/pdfhub-stage-signed-candidate.sh").read_text()
        self.assertIn("--provenance=mode=max,version=v1", script)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.oci.tar"
            fixture(path, predicate_type="https://slsa.dev/provenance/v0.2")
            with self.assertRaisesRegex(stage.EvidenceError, "SLSA v1"):
                stage.inspect_archive(path)

    def test_wrong_slsa_subject_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "gotenberg.oci.tar"
            fixture(path, bad_subject=True)
            with self.assertRaisesRegex(stage.EvidenceError, "does not bind"):
                stage.inspect_archive(path)

    def test_wrong_source_revision_label_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.oci.tar"
            fixture(path, wrong_label=True)
            with self.assertRaisesRegex(stage.EvidenceError, "revision label"):
                stage.inspect_archive(path)

    def test_corrupt_layer_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.oci.tar"
            fixture(path, broken_layer=True)
            with self.assertRaisesRegex(stage.EvidenceError, "size|SHA-256 mismatch"):
                stage.inspect_archive(path)

    def test_wrong_source_sha_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api.oci.tar"
            fixture(path)
            with self.assertRaisesRegex(stage.EvidenceError, "Unapproved source"):
                stage.inspect_archive(path, "f" * 40)

    def test_operator_detached_signature_and_tamper(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            priv = root / "signing.pem"
            pub = root / "signing.pub"
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA",
                            "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(priv)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(["openssl", "pkey", "-in", str(priv), "-pubout", "-out", str(pub)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            for name in stage.COMPONENTS:
                path = root / f"{name}.oci.tar"
                fixture(path)
                (root / f"{name}.metadata.json").write_text(
                    json.dumps(stage.inspect_archive(path)), encoding="utf-8"
                )
            receipt = stage.create_receipt(root, stage.SOURCE_SHA, pub)
            subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(priv),
                            "-out", str(root / "candidate.sig"), str(receipt)], check=True)
            with patch("builtins.print"):
                stage.verify_candidate(root, pub)
            self.assertEqual(root.joinpath("candidate.json").stat().st_mode & 0o777, 0o600)
            receipt.write_bytes(receipt.read_bytes() + b"tamper\n")
            with self.assertRaisesRegex(stage.EvidenceError, "signature"):
                stage.verify_candidate(root, pub)


if __name__ == "__main__":
    unittest.main()
