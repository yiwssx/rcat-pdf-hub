"""Fast routing regressions for Lean CI, no Docker or network required."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ci_scope", ROOT / "scripts/ci-scope.py")
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ScopeTests(unittest.TestCase):
    def test_docs_are_not_full_stack(self):
        self.assertEqual(mod.classify(["README.md", "docs/guide.md"]), {
            "backend": False, "frontend": False, "ops": False, "gotenberg": False
        })

    def test_backend_only(self):
        r = mod.classify(["apps/api/app/main.py"])
        self.assertTrue(r["backend"])
        self.assertFalse(r["frontend"])
        self.assertFalse(r["ops"])

    def test_frontend_only(self):
        r = mod.classify(["apps/web/app/page.tsx"])
        self.assertTrue(r["frontend"])
        self.assertFalse(r["backend"])
        self.assertFalse(r["ops"])

    def test_operations_and_DR(self):
        r = mod.classify(["scripts/dr-drill.sh", "docker-compose.drill.yml"])
        self.assertTrue(r["ops"])
        self.assertFalse(r["backend"])
        self.assertFalse(r["frontend"])

    def test_converter_change_requires_gotenberg(self):
        r = mod.classify(["ops/gotenberg/Dockerfile"])
        self.assertTrue(r["gotenberg"])
        self.assertTrue(r["ops"])

    def test_unknown_fails_closed(self):
        r = mod.classify(["new-component/custom.ext"])
        self.assertTrue(r["backend"])
        self.assertTrue(r["frontend"])
        self.assertTrue(r["ops"])

    def test_force_all(self):
        self.assertTrue(all(mod.classify([], force_all=True).values()))

    def test_mixed(self):
        r = mod.classify(["apps/api/app/main.py", "apps/web/app/page.tsx", "README.md"])
        self.assertTrue(r["backend"])
        self.assertTrue(r["frontend"])
        self.assertFalse(r["ops"])


if __name__ == "__main__":
    unittest.main()
