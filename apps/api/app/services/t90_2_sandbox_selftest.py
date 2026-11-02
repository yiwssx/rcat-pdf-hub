"""Read-only, real-runtime T90-2 Bubblewrap security smoke for QA host.

Run IN the isolated QA clone's existing worker container:
    docker compose exec -T worker-heavy python -m app.services.t90_2_sandbox_selftest

No feature flags, privileged container settings, network calls outside
Bubblewrap, firewall edits, file uploads, or external native files required.
This is NOT a genuine-source conversion nor a production acceptance result.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from app.services.native_sandbox import SANDBOX_INPUT, isolated_native_command


# Executes only INSIDE Bubblewrap. A failure to create namespace is itself
# a failed mandatory acceptance precondition, with no unsandboxed fallback.
_CHILD = r"""
import json
from pathlib import Path
import socket
import sys

src = Path(sys.argv[1])
assert src.read_bytes() == b'T90-2 native sandbox input\n'
assert not Path('/data').exists(), 'private document store is exposed'
assert not Path('/mnt' + '/pdfhub-nas').exists(), 'NAS is exposed'
assert not Path('/app/.env').exists(), 'application dotenv is exposed'
assert not Path('/opt/other').exists(), 'unapproved /opt package is exposed'
for candidate in ('/etc/passwd', '/run/secrets'):
    assert not Path(candidate).exists(), 'host metadata or secrets exposed'
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(2.0)
try:
    sock.connect(('1.1.1.1', 443))
    raise AssertionError('sandbox decoder unexpectedly reached public TCP')
except OSError:
    pass
finally:
    sock.close()
print(json.dumps({'source_read': True, 'network_denied': True,
                  'host_data_unmounted': True, 'restricted_runtime_mounts': True}))
"""


def main() -> int:
    result: dict[str, object] = {
        "check": "T90-2 native Bubblewrap sandbox QA smoke",
        "environment": "existing worker container, read-only temporary input",
        "conclusion": "BLOCKED",
        "important": "Passing does not certify each external native decoder or real PDF fidelity",
    }
    try:
        with TemporaryDirectory(prefix="pdfhub-sandbox-qa-") as folder:
            source = Path(folder) / "source.bin"
            source.write_bytes(b"T90-2 native sandbox input\n")
            command = isolated_native_command(
                source, None,
                [sys.executable, "-c", _CHILD, SANDBOX_INPUT],
            )
            completed = subprocess.run(
                command, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=15,
                check=False, close_fds=True,
                env={"PATH": "/usr/bin:/bin"},
            )
            if completed.returncode:
                result["reason"] = "Bubblewrap or its required security checks failed"
                # Do not dump the entire child error (potentially includes paths).
                result["exit_code"] = completed.returncode
                # bwrap prints fixed, non-user-controlled mount/syscall errors.
                # Strip the generated source path; never emit env/secret values.
                diagnostic = completed.stderr.strip()[-400:]
                result["diagnostic"] = diagnostic.replace(str(source), "<qa-input>").replace(folder, "<qa-dir>")
                result["conclusion"] = "FAIL"
            elif len(completed.stdout.encode("utf-8")) > 2048:
                result["conclusion"] = "FAIL"
                result["reason"] = "Unexpected unbounded native QA output"
            else:
                child = json.loads(completed.stdout)
                expected = {
                    "source_read": True, "network_denied": True,
                    "host_data_unmounted": True,
                    "restricted_runtime_mounts": True,
                }
                if child != expected:
                    result["conclusion"] = "FAIL"
                    result["reason"] = "Native sandbox boundary assertions mismatched"
                else:
                    result["conclusion"] = "PASS"
                    result["native_sandbox_observed"] = child
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["conclusion"] = "BLOCKED"
        result["reason"] = type(exc).__name__
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["conclusion"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
