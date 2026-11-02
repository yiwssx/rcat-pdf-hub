"""Strict, non-networked bubblewrap command constructor for native readers.

This is *mandatory* for T20/T30/T34/T09/T25 native development adapters:
never fallback to unsandboxed execution. It does not itself prove Docker
supports unprivileged namespaces or native decoder safety; that requires an
explicit acceptance exercise before feature staging.

Mounts: runtime/code RO; one source file RO; one dedicated task directory RW;
private /tmp, /proc and /dev; no network, host /data, database, docker.sock,
home, host /run, service tokens, or user-controlled arbitrary filesystem paths.
"""
from __future__ import annotations

from pathlib import Path
import os
from typing import Sequence

BWRAP = Path("/usr/bin/bwrap")
SANDBOX_INPUT = "/input/source"
SANDBOX_OUTPUT = "/output"


def isolated_native_command(
    source: Path,
    output_dir: Path | None,
    argv: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> list[str]:
    """Build argv for a fixed native program; caller supplies no shell string.

    argv is already expressed using /input/source and /output/* paths.
    When there is no output directory (CHM reader), the helper may only
    report through bounded stdout. The caller still imposes rlimits/timeouts.
    """
    dedicated_container = os.environ.get("PDFHUB_NATIVE_ISOLATED_CONTAINER") == "1"
    if not dedicated_container and (not BWRAP.is_file() or BWRAP.is_symlink()):
        raise ValueError("Mandatory native isolation utility unavailable")
    if not source.is_file() or source.is_symlink():
        raise ValueError("Native input must be one existing regular file")
    src = source.resolve(strict=True)
    if output_dir is not None:
        if not output_dir.is_dir() or output_dir.is_symlink():
            raise ValueError("Native output must be a fresh task-owned directory")
        destination = output_dir.resolve(strict=True)
        if destination == src.parent or src.is_relative_to(destination):
            raise ValueError("Native input/output sandbox paths overlap")
    else:
        destination = None
    command = list(argv)
    if (not command or not command[0].startswith("/")
            or any(not isinstance(value, str) or not value or "\0" in value
                   for value in command)
            or SANDBOX_INPUT not in command):
        raise ValueError("Native decoder command must use a fixed absolute program and sandbox input")
    if any("/data/" in value or "/mnt/" in value for value in command):
        raise ValueError("Host data mount paths cannot enter decoder argv")
    if destination is None and any(SANDBOX_OUTPUT in value for value in command):
        raise ValueError("Native command cannot use a missing output mount")

    # The only supported alternative to nested Bubblewrap is an ENTIRELY
    # SEPARATE, read-only Docker native-decoder sidecar with no host files,
    # database, Redis, NAS or credentials. Never permit direct native
    # decoding in the ordinary API/RQ worker.
    if dedicated_container:
        if os.geteuid() == 0 or not Path("/.dockerenv").exists():
            raise ValueError("Dedicated native decoder must run non-root in Docker")
        try:
            status = Path("/proc/self/status").read_text(encoding="ascii")
            if ("NoNewPrivs:\t1" not in status
                    or not any(line.startswith("CapEff:\t0000000000000000")
                               for line in status.splitlines())
                    or not (os.statvfs("/").f_flag & os.ST_RDONLY)):
                raise ValueError("Native sidecar lacks required Docker hardening")
        except OSError as exc:
            raise ValueError("Native Docker security state unavailable") from exc
        for prohibited in (Path("/data"), Path("/mnt/pdfhub-nas"),
                           Path("/var/run/docker.sock")):
            if prohibited.exists():
                raise ValueError("Native sidecar has forbidden host mount")
        # Only fixed request-validated path replacements; no shell or user
        # controlled program name/flags. Convert exactly one source and one
        # ephemeral native output directory per signed sidecar request.
        def rewrite(argument: str) -> str:
            if argument == SANDBOX_INPUT:
                return str(src)
            if argument == SANDBOX_OUTPUT or argument.startswith(SANDBOX_OUTPUT + "/"):
                if destination is None:
                    raise ValueError("Missing isolated native output directory")
                return str(destination) + argument[len(SANDBOX_OUTPUT):]
            return argument
        allowed_environment = {"LD_LIBRARY_PATH", "LIBHEIF_PLUGIN_PATHS"}
        override = []
        for key, value in (env or {}).items():
            if (key not in allowed_environment or not isinstance(value, str)
                    or not value.startswith("/") or "\0" in value):
                raise ValueError("Native runtime environment override forbidden")
            override.append(key + "=" + value)
        return ["/usr/bin/env", *override, *(rewrite(arg) for arg in command)]

    # Unshare network is mandatory. Do not use --unshare-user-try, since that
    # might silently skip the required namespace. If the Docker seccomp or
    # host kernel disallows a namespace, bwrap exits nonzero and job fails.
    sandbox = [
        str(BWRAP), "--die-with-parent", "--new-session",
        "--unshare-user", "--unshare-net", "--unshare-ipc",
        "--unshare-pid", "--unshare-uts", "--clearenv",
        "--ro-bind", "/usr", "/usr",
        # Never expose the entire application root or /opt to native decoders:
        # deployment-specific .env files and unrelated host-mounted paths
        # can exist there. The child needs only its Python package, venv and
        # the independently provisioned and audited native runtimes.
        "--dir", "/app",
        "--ro-bind", "/app/app", "/app/app",
        "--dir", "/opt",
        "--ro-bind", "/opt/venv", "/opt/venv",
        "--dir", "/opt/pdfhub",
        "--ro-bind-try", "/opt/pdfhub/heif", "/opt/pdfhub/heif",
        "--ro-bind-try", "/opt/pdfhub/cad", "/opt/pdfhub/cad",
        "--ro-bind-try", "/lib", "/lib",
        "--ro-bind-try", "/lib64", "/lib64",
        "--ro-bind-try", "/bin", "/bin",
        "--ro-bind-try", "/etc/alternatives", "/etc/alternatives",
        "--ro-bind-try", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--ro-bind-try", "/etc/fonts", "/etc/fonts",
        "--ro-bind-try", "/etc/ssl/certs", "/etc/ssl/certs",
        # Bubblewrap applies mount operations in argv order. Native inputs
        # and output task directories can reside under the host /tmp; bind
        # their fds *before* replacing /tmp with the child private tmpfs.
        "--dir", "/input",
        "--ro-bind", str(src), SANDBOX_INPUT,
        "--setenv", "HOME", "/tmp",
        "--setenv", "TMPDIR", "/tmp",
        "--setenv", "LANG", "C.UTF-8",
        "--setenv", "PATH", "/opt/venv/bin:/usr/local/bin:/usr/bin:/bin",
        "--setenv", "PYTHONNOUSERSITE", "1",
        "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
    ]
    if destination is not None:
        sandbox += ["--bind", str(destination), SANDBOX_OUTPUT]
    # A fresh temporary filesystem and isolated proc/dev are layered AFTER
    # all host file bind mounts; /input/source and /output remain accessible.
    sandbox += ["--tmpfs", "/tmp", "--proc", "/proc", "--dev", "/dev",
                "--chdir", "/app"]
    allowed_environment = {"LD_LIBRARY_PATH", "LIBHEIF_PLUGIN_PATHS"}
    if env:
        for key, value in env.items():
            if (key not in allowed_environment or not isinstance(value, str)
                    or not value.startswith("/") or "\0" in value):
                raise ValueError("Native sandbox environment override is forbidden")
            sandbox.extend(("--setenv", key, value))
    # '--' prevents a tool argument from being interpreted as bubblewrap args.
    return sandbox + ["--", *command]
