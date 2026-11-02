"""Actual Docker-native isolation test without nested Bubblewrap.

Run in a disposable container using:
  --network none --cap-drop=ALL --security-opt=no-new-privileges --read-only
  --tmpfs /tmp:rw,nosuid,nodev,size=64m
  -e PDFHUB_NATIVE_ISOLATED_CONTAINER=1

No native codec or production documents required. This is a CONTAINER
security prerequisite, not a true HEIC/DWG/CHM/WPS functional acceptance.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from app.services.native_sandbox import SANDBOX_INPUT, SANDBOX_OUTPUT, isolated_native_command

_CHILD = r"""
import json
from pathlib import Path
import socket
import sys
assert Path(sys.argv[1]).read_bytes() == b'isolated-input-test'
Path(sys.argv[2]).write_bytes(b'isolated-output-test')
assert not Path('/data').exists()
assert not Path('/mnt' + '/pdfhub-nas').exists()
assert not Path('/var/run/docker.sock').exists()
network_denied = False
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(2)
    try:
        sock.connect(('1.1.1.1', 443))
    except OSError:
        network_denied = True
assert network_denied, 'native codec unexpectedly has Internet egress'
print(json.dumps({'read_source':True,'write_output':True,
                  'no_user_storage':True,'network_denied':True}))
"""


def main() -> int:
    summary = {"test": "docker-native-standalone-confinement",
               "status": "BLOCKED", "not_a_codec_test": True}
    try:
        if os.environ.get("PDFHUB_NATIVE_ISOLATED_CONTAINER") != "1":
            raise ValueError("Isolated native service environment not active")
        with (TemporaryDirectory(prefix="native-qa-source-") as raw,
              TemporaryDirectory(prefix="native-qa-output-") as outputs):
            input_file = Path(raw) / "input.bin"
            input_file.write_bytes(b"isolated-input-test")
            command = isolated_native_command(
                input_file, Path(outputs),
                [sys.executable, "-c", _CHILD,
                 SANDBOX_INPUT, SANDBOX_OUTPUT + "/output.bin"],
            )
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, check=False, timeout=10, close_fds=True,
                env={"PATH": "/usr/bin:/bin"},
            )
            if result.returncode:
                summary["status"] = "FAIL"
                summary["exit_code"] = result.returncode
                summary["diagnostic"] = result.stderr.strip()[-250:].replace(raw, "<qa>")
            else:
                child = json.loads(result.stdout)
                expected = {"read_source": True, "write_output": True,
                            "no_user_storage": True, "network_denied": True}
                if child != expected or (Path(outputs) / "output.bin").read_bytes() != b"isolated-output-test":
                    raise ValueError("Native Docker output or isolation assertions mismatched")
                summary["status"] = "PASS"
                summary["checks"] = child
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        summary["status"] = "FAIL"
        summary["reason"] = type(exc).__name__
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
