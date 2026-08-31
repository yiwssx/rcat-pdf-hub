#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import math
import statistics
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.inf
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def request_json(url: str, api_key: str, *, method: str = "GET", body: bytes | None = None, content_type: str | None = None, timeout: float = 30) -> dict:
    headers = {"X-API-Key": api_key, "User-Agent": "rcat-pdf-hub-workload-smoke/0.5.1"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def upload_png(base: str, api_key: str, timeout: float) -> str:
    boundary = "----pdfhub" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="pixel.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode() + PNG + f"\r\n--{boundary}--\r\n".encode()
    payload = request_json(
        base + "/api/v1/files",
        api_key,
        method="POST",
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
        timeout=timeout,
    )
    return str(payload["id"])


def run_transaction(base: str, api_key: str, timeout: float) -> tuple[bool, float, str]:
    started = time.perf_counter()
    try:
        file_id = upload_png(base, api_key, timeout)
        payload = request_json(
            base + "/api/v1/pdf/images-to-pdf",
            api_key,
            method="POST",
            body=json.dumps({"file_ids": [file_id]}).encode(),
            content_type="application/json",
            timeout=timeout,
        )
        job_id = str(payload["id"])
        deadline = time.monotonic() + timeout
        output_id = ""
        while time.monotonic() < deadline:
            state = request_json(base + f"/api/v1/jobs/{job_id}", api_key, timeout=min(timeout, 30))
            if state["status"] == "completed":
                output_id = str(state["output_file_id"])
                break
            if state["status"] == "failed":
                raise RuntimeError(str(state.get("error") or "PDF job failed"))
            time.sleep(0.25)
        if not output_id:
            raise TimeoutError("PDF job did not finish before workload timeout")

        request = urllib.request.Request(
            base + f"/api/v1/files/{output_id}/download",
            headers={"X-API-Key": api_key, "User-Agent": "rcat-pdf-hub-workload-smoke/0.5.1"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            prefix = response.read(5)
        if prefix != b"%PDF-":
            raise RuntimeError("processed output is not a PDF")
        return True, (time.perf_counter() - started) * 1000, "ok"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError, KeyError, ValueError) as exc:
        return False, (time.perf_counter() - started) * 1000, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end PDF workload smoke/load gate")
    parser.add_argument("--url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--requests", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--max-p95-ms", type=float, default=30000.0)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")

    base = args.url.rstrip("/")
    results: list[tuple[bool, float, str]] = []
    wall = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run_transaction, base, args.api_key, args.timeout) for _ in range(args.requests)]
        for future in as_completed(futures):
            results.append(future.result())
    wall_seconds = max(time.perf_counter() - wall, 1e-9)

    latencies = [row[1] for row in results]
    failures = [row for row in results if not row[0]]
    error_rate = len(failures) / len(results)
    p50 = percentile(latencies, 0.50)
    p95 = percentile(latencies, 0.95)
    p99 = percentile(latencies, 0.99)
    mean = statistics.fmean(latencies)
    throughput = len(results) / wall_seconds
    print(f"pdf_transactions={len(results)} concurrency={args.concurrency} tx_per_second={throughput:.3f}")
    print(f"errors={len(failures)} error_rate={error_rate:.4f}")
    print(f"end_to_end_ms mean={mean:.2f} p50={p50:.2f} p95={p95:.2f} p99={p99:.2f}")
    for _, elapsed, message in failures[:10]:
        print(f"failure elapsed_ms={elapsed:.2f} error={message}")
    if error_rate > args.max_error_rate:
        print(f"FAIL: workload error rate {error_rate:.4f} > {args.max_error_rate:.4f}")
        return 1
    if p95 > args.max_p95_ms:
        print(f"FAIL: workload p95 {p95:.2f} ms > {args.max_p95_ms:.2f} ms")
        return 1
    print("pdf workload smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
