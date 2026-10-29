"""T90-2 registry completeness and no-stub activation proof."""
from app.staged_to_pdf_adapters import (
    OFFICE_TO_PDF_OPERATIONS, STAGED_TO_PDF_INPUTS, STAGED_TO_PDF_OPERATIONS,
)
from app.t90_2_catalog import FORMAT_CAPABILITIES, FORMAT_BY_ID
from app.routers import to_pdf
from app.config import get_settings
from app.main import app as production_app


def test_exactly_40_real_capability_decisions_none_implied_released():
    assert len(FORMAT_CAPABILITIES) == 40
    assert set(FORMAT_BY_ID) == {f"T{number:02d}" for number in range(1, 41)}
    assert len({item.item_id for item in FORMAT_CAPABILITIES}) == 40
    assert {item.engineering_state for item in FORMAT_CAPABILITIES} == {"STAGED", "BLOCKED"}
    assert sum(item.engineering_state == "STAGED" for item in FORMAT_CAPABILITIES) == 25
    assert sum(item.engineering_state == "BLOCKED" for item in FORMAT_CAPABILITIES) == 15


def test_no_undocumented_stage_route_or_blocked_fake_engine():
    allowed = {op for item in FORMAT_CAPABILITIES for op in item.operations}
    assert allowed == STAGED_TO_PDF_OPERATIONS == set(STAGED_TO_PDF_INPUTS)
    assert len(allowed) == 29
    actual_routes = {
        route.path.rsplit("/", 1)[-1] + "-to-pdf"
        for route in to_pdf.router.routes
        if route.path.startswith("/api/v1/pdf/to-pdf/")
    }
    assert actual_routes == allowed
    for item in FORMAT_CAPABILITIES:
        if item.engineering_state == "BLOCKED":
            assert not item.operations
            assert item.risk_or_blocker


def test_default_off_staging_does_not_change_legacy_openapi_or_registry():
    assert not get_settings().to_pdf_tools_enabled
    assert not any(r.path.startswith("/api/v1/pdf/to-pdf/") for r in production_app.routes)
    assert "url-to-pdf" not in STAGED_TO_PDF_INPUTS
    assert "cbr-to-pdf" not in STAGED_TO_PDF_INPUTS
    assert all(v[0] and v[1].startswith(".") for v in STAGED_TO_PDF_INPUTS.values())
    assert len(OFFICE_TO_PDF_OPERATIONS) == 10


def test_public_scope_retains_existing_image_versus_convert_boundary():
    by_path = {
        route.path.rsplit("/", 1)[-1]: route
        for route in to_pdf.router.routes
        if route.path.startswith("/api/v1/pdf/to-pdf/")
    }
    assert len(by_path) == 29
    for item in FORMAT_CAPABILITIES:
        for operation in item.operations:
            assert operation.removesuffix("-to-pdf") in by_path
