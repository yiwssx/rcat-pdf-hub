#!/usr/bin/env python3
"""Signed-release input receipt: public Git source only, never a built OCI image.

The institutional Gotenberg fonts and Host config are deliberately excluded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")

COMPONENT_FILES = {
    "api": ("apps/api", "apps/api/Dockerfile", "apps/api/requirements.lock"),
    "web": ("apps/web", "apps/web/Dockerfile", "apps/web/package-lock.json"),
    "gotenberg": ("ops/gotenberg", "ops/gotenberg/Dockerfile", "ops/gotenberg/13fonts-manifest.json"),
}
COMMON_FILES = ("docker-compose.yml", "docker-compose.prod.yml")


class ReceiptError(ValueError):
    pass


def git(*args: str) -> bytes:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), *args], timeout=30)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReceiptError("Required local Git evidence unavailable") from exc


def sha256_file(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def collect(source_sha: str) -> dict:
    if not SHA.fullmatch(source_sha) or git("rev-parse", "HEAD").decode().strip() != source_sha:
        raise ReceiptError("Receipt must bind exact checked-out Git commit")

    tracked = set(git("ls-files", "-z").decode().strip("\0").split("\0"))
    required = set(COMMON_FILES)
    for context, dockerfile, lock in COMPONENT_FILES.values():
        required.update((dockerfile, lock))
    if not required.issubset(tracked):
        raise ReceiptError("Missing tracked build input")

    # Never include the locally licensed 57-font bundle in a public release.
    unexpected_fonts = sorted(
        name for name in tracked
        if name.startswith("ops/gotenberg/fonts/")
        and name != "ops/gotenberg/fonts/.gitkeep"
    )
    if unexpected_fonts:
        raise ReceiptError("Private Gotenberg font payload tracked in Git")

    # Refuse accidentally committed secret/credential payloads in source archive.
    for name in tracked:
        lower = name.lower()
        if (lower == ".env" or lower.startswith(".env.")
                and lower != ".env.example"
                or lower.endswith((".pem", ".p12", ".pfx", ".key"))
                or "/secrets/" in f"/{lower}/"):
            raise ReceiptError("Sensitive-like path tracked in source archive")

    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for component, (context, _, _) in COMPONENT_FILES.items():
        marker = f"  {component}:\n    build: ./{context}\n"
        if marker not in compose:
            raise ReceiptError(f"Unexpected Compose build context for {component}")

    gotenberg = (ROOT / COMPONENT_FILES["gotenberg"][1]).read_text(encoding="utf-8")
    if ("FROM gotenberg/gotenberg:8.34.0" not in gotenberg
            or "COPY fonts/" not in gotenberg):
        raise ReceiptError("Gotenberg font-sensitive Dockerfile changed")

    font_data = json.loads((ROOT / COMPONENT_FILES["gotenberg"][2]).read_text(encoding="utf-8"))
    if font_data.get("font_count") != 57 or not DIGEST.fullmatch(font_data.get("fingerprint_sha256", "")):
        raise ReceiptError("Invalid institutional font inventory fingerprint")

    components = []
    for component, (context, dockerfile, lock) in sorted(COMPONENT_FILES.items()):
        components.append({
            "name": component,
            "build_context": context,
            "dockerfile_sha256": sha256_file(dockerfile),
            "dependency_or_font_manifest": lock,
            "dependency_or_font_manifest_sha256": sha256_file(lock),
            "published_oci_digest": None,
            "built_image_attested": False,
        })
    return {
        "schema_version": 1,
        "kind": "rcat.pdf-hub.git-source-build-input-receipt",
        "source_repository": "yiwssx/rcat-pdf-hub",
        "source_commit": source_sha,
        "trust_boundary": "Tracked Git sources/build recipes only; NOT built image digests, runtime Host image identity or production deployment",
        "components": components,
        "compose_input_sha256": {name: sha256_file(name) for name in COMMON_FILES},
        "institutional_font_bundle": {
            "count": 57,
            "fingerprint_sha256": font_data["fingerprint_sha256"],
            "font_payloads_in_git": False,
            "host_image_font_bytes_verified": False,
        },
        "release_gate": "SOURCE_ONLY_PASS_DOES_NOT_MEAN_DEPLOYABLE_IMAGE_PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("Select exactly one of --check or --write")
    actual_sha = git("rev-parse", "HEAD").decode().strip()
    if args.write and os.environ.get("GITHUB_SHA") != actual_sha:
        raise ReceiptError("Exact GITHUB_SHA is required for a signed release")
    receipt = collect(actual_sha)
    if args.check:
        print("PDFHUB_HDA06_SOURCE_INPUTS=PASS")
        print("DEPLOYABLE_OCI_IMAGE_ATTESTATION=NOT_CLAIMED")
        return
    directory = ROOT / "release"
    directory.mkdir(exist_ok=True)
    filename = f"pdfhub-source-inputs-{actual_sha}.json"
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (directory / filename).write_bytes(payload)
    (directory / (filename + ".sha256")).write_text(
        hashlib.sha256(payload).hexdigest() + "  " + filename + "\n", encoding="ascii"
    )
    print("PDFHUB_HDA06_SOURCE_INPUTS=SIGNED_CANDIDATE_READY")
    print("component_count=3")
    print("private_font_binaries_included=false")
    print("deployable_images_attested=false")


if __name__ == "__main__":
    try:
        main()
    except (ReceiptError, OSError, ValueError, UnicodeError) as exc:
        raise SystemExit("PDFHUB_HDA06_BLOCKED: " + str(exc)) from exc
