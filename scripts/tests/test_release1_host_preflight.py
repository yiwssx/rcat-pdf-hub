"""Negative and positive read-only Compose preflight tests."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("r1host", ROOT / "scripts/release1-host-preflight.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class HostPreflightTests(unittest.TestCase):
    def setUp(self):
        env = {**mod.REQUIRED,
               "PDFHUB_OIDC_CLIENT_ID": "r1-test-client",
               "PDFHUB_OIDC_CLIENT_SECRET": "r1-test-value-never-log",
               "PDFHUB_PUBLIC_BASE_URL": "https://pdf.rcat.ac.th"}
        self.config = {"services": {name: {"environment": dict(env)}
                                    for name in mod.SERVICES}}

    def test_secure_configuration_shape_passes(self):
        self.assertEqual(mod.inspect_compose(self.config), [])

    def test_live_oidc_missing_fails(self):
        self.config["services"]["api"]["environment"]["PDFHUB_OIDC_ENABLED"] = "false"
        self.assertIn("insecure_setting:PDFHUB_OIDC_ENABLED", mod.inspect_compose(self.config))

    def test_prevent_non_rcat_access_or_http(self):
        env = self.config["services"]["api"]["environment"]
        env["PDFHUB_RCAT_INSTITUTIONAL_ONLY"] = "false"
        env["PDFHUB_PUBLIC_BASE_URL"] = "http://pdf.rcat.ac.th"
        failures = mod.inspect_compose(self.config)
        self.assertIn("insecure_setting:PDFHUB_RCAT_INSTITUTIONAL_ONLY", failures)
        self.assertIn("unsafe_public_base_url", failures)

    def test_credential_not_printed_in_diagnostics(self):
        env = self.config["services"]["worker"]["environment"]
        env["PDFHUB_OIDC_CLIENT_SECRET"] = "very-private-value"
        self.assertNotIn("very-private-value", " ".join(mod.inspect_compose(self.config)))
        self.assertIn("service_environment_mismatch:worker:PDFHUB_OIDC_CLIENT_SECRET",
                      mod.inspect_compose(self.config))

    def test_disabled_antivirus_blocks_pilot(self):
        self.config["services"]["api"]["environment"]["PDFHUB_CLAMAV_ENABLED"] = "false"
        self.assertIn("insecure_setting:PDFHUB_CLAMAV_ENABLED",
                      mod.inspect_compose(self.config))

    def test_missing_worker_blocks_pilot(self):
        del self.config["services"]["worker-heavy"]
        self.assertIn("missing_service:worker-heavy", mod.inspect_compose(self.config))

    def test_unforwarded_optional_flags_use_api_default_off(self):
        for name in mod.SERVICES:
            env = self.config["services"][name]["environment"]
            for key in mod.OPTIONAL_OFF:
                self.assertNotIn(key, env)
        self.assertEqual(mod.inspect_compose(self.config), [])

    def test_newly_forwarded_experimental_flag_blocks_pilot(self):
        self.config["services"]["api"]["environment"]["PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED"] = "true"
        self.assertIn(
            "insecure_setting:PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED",
            mod.inspect_compose(self.config),
        )

    def test_worker_experimental_flag_cannot_diverge(self):
        self.config["services"]["worker"]["environment"]["PDFHUB_TO_PDF_TOOLS_ENABLED"] = "true"
        self.assertIn(
            "service_environment_mismatch:worker:PDFHUB_TO_PDF_TOOLS_ENABLED",
            mod.inspect_compose(self.config),
        )

    def test_all_uncertified_r1_experimental_flags_fail_closed(self):
        # Regression: an R1 preflight must never pass merely because a newly
        # forwarded T90 flag is omitted from its denylist.
        for key in mod.OPTIONAL_OFF:
            with self.subTest(key=key):
                env = self.config["services"]["api"]["environment"]
                env[key] = "true"
                self.assertIn(
                    "insecure_setting:" + key,
                    mod.inspect_compose(self.config),
                )
                del env[key]

    def test_all_uncertified_worker_flags_must_match_api(self):
        for key in mod.OPTIONAL_OFF:
            with self.subTest(key=key):
                env = self.config["services"]["worker-heavy"]["environment"]
                env[key] = "true"
                self.assertIn(
                    "service_environment_mismatch:worker-heavy:" + key,
                    mod.inspect_compose(self.config),
                )
                del env[key]

    def test_experimental_converter_flag_blocks_pilot(self):
        self.config["services"]["api"]["environment"]["PDFHUB_FROM_PDF_TOOLS_ENABLED"] = "true"
        self.assertIn("insecure_setting:PDFHUB_FROM_PDF_TOOLS_ENABLED",
                      mod.inspect_compose(self.config))


if __name__ == "__main__":
    unittest.main()
