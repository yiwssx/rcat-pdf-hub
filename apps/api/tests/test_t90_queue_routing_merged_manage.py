"""Source-complete T90 tools must be RQ-submittable only when their own gate is ON.

Regression: an actual PDF engine+API/Web can otherwise pass all source tests but
_create_job -> enqueue_processing_job fails as an unsupported operation.
"""
import pytest

from app import queue


@pytest.mark.parametrize("operation,flag,queue_class", [
    ("watermark-pdf-image", "pdf_image_watermark_tools_enabled", "pdf"),
    ("flatten-pdf-visual", "pdf_flatten_visual_tools_enabled", "heavy"),
    ("pdf-markup", "pdf_markup_tools_enabled", "pdf"),
    ("repair-pdf-structure", "pdf_repair_structure_tools_enabled", "pdf"),
    ("pdf-extractive-summary", "pdf_extractive_assist_tools_enabled", "heavy"),
    ("pdf-extractive-evidence", "pdf_extractive_assist_tools_enabled", "heavy"),
])
def test_new_t90_operation_requires_exact_capability_gate(
    monkeypatch, operation, flag, queue_class,
):
    baseline = queue.settings
    monkeypatch.setattr(queue, "settings", baseline.model_copy(update={flag: False}))
    with pytest.raises(ValueError, match="Unsupported PDF operation"):
        queue.queue_class_for_operation(operation)
    monkeypatch.setattr(queue, "settings", baseline.model_copy(update={flag: True}))
    assert queue.queue_class_for_operation(operation) == queue_class
    assert queue.queue_name_for_operation(operation) == {
        "interactive": baseline.rq_interactive_queue,
        "pdf": baseline.rq_queue,
        "heavy": baseline.rq_heavy_queue,
    }[queue_class]


def test_unrelated_existing_queue_routing_remains_unchanged(monkeypatch):
    baseline = queue.settings
    monkeypatch.setattr(queue, "settings", baseline)
    assert queue.queue_class_for_operation("merge") == "pdf"
    assert queue.queue_class_for_operation("rotate") == "interactive"
    assert queue.queue_class_for_operation("ocr") == "heavy"
