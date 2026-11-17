#!/usr/bin/env python3
"""Private staging OCI archive provenance + operator signature verification.

No Docker calls, network, font exports, registry pushes, or Host mutations.
The images may contain institution-licensed fonts: NEVER upload OCI tar files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

SOURCE_SHA = "645de50a9205f5b54455ea78d8fef26e97640e9c"
SOURCE_REPO = "https://github.com/yiwssx/rcat-pdf-hub"
SOURCE_SIGNING_RUN = 43819808546
FONT_FINGERPRINT = "f6e97d9ff6bba7446cb2d50530b034afedbd23e78c2d47c9cfcef50db8c2e015"
COMPONENTS = ("api", "web", "gotenberg")
DIGEST_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
SLSA_TYPE = "https://slsa.dev/provenance/v1"
ATTEST_TYPE = "attestation-manifest"
MAX_JSON_BLOB = 32 * 1024 * 1024


class EvidenceError(ValueError):
    pass


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def object_blob(tf: tarfile.TarFile, descriptor: dict, *, collect: bool = True) -> bytes | None:
    digest = descriptor.get("digest", "")
    match = DIGEST_RE.fullmatch(digest)
    require(match is not None, "Non-SHA-256 OCI descriptor")
    try:
        member = tf.getmember("blobs/sha256/" + match.group(1))
    except KeyError as exc:
        raise EvidenceError("Missing referenced OCI blob") from exc
    require(member.isfile(), "OCI blob is not a regular file")
    require(member.size == descriptor.get("size"), "OCI descriptor size differs from stored blob")
    fileobj = tf.extractfile(member)
    require(fileobj is not None, "Unreadable OCI blob")
    hasher = hashlib.sha256()
    chunks: list[bytes] = []
    with fileobj:
        for chunk in iter(lambda: fileobj.read(1024 * 1024), b""):
            hasher.update(chunk)
            if collect:
                chunks.append(chunk)
                require(sum(map(len, chunks)) <= MAX_JSON_BLOB, "OCI JSON evidence exceeds safety cap")
    require(hasher.hexdigest() == match.group(1), "OCI blob SHA-256 mismatch")
    return b"".join(chunks) if collect else None


def object_json(tf: tarfile.TarFile, descriptor: dict) -> dict:
    payload = object_blob(tf, descriptor)
    try:
        value = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise EvidenceError("Invalid OCI JSON object") from exc
    require(isinstance(value, dict), "OCI blob must be a JSON object")
    return value


def inspect_archive(archive: Path, source_sha: str = SOURCE_SHA) -> dict:
    require(archive.is_file() and not archive.is_symlink(), "OCI archive must be a regular local file")
    require(source_sha == SOURCE_SHA, "Unapproved source SHA")
    with tarfile.open(archive, mode="r:") as tf:
        try:
            index_file = tf.extractfile("index.json")
        except KeyError as exc:
            raise EvidenceError("OCI archive missing index.json") from exc
        require(index_file is not None, "Unreadable OCI index")
        index_raw = index_file.read(MAX_JSON_BLOB + 1)
        require(len(index_raw) <= MAX_JSON_BLOB, "OCI index too large")
        index = json.loads(index_raw)
        require(index.get("schemaVersion") == 2, "Unexpected OCI index version")
        descriptors = index.get("manifests", [])
        require(isinstance(descriptors, list), "Unexpected OCI index manifests")
        normal = [
            d for d in descriptors
            if d.get("platform", {}).get("os") == "linux"
            and d.get("platform", {}).get("architecture") == "amd64"
            and d.get("annotations", {}).get("vnd.docker.reference.type") != ATTEST_TYPE
        ]
        require(len(normal) == 1, "Require exactly one linux/amd64 runnable image")
        image_descriptor = normal[0]
        image_manifest = object_json(tf, image_descriptor)
        require(image_manifest.get("schemaVersion") == 2, "Unexpected image manifest version")
        image_config = object_json(tf, image_manifest["config"])
        labels = image_config.get("config", {}).get("Labels", {})
        require(labels.get("org.opencontainers.image.revision") == source_sha, "Image source revision label mismatch")
        require(labels.get("org.opencontainers.image.source") == SOURCE_REPO, "Image source repository label mismatch")
        layers = image_manifest.get("layers", [])
        require(isinstance(layers, list) and len(layers) > 0, "Missing image layers")
        for layer in layers:
            object_blob(tf, layer, collect=False)

        attesters = [
            d for d in descriptors
            if d.get("annotations", {}).get("vnd.docker.reference.type") == ATTEST_TYPE
            and d.get("annotations", {}).get("vnd.docker.reference.digest") == image_descriptor["digest"]
        ]
        require(len(attesters) == 1, "Missing or ambiguous image-linked BuildKit attestation manifest")
        attester = object_json(tf, attesters[0])
        if attester.get("subject"):
            require(
                attester["subject"].get("digest") == image_descriptor["digest"],
                "Attestation OCI artifact subject mismatch",
            )
        in_toto = [
            layer for layer in attester.get("layers", [])
            if layer.get("mediaType") == "application/vnd.in-toto+json"
        ]
        require(len(in_toto) >= 1, "No embedded in-toto provenance blob")
        slsa: list[str] = []
        for attestation_blob in in_toto:
            statement = object_json(tf, attestation_blob)
            if statement.get("predicateType") != SLSA_TYPE:
                continue
            subject_matches = any(
                item.get("digest", {}).get("sha256") == image_descriptor["digest"].removeprefix("sha256:")
                for item in statement.get("subject", [])
            )
            require(subject_matches, "SLSA statement does not bind image manifest digest")
            require(isinstance(statement.get("predicate"), dict), "SLSA predicate missing")
            slsa.append(attestation_blob["digest"])
        require(len(slsa) == 1, "Expected exactly one image-bound SLSA v1 provenance statement")
    return {
        "archive_sha256": sha256_path(archive),
        "oci_index_sha256": hashlib.sha256(index_raw).hexdigest(),
        "image_manifest_digest": image_descriptor["digest"],
        "buildkit_slsa_v1_blob_digest": slsa[0],
        "image_platform": "linux/amd64",
        "image_source_sha": source_sha,
        "local_oci_archive": True,
        "registry_published": False,
        "production_deployed": False,
    }


def create_receipt(directory: Path, source_sha: str, public_key: Path) -> Path:
    require(source_sha == SOURCE_SHA, "Signed GitHub source commit differs from candidate commit")
    require(public_key.is_file() and not public_key.is_symlink(), "Trusted public-key file is required")
    components: dict[str, dict] = {}
    for name in COMPONENTS:
        archive = directory / f"{name}.oci.tar"
        expected = json.loads((directory / f"{name}.metadata.json").read_text("utf-8"))
        observed = inspect_archive(archive, source_sha)
        require(observed == expected, f"{name} OCI verification differs from build record")
        components[name] = observed

    receipt = {
        "schema_version": 1,
        "kind": "rcat.pdfhub.private-staging-signed-buildkit-oci-candidate",
        "source_repository": SOURCE_REPO,
        "reviewed_source_sha": SOURCE_SHA,
        "signed_source_inputs_run_id": SOURCE_SIGNING_RUN,
        "institutional_font_bundle": {
            "file_count": 57,
            "verified_stage_source_fingerprint_sha256": FONT_FINGERPRINT,
            "font_binaries_public": False,
            "gotenberg_oci_contains_private_fonts": True,
        },
        "components": components,
        "operator_public_key_sha256": sha256_path(public_key),
        "trust_scope": (
            "Private staging images freshly built by the operator-controlled BuildKit builder; "
            "NOT original Production image provenance or a public registry/Sigstore signature"
        ),
        "buildkit_attestation_status": "OCI_EMBEDDED_SLSA_V1_PRESENT_AND_VERIFIED",
        "staging_only": True,
        "production_unchanged": True,
    }
    dest = directory / "candidate.json"
    require(not dest.exists(), "Candidate receipt exists; refusing to overwrite")
    dest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", "utf-8")
    dest.chmod(0o600)
    return dest


def verify_candidate(directory: Path, pubkey: Path) -> None:
    receipt_path = directory / "candidate.json"
    signature = directory / "candidate.sig"
    require(receipt_path.is_file() and signature.is_file(), "Missing candidate receipt or detached signature")
    require(pubkey.is_file(), "Operator trusted public key is required")
    verify = subprocess.run(
        ["openssl", "dgst", "-sha256", "-verify", str(pubkey), "-signature", str(signature), str(receipt_path)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    require(verify.returncode == 0 and "Verified OK" in verify.stdout, "Operator signature verification FAIL")
    receipt = json.loads(receipt_path.read_text("utf-8"))
    require(receipt.get("kind") == "rcat.pdfhub.private-staging-signed-buildkit-oci-candidate", "Unrecognized candidate contract")
    require(receipt.get("reviewed_source_sha") == SOURCE_SHA, "Wrong source SHA")
    require(receipt.get("signed_source_inputs_run_id") == SOURCE_SIGNING_RUN, "Wrong accepted GitHub signing run")
    require(receipt.get("operator_public_key_sha256") == sha256_path(pubkey), "Untrusted signer key fingerprint")
    fonts = receipt.get("institutional_font_bundle", {})
    require(fonts.get("file_count") == 57 and
            fonts.get("verified_stage_source_fingerprint_sha256") == FONT_FINGERPRINT and
            fonts.get("gotenberg_oci_contains_private_fonts") is True, "Wrong staged font inputs")
    components = receipt.get("components", {})
    require(set(components) == set(COMPONENTS), "Candidate is not a 3-component release")
    for component in COMPONENTS:
        observed = inspect_archive(directory / f"{component}.oci.tar")
        require(components[component] == observed, f"{component} signed OCI archive mismatch")
        print(f"PDFHUB_STAGE_OCI_PROVENANCE_PASS={component} {observed['image_manifest_digest']}")
    print(f"PDFHUB_STAGE_OPERATOR_SIGNATURE=PASS signer_pubkey_sha256={sha256_path(pubkey)}")
    print("PDFHUB_SIGNED_STAGING_CANDIDATE=PASS_3_OF_3")
    print("PDFHUB_EXISTING_PRODUCTION_IMAGE_PROVENANCE=NOT_CLAIMED")
    print("PDFHUB_PRODUCTION_MUTATION=NONE")


def main(argv: list[str]) -> None:
    if len(argv) == 3 and argv[0] == "inspect":
        print(json.dumps(inspect_archive(Path(argv[1]), argv[2]), sort_keys=True))
    elif len(argv) == 4 and argv[0] == "receipt":
        print(create_receipt(Path(argv[1]), argv[2], Path(argv[3])))
    elif len(argv) == 3 and argv[0] == "verify":
        verify_candidate(Path(argv[1]), Path(argv[2]))
    else:
        raise EvidenceError("Usage: inspect ARCHIVE SOURCE_SHA | receipt DIRECTORY SOURCE_SHA TRUSTED_PUBLIC_KEY | verify DIRECTORY TRUSTED_PUBLIC_KEY")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (EvidenceError, OSError, ValueError, KeyError, IndexError, tarfile.TarError,
            subprocess.SubprocessError) as exc:
        print("PDFHUB_SIGNED_STAGE_BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
