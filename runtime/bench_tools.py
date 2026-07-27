#!/usr/bin/env python3
"""Measure per-call /tools latency against a live Newton (emulator or hardware).

    python3 runtime/bench_tools.py --op ping --count 10

Prints each call's latency, then min/median/max. Emulator baseline for
comparison is 5.8-11.5 s per call.

ponytail: stdlib urllib + statistics, no client class. The whole job is
"time a POST N times".
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

BASELINE = "emulator poll+POST baseline: 5.8-11.5 s"


def call(url: str, op: str, note_id: int | None, timeout: float) -> tuple[float, str, str]:
    """POST one op. Returns (elapsed_seconds, status, value-or-error)."""
    args: dict[str, int] = {} if note_id is None else {"id": note_id}
    body = json.dumps({"op": op, "args": args}).encode("utf-8")
    request = urllib.request.Request(
        f"{url}/tools?timeout={timeout:g}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout + 5) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:  # 504 timeout, 422 error, 400 unknown_op
        payload = json.loads(exc.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return time.monotonic() - start, "unreachable", str(exc)
    elapsed = time.monotonic() - start
    status = str(payload.get("status", "?"))
    return elapsed, status, str(payload.get("result", payload.get("error", "")))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://10.42.0.1:18081")
    parser.add_argument("--op", default="ping")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--id", type=int, default=None, help="entry id for get_note")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    good: list[float] = []
    for i in range(1, args.count + 1):
        elapsed, status, value = call(args.url, args.op, args.id, args.timeout)
        if status == "result":
            good.append(elapsed)
        print(f"{i:3d}  {elapsed:7.3f}s  {status:<11} {value[:60]}", flush=True)

    print(f"\n{len(good)}/{args.count} succeeded   ({BASELINE})")
    if good:
        print(
            f"min {min(good):.3f}s   median {statistics.median(good):.3f}s   "
            f"max {max(good):.3f}s"
        )
    return 0 if len(good) == args.count else 1


if __name__ == "__main__":
    sys.exit(main())
