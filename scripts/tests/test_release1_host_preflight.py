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


    def configure_t90_code_first(self):
        for name in mod.SERVICES:
            env = self.config["services"][name]["environment"]
            env[mod.T90_MARKER] = "true"
            env["PDFHUB_FROM_PDF_TOOLS_ENABLED"] = "true"
            for key in mod.OPTIONAL_OFF:
                env[key] = "true" if key in mod.T90_CORE_REQUIRED else "false"
        self.config["services"]["web"] = {
            "environment": {
                **{key: "true" for key in mod.T90_CORE_REQUIRED},
                **{key: "true" for key in mod.T90_WEB_REQUIRED},
                "PDFHUB_FROM_PDF_TOOLS_ENABLED": "true",
            }
        }

    def test_explicit_t90_code_first_with_institutional_login_passes(self):
        self.configure_t90_code_first()
        self.assertEqual(mod.inspect_compose(self.config), [])

    def test_t90_rollout_requires_ui_and_worker_flag_consistency(self):
        self.configure_t90_code_first()
        del self.config["services"]["web"]["environment"]["PDFHUB_STAGED_TO_PDF_WEB_ENABLED"]
        self.assertIn("insecure_web_rollout_setting:PDFHUB_STAGED_TO_PDF_WEB_ENABLED",
                      mod.inspect_compose(self.config))
        self.configure_t90_code_first()
        del self.config["services"]["worker"]["environment"][mod.T90_MARKER]
        self.assertIn("service_environment_mismatch:worker:" + mod.T90_MARKER,
                      mod.inspect_compose(self.config))

    def test_t90_code_first_never_opens_native_or_url_without_host_guards(self):
        self.configure_t90_code_first()
        for key in ("PDFHUB_CHM_NATIVE_DEV_ENABLED", "PDFHUB_HEIF_NATIVE_DEV_ENABLED",
                    "PDFHUB_DWG_NATIVE_DEV_ENABLED", "PDFHUB_WPS_NATIVE_DEV_ENABLED",
                    "PDFHUB_URL_TO_PDF_DEV_ENABLED",
                    "PDFHUB_PROTECT_PDF_TOOLS_ENABLED", "PDFHUB_UNLOCK_PDF_TOOLS_ENABLED"):
            with self.subTest(key=key):
                self.config["services"]["api"]["environment"][key] = "true"
                self.assertIn("insecure_setting:" + key, mod.inspect_compose(self.config))
                self.config["services"]["api"]["environment"][key] = "false"

    def test_t90_code_first_does_not_disable_google_oidc_or_av(self):
        self.configure_t90_code_first()
        env = self.config["services"]["api"]["environment"]
        for key in ("PDFHUB_OIDC_ENABLED", "PDFHUB_CLAMAV_ENABLED",
                    "PDFHUB_RCAT_INSTITUTIONAL_ONLY"):
            with self.subTest(key=key):
                env[key] = "false"
                self.assertIn("insecure_setting:" + key, mod.inspect_compose(self.config))
                env[key] = "true"


    def configure_t90_full_runtime(self):
        import base64
        self.configure_t90_code_first()
        secret_a = base64.urlsafe_b64encode(bytes([1]) * 32).decode()
        secret_b = base64.urlsafe_b64encode(bytes([2]) * 32).decode()
        hmac_native = "a" * 64
        hmac_url = "b" * 64
        for name in mod.SERVICES:
            env = self.config["services"][name]["environment"]
            env[mod.T90_FULL_MARKER] = "true"
            env.update({key: "true" for key in mod.T90_LIMITED_FLAGS})
            env[mod.T90_AEAD_KEYS[0]] = secret_a
            env[mod.T90_AEAD_KEYS[1]] = secret_b
        self.config["services"]["web"]["environment"].update(
            {key: "true" for key in mod.T90_LIMITED_FLAGS}
        )
        heavy = self.config["services"]["worker-heavy"]
        heavy["networks"] = {key: {} for key in (
            "data", "management", "egress",
            "native_converter_internal", "url_fetch_internal"
        )}
        heavy["environment"][mod.T90_HMAC_KEYS[0]] = hmac_native
        heavy["environment"][mod.T90_HMAC_KEYS[1]] = hmac_url
        self.config["services"]["native-decoder"] = {
            "networks": {"native_converter_internal": {}},
            "environment": {mod.T90_HMAC_KEYS[0]: hmac_native},
            "cap_drop": ["ALL"], "read_only": True,
        }
        self.config["services"]["native-gotenberg"] = {
            "networks": {"native_converter_internal": {}},
        }
        self.config["services"]["url-fetcher"] = {
            "networks": {
                "url_fetch_internal": {},
                "url_fetch_egress": {"ipv4_address": "172.30.243.2"},
            },
            "environment": {mod.T90_HMAC_KEYS[1]: hmac_url},
            "cap_drop": ["ALL"], "read_only": True,
        }
        self.config["networks"] = {
            "url_fetch_egress": {
                "driver": "bridge",
                "enable_ipv6": False,
                "driver_opts": {"com.docker.network.bridge.name": "br-pdfhub-url"},
                "ipam": {"config": [{"subnet": "172.30.243.0/28"}]},
            }
        }

    def test_full_runtime_requires_owner_restricted_services_and_credentials(self):
        self.configure_t90_full_runtime()
        self.assertEqual(mod.inspect_compose(self.config), [])

    def test_full_runtime_refuses_missing_url_sidecar_and_network_access(self):
        self.configure_t90_full_runtime()
        del self.config["services"]["url-fetcher"]
        self.assertIn("missing_runtime_service:url-fetcher",
                      mod.inspect_compose(self.config))
        self.configure_t90_full_runtime()
        del self.config["services"]["worker-heavy"]["networks"]["data"]
        self.assertIn("missing_production_heavy_worker_networks",
                      mod.inspect_compose(self.config))

    def test_full_runtime_allows_host_selected_nonconflicting_private_url_subnet(self):
        self.configure_t90_full_runtime()
        self.config["networks"]["url_fetch_egress"]["ipam"]["config"][0]["subnet"] = "10.254.240.0/28"
        self.config["services"]["url-fetcher"]["networks"]["url_fetch_egress"]["ipv4_address"] = "10.254.240.2"
        self.assertEqual(mod.inspect_compose(self.config), [])

    def test_full_runtime_rejects_mismatched_ip_and_renamed_firewall_bridge(self):
        self.configure_t90_full_runtime()
        self.config["services"]["url-fetcher"]["networks"]["url_fetch_egress"]["ipv4_address"] = "172.30.243.3"
        self.assertIn("invalid_url_egress_network", mod.inspect_compose(self.config))
        self.configure_t90_full_runtime()
        self.config["networks"]["url_fetch_egress"]["driver_opts"]["com.docker.network.bridge.name"] = "br-other"
        self.assertIn("invalid_url_egress_network", mod.inspect_compose(self.config))

    def test_full_runtime_rejects_public_or_too_broad_url_egress_subnet(self):
        self.configure_t90_full_runtime()
        self.config["networks"]["url_fetch_egress"]["ipam"]["config"][0]["subnet"] = "172.30.0.0/16"
        self.assertIn("invalid_url_egress_network", mod.inspect_compose(self.config))
        self.configure_t90_full_runtime()
        self.config["networks"]["url_fetch_egress"]["ipam"]["config"][0]["subnet"] = "8.8.8.0/28"
        self.assertIn("invalid_url_egress_network", mod.inspect_compose(self.config))

    def test_full_runtime_fails_closed_on_secret_or_oidc_mismatch(self):
        self.configure_t90_full_runtime()
        self.config["services"]["url-fetcher"]["environment"][
            mod.T90_HMAC_KEYS[1]] = "incorrect"
        self.assertIn("sidecar_secret_mismatch:" + mod.T90_HMAC_KEYS[1],
                      mod.inspect_compose(self.config))
        self.configure_t90_full_runtime()
        self.config["services"]["api"]["environment"]["PDFHUB_OIDC_ENABLED"] = "false"
        self.assertIn("insecure_setting:PDFHUB_OIDC_ENABLED",
                      mod.inspect_compose(self.config))

    def test_full_runtime_never_accepts_unconfined_sidecar(self):
        self.configure_t90_full_runtime()
        self.config["services"]["native-decoder"]["cap_drop"] = []
        self.assertIn("unconfined_runtime_service:native-decoder",
                      mod.inspect_compose(self.config))


if __name__ == "__main__":
    unittest.main()
