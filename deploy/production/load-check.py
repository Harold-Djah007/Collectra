"""Bounded, read-only HTTP latency check; does not submit forms or sign in."""
import argparse
import concurrent.futures
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def fetch(url):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            body = response.read(1024 * 1024 + 1)
            status = response.status if len(body) <= 1024 * 1024 else 0
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
    except (OSError, urllib.error.URLError):
        status = 0
    return status, (time.perf_counter() - started) * 1000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-p95-ms", type=float, default=3000)
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        parser.error("Use a bare HTTP(S) origin without credentials or query parameters")
    if not 1 <= args.requests <= 500 or not 1 <= args.concurrency <= min(32, args.requests):
        parser.error("Use 1-500 requests and 1-32 concurrent requests, no more than the request count")
    if not math.isfinite(args.max_p95_ms) or args.max_p95_ms <= 0:
        parser.error("Latency threshold must be positive")
    url = args.base_url.rstrip("/") + "/accounts/login/"
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(fetch, [url] * args.requests))
    latencies = [latency for _, latency in results]
    failures = sum(status != 200 for status, _ in results)
    p95 = percentile(latencies, .95)
    print(json.dumps({"endpoint": url, "requests": args.requests, "concurrency": args.concurrency,
                      "failures": failures, "p50_ms": round(percentile(latencies, .5), 1),
                      "p95_ms": round(p95, 1), "max_ms": round(max(latencies), 1),
                      "passed": failures == 0 and p95 <= args.max_p95_ms,
                      "scope": "Unauthenticated login GET only; not mobile sync/report load"}, indent=2))
    return 1 if failures or p95 > args.max_p95_ms else 0


if __name__ == "__main__":
    raise SystemExit(main())
