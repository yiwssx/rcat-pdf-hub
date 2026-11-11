"""Read-only pure tests for Host URL egress /28 allocation.

Never queries the real Docker daemon, edits Host networking or logs credentials.
"""
from __future__ import annotations

import importlib.util
import ipaddress
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "url_subnet", ROOT / "scripts/provision-t90-url-egress-network.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class UrlSubnetTests(unittest.TestCase):
    def test_avoids_docker_reserved_172_subnet(self):
        occupied = [ipaddress.ip_network("172.30.0.0/16"),
                    ipaddress.ip_network("172.31.0.0/16")]
        choice = mod.pick(None, occupied, [])
        self.assertFalse(any(choice.overlaps(net) for net in occupied))
        self.assertEqual(choice.prefixlen, 28)
        self.assertTrue(choice.is_private)

    def test_does_not_reassign_live_docker_url_egress_network(self):
        net = ipaddress.ip_network("10.254.240.0/28")
        self.assertEqual(mod.pick(net, [], [net]), net)
        with self.assertRaisesRegex(ValueError, "differs"):
            mod.pick(mod.DEFAULT, [], [net])
        with self.assertRaisesRegex(ValueError, "conflicts"):
            mod.pick(net, [ipaddress.ip_network("10.254.0.0/16")], [net])

    def test_rejects_nonprivate_or_unbounded_network(self):
        for cidr in ("8.8.8.0/28", "10.0.0.0/8",
                     "172.30.243.3/28", "::1/128"):
            with self.subTest(cidr=cidr):
                with self.assertRaises(ValueError):
                    mod.parse_subnet(cidr)

    def test_host_route_reader_excludes_own_bridge_only_when_requested(self):
        routes = [
            {"dst": "default", "dev": "enp3s0"},
            {"dst": "10.10.1.0/24", "dev": "enp3s0"},
            {"dst": "172.30.243.0/28", "dev": "br-pdfhub-url"},
        ]
        addresses = [
            {"ifname": "enp3s0", "addr_info": [
                {"family": "inet", "local": "10.10.1.100", "prefixlen": 24}]},
            {"ifname": "br-pdfhub-url", "addr_info": [
                {"family": "inet", "local": "172.30.243.1", "prefixlen": 28}]},
        ]
        def data(*argv):
            return json.dumps(routes if "route" in argv else addresses)
        with patch.object(mod, "execute", side_effect=data):
            self.assertNotIn(mod.DEFAULT, mod.host_subnets(ignore_iface="br-pdfhub-url"))
            self.assertIn(mod.DEFAULT, mod.host_subnets())

    def test_atomic_env_update_preserves_credentials_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            env = root / ".env"
            env.write_text("POSTGRES_PASSWORD=keep-private\nPDFHUB_OIDC_ENABLED=true\n")
            env.chmod(0o600)
            occupied = [ipaddress.ip_network("172.30.0.0/16")]
            with (patch.object(mod, "ROOT", root),
                  patch.object(mod, "ENV", env),
                  patch.object(mod.os, "geteuid", return_value=0),
                  patch.dict(mod.os.environ, {"GITHUB_ACTIONS": ""}),
                  patch.object(mod, "docker_subnets", return_value=(occupied, [])),
                  patch.object(mod, "host_subnets", return_value=[])):
                chosen, status = mod.provision()
                self.assertEqual(status, "UPDATED")
                self.assertFalse(ipaddress.ip_network(chosen).overlaps(occupied[0]))
                self.assertIn("POSTGRES_PASSWORD=keep-private", env.read_text())
                self.assertIn("PDFHUB_OIDC_ENABLED=true", env.read_text())
                self.assertIn("PDFHUB_URL_EGRESS_SUBNET=", env.read_text())
                self.assertIn("PDFHUB_URL_EGRESS_IPV4=", env.read_text())
                self.assertEqual(stat.S_IMODE(env.stat().st_mode), 0o600)
                again, status = mod.provision()
                self.assertEqual(again, chosen)
                self.assertEqual(status, "REUSED")

    def test_partial_settings_fail_closed_without_mutation(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            env = root / ".env"
            text = "PDFHUB_URL_EGRESS_SUBNET=172.30.243.0/28\n"
            env.write_text(text)
            with (patch.object(mod, "ROOT", root),
                  patch.object(mod, "ENV", env),
                  patch.object(mod.os, "geteuid", return_value=0),
                  patch.dict(mod.os.environ, {"GITHUB_ACTIONS": ""})):
                with self.assertRaisesRegex(ValueError, "partial"):
                    mod.provision()
            self.assertEqual(env.read_text(), text)


if __name__ == "__main__":
    unittest.main()
