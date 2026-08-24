import os
import sys

from app.migrate import run_migrations


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "api"
    if mode == "api":
        run_migrations()
        os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
    raise SystemExit(f"Unknown entrypoint mode: {mode}")


if __name__ == "__main__":
    main()
