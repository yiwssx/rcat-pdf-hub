"""T90-0.15: 13 static adapters preserve existing worker PDF engine semantics."""
from pathlib import Path

import pytest

from app import worker_tasks
from app.operation_adapters import ADAPTERS, execute_operation
from app.queue import SUPPORTED_OPERATIONS, queue_class_for_operation
from app.routers.jobs import OPERATION_SCOPES
from app.services import pdf_tools


@pytest.mark.parametrize("operation,engine,count,params,expected_args,expected_kwargs", [
    ("merge", "merge", 2, {}, 3, {}),
    ("organize", "organize", 1, {"pages": [{"page": 1, "rotation": 0}]}, 3, {}),
    ("split", "split", 1, {"pages": "1-z"}, 3, {}),
    ("rotate", "rotate", 1, {"pages": "1-z", "degrees": 90}, 4, {}),
    ("compress", "compress", 1, {}, 2, {}),
    ("ocr", "ocr", 1, {}, 5, {}),
    ("pdfa", "pdfa", 1, {}, 3, {}),
    ("office-to-pdf", "office_to_pdf", 1, {}, 2, {}),
    ("images-to-pdf", "images_to_pdf", 2, {}, 2,
     {"page_size": "auto", "fit": "contain", "margin": 18.0, "dpi": 150}),
    ("pdf-to-images", "pdf_to_images", 1, {}, 2,
     {"image_format": "png", "dpi": 150, "first_page": 1, "last_page": None}),
    ("watermark", "watermark_text", 1, {"text": "RCAT"}, 2,
     {"text": "RCAT", "font_size": 48.0, "opacity": .18,
      "rotation": 45.0, "position": "center", "margin": 36.0}),
    ("page-numbers", "add_page_numbers", 1, {}, 2,
     {"format_text": "{page} / {total}", "start_number": 1,
      "font_size": 10.0, "position": "bottom-center", "margin": 24.0}),
    ("stamp", "stamp_pdf", 2, {}, 3,
     {"position": "bottom-right", "scale": .20, "margin": 24.0}),
])
def test_static_engine_dispatch_preserves_legacy_default_arguments(
    monkeypatch, operation, engine, count, params, expected_args, expected_kwargs
):
    observed = []
    monkeypatch.setattr(pdf_tools, engine, lambda *a, **kw: observed.append((a, kw)))
    paths = [Path(f"/tmp/t90-existing-{n}.pdf") for n in range(count)]
    output = Path("/tmp/t90-existing-output.pdf")
    execute_operation(operation, paths, output, params)
    assert len(observed) == 1
    args, kwargs = observed[0]
    assert len(args) == expected_args
    assert args[-1] == output or args[-2] == output
    assert kwargs == expected_kwargs


def test_operation_identity_exactly_matches_queue_and_current_api():
    assert len(ADAPTERS) == 13
    assert set(ADAPTERS) == SUPPORTED_OPERATIONS
    assert set(ADAPTERS) == set(OPERATION_SCOPES)
    for operation in ADAPTERS:
        assert queue_class_for_operation(operation) in {"interactive", "pdf", "heavy"}


def test_unsupported_tool_cannot_execute_arbitrary_engine(monkeypatch):
    observed = []
    monkeypatch.setattr(pdf_tools, "compress", lambda *args, **kw: observed.append(True))
    with pytest.raises(RuntimeError, match="Unsupported operation"):
        execute_operation("__import__('os').system('touch /tmp/pwned')", [], Path("/tmp/anything"), {})
    assert not observed


@pytest.mark.parametrize("operation,bad_count", [
    ("merge", 0), ("merge", 1), ("merge", 51),
    ("stamp", 0), ("stamp", 1), ("stamp", 3),
    ("pdf-to-images", 0), ("compress", 2),
    ("images-to-pdf", 0), ("images-to-pdf", 101),
])
def test_adapter_rejects_invalid_input_counts_before_call(monkeypatch, operation, bad_count):
    monkeypatch.setattr(pdf_tools, "merge", lambda *a, **k: pytest.fail("Engine called"))
    with pytest.raises(ValueError, match="input files"):
        execute_operation(operation, [Path("/tmp/input") for _ in range(bad_count)],
                          Path("/tmp/output"), {})


def test_adapter_rejects_non_object_params(monkeypatch):
    monkeypatch.setattr(pdf_tools, "compress", lambda *a, **k: pytest.fail("Engine called"))
    with pytest.raises(ValueError, match="object"):
        execute_operation("compress", [Path("/tmp/input")], Path("/tmp/output"), [])


def test_existing_worker_patch_target_points_to_same_converter_module():
    assert worker_tasks.pdf_tools is pdf_tools


def test_selected_engine_options_preserved_exactly(monkeypatch):
    observed = []
    monkeypatch.setattr(pdf_tools, "images_to_pdf", lambda *args, **kw: observed.append(kw))
    execute_operation("images-to-pdf", [Path("/tmp/a.png")], Path("/tmp/a.pdf"), {
        "page_size": "a4", "fit": "cover", "margin": 0.0, "dpi": 300,
    })
    assert observed == [{"page_size": "a4", "fit": "cover", "margin": 0.0, "dpi": 300}]
