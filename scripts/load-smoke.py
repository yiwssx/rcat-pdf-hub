#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


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


def one_request(url: str, api_key: str | None, timeout: float) -> tuple[bool, float, int]:
    headers = {"User-Agent": "rcat-pdf-hub-load-smoke/0.5"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, headers=headers, method="GET")
    started = time.perf_counter()
    status = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            response.read(64)
        ok = 200 <= status < 400
    except urllib.error.HTTPError as exc:
        status = exc.code
        ok = False
    except Exception:
        ok = False
    elapsed_ms = (time.perf_counter() - started) * 1000
    return ok, elapsed_ms, status


def main() -> int:
    parser = argparse.ArgumentParser(description="Small dependency-free RCAT PDF Hub HTTP load/latency gate")
    parser.add_argument("--url", required=True, help="Base URL such as http://127.0.0.1:8080")
    parser.add_argument("--path", default="/healthz", help="Path to request; defaults to /healthz")
    parser.add_argument("--api-key", default=None, help="Optional X-API-Key for protected endpoints")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=float, default=1500.0)
    args = parser.parse_args()

    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")
    if not 0 <= args.max_error_rate <= 1:
        parser.error("--max-error-rate must be between 0 and 1")

    target = args.url.rstrip("/") + "/" + args.path.lstrip("/")
    results: list[tuple[bool, float, int]] = []
    wall_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(one_request, target, args.api_key, args.timeout) for _ in range(args.requests)]
        for future in as_completed(futures):
            results.append(future.result())
    wall_seconds = max(time.perf_counter() - wall_started, 1e-9)

    latencies = [elapsed for _, elapsed, _ in results]
    failures = [row for row in results if not row[0]]
    error_rate = len(failures) / len(results)
    p50 = percentile(latencies, 0.50)
    p95 = percentile(latencies, 0.95)
    p99 = percentile(latencies, 0.99)
    mean = statistics.fmean(latencies)
    rps = len(results) / wall_seconds

    print(f"target={target}")
    print(f"requests={len(results)} concurrency={args.concurrency} rps={rps:.2f}")
    print(f"errors={len(failures)} error_rate={error_rate:.4f}")
    print(f"latency_ms mean={mean:.2f} p50={p50:.2f} p95={p95:.2f} p99={p99:.2f}")
    if failures:
        codes: dict[int, int] = {}
        for _, _, status in failures:
            codes[status] = codes.get(status, 0) + 1
        print("failure_statuses=" + ",".join(f"{code}:{count}" for code, count in sorted(codes.items())))

    if error_rate > args.max_error_rate:
        print(f"FAIL: error rate {error_rate:.4f} > {args.max_error_rate:.4f}")
        return 1
    if p95 > args.max_p95_ms:
        print(f"FAIL: p95 {p95:.2f} ms > {args.max_p95_ms:.2f} ms")
        return 1
    print("load smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
