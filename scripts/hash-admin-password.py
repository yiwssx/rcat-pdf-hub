#!/usr/bin/env python3
from getpass import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.passwords import hash_password

first = getpass("Local admin password (min 12 chars): ")
second = getpass("Confirm password: ")
if first != second:
    raise SystemExit("Passwords do not match")
print(hash_password(first))
