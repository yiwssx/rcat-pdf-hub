"""T90-0.16: no-prod-access Phase 0 architecture readiness tests."""
import importlib.util
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/validate-t90-phase-zero.py"
spec = importlib.util.spec_from_file_location("t90_phase_zero_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

SNAPSHOTS = (
    "contracts/pdf-tools.v1.json",
    "contracts/pdf-output-manifest.v1.schema.json",
    "apps/api/app/operation_adapters.py",
    "apps/api/app/queue.py",
    "apps/api/app/routers/jobs.py",
    "apps/api/app/routers/pdf.py",
    "apps/api/app/filetypes.py",
    "apps/api/app/services/zip_preflight.py",
    "apps/api/app/worker_tasks.py",
    "apps/api/app/config.py",
    "apps/api/app/schemas.py",
)


class T90PhaseZeroReadinessTests(unittest.TestCase):
    def test_actual_90_tool_phase_zero_contract(self):
        self.assertEqual([], gate.inspect_phase_zero())

    def with_snapshot(self, mutate, expected):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for path in SNAPSHOTS:
                dest = root / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPO / path, dest)
            mutate(root)
            previous = gate.ROOT
            try:
                gate.ROOT = root
                errors = gate.inspect_phase_zero()
                self.assertTrue(any(expected in error for error in errors), errors)
            finally:
                gate.ROOT = previous

    def test_detect_unexpected_tool_activation(self):
        def mutate(root):
            path = root / "contracts/pdf-tools.v1.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["tools"][0]["runtime_enabled"] = True
            path.write_text(json.dumps(data), encoding="utf-8")
        self.with_snapshot(mutate, "unexpectedly enabled")

    def test_detect_queue_and_adapter_drift(self):
        def mutate(root):
            path = root / "apps/api/app/queue.py"
            source = path.read_text(encoding="utf-8")
            assert '"merge",' in source
            path.write_text(source.replace('"merge",', "", 1), encoding="utf-8")
        self.with_snapshot(mutate, "diverged")

    def test_detect_missing_pdf_only_input_gate(self):
        def mutate(root):
            path = root / "apps/api/app/routers/pdf.py"
            source = path.read_text(encoding="utf-8")
            assert '"compress",' in source
            path.write_text(source.replace('"compress",', "", 1), encoding="utf-8")
        self.with_snapshot(mutate, "PDF-only MIME validation")

    def test_detect_201_artifact_boundary_drift(self):
        def mutate(root):
            path = root / "contracts/pdf-output-manifest.v1.schema.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["properties"]["artifacts"]["maxItems"] = 200
            path.write_text(json.dumps(data), encoding="utf-8")
        self.with_snapshot(mutate, "Multi-output ZIP+200")

    def test_detect_unsafe_flag_activation(self):
        def mutate(root):
            path = root / "apps/api/app/config.py"
            source = path.read_text(encoding="utf-8")
            assert 'multi_output_artifacts_enabled: bool = False' in source
            path.write_text(
                source.replace('multi_output_artifacts_enabled: bool = False',
                               'multi_output_artifacts_enabled: bool = True'),
                encoding="utf-8",
            )
        self.with_snapshot(mutate, "Feature flag default not false")

    def test_detect_missing_worker_adapter_call(self):
        def mutate(root):
            path = root / "apps/api/app/worker_tasks.py"
            source = path.read_text(encoding="utf-8")
            assert "execute_operation(job.operation, inputs, output, params)" in source
            path.write_text(
                source.replace("execute_operation(job.operation, inputs, output, params)",
                               "pass"),
                encoding="utf-8",
            )
        self.with_snapshot(mutate, "reviewed adapter seam")

    def test_detect_unsafe_office_limit_expansion(self):
        def mutate(root):
            path = root / "apps/api/app/services/zip_preflight.py"
            source = path.read_text(encoding="utf-8")
            assert "MAX_OFFICE_ZIP_ENTRIES = 2048" in source
            path.write_text(source.replace("MAX_OFFICE_ZIP_ENTRIES = 2048",
                                           "MAX_OFFICE_ZIP_ENTRIES = 999999"), encoding="utf-8")
        self.with_snapshot(mutate, "Office ZIP bound")


if __name__ == "__main__":
    unittest.main()
