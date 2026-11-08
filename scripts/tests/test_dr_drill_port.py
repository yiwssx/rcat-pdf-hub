"""Port-selection regressions for the isolated DR drill."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import socket
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("drill_port", ROOT / "scripts/select-drill-port.py")
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DrillPortTests(unittest.TestCase):
    def test_auto_selects_available_loopback_port(self) -> None:
        port = module.choose_port(None)
        self.assertGreaterEqual(port, 1024)
        self.assertLessEqual(port, 65535)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))

    def test_explicit_free_port(self) -> None:
        port = module.choose_port(None)
        self.assertEqual(module.choose_port(str(port)), port)

    def test_explicit_busy_port_fails_closed(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with self.assertRaises(OSError):
                module.choose_port(str(port))

    def test_invalid_explicit_ports_rejected(self) -> None:
        for bad in ("0", "80", "65536", "-1", "not-a-port", "3.14", " 8081", "１２３４"):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    module.choose_port(bad)


if __name__ == "__main__":
    unittest.main()
