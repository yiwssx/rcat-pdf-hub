#!/usr/bin/env bash
# check-test-coverage.sh — Run pytest with coverage and fail if below threshold.
#
# Usage:
#   ./check-test-coverage.sh [--output-dir <dir>] [--fail-under <pct>]
#
# Options:
#   --output-dir <dir>   Directory to write coverage results (default: ./coverage-results)
#   --fail-under <pct>   Minimum coverage percentage (default: 80)

set -euo pipefail

# ─── Defaults ───────────────────────────────────────────────────────────────────
OUTPUT_DIR="./coverage-results"
FAIL_UNDER=80

# ─── Parse arguments ────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --fail-under)
            FAIL_UNDER="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--output-dir <dir>] [--fail-under <pct>]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# ─── Setup ───────────────────────────────────────────────────────────────────────
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="$OUTPUT_DIR/coverage-report-${TIMESTAMP}.txt"
HTML_DIR="$OUTPUT_DIR/htmlcov"

echo "=== Test Coverage Check ==="
echo "Fail-under threshold: ${FAIL_UNDER}%"
echo "Output directory:     ${OUTPUT_DIR}"
echo ""

# ─── Run pytest with coverage ────────────────────────────────────────────────────
EXIT_CODE=0
pytest \
    --cov=app \
    --cov-report=term-missing \
    --cov-report="html:${HTML_DIR}" \
    --cov-report="json:${OUTPUT_DIR}/coverage.json" \
    --cov-fail-under="${FAIL_UNDER}" \
    -q \
    2>&1 | tee "$RESULTS_FILE" || EXIT_CODE=$?

echo "" >> "$RESULTS_FILE"
echo "Timestamp: $(date -Iseconds)" >> "$RESULTS_FILE"
echo "Threshold: ${FAIL_UNDER}%" >> "$RESULTS_FILE"

# ─── Report result ───────────────────────────────────────────────────────────────
if [[ $EXIT_CODE -eq 0 ]]; then
    echo ""
    echo "PASS: Coverage meets the ${FAIL_UNDER}% threshold."
    echo "Status: PASS" >> "$RESULTS_FILE"
    echo "HTML report: ${HTML_DIR}/index.html"
    echo "Full report: ${RESULTS_FILE}"
else
    echo ""
    echo "FAIL: Coverage is below the ${FAIL_UNDER}% threshold."
    echo "Status: FAIL" >> "$RESULTS_FILE"
    echo "Review missing coverage in: ${HTML_DIR}/index.html"
    echo "Full report: ${RESULTS_FILE}"
fi

exit $EXIT_CODE
