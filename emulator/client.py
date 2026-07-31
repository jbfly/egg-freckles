#!/usr/bin/env python3
"""Command-line client for the headless Einstein control service."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "http://127.0.0.1:18080"


def instance_url(instance: str) -> str:
    """Ask podman which host port the named instance published for 8080."""
    container = f"newton-harness-{instance}_emulator_1"
    found = subprocess.run(
        ["podman", "port", container, "8080"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    published = found.stdout.decode("utf-8", "replace").split()
    if found.returncode or not published:
        detail = found.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(detail or f"emulator instance {instance!r} is not running")
    return "http://127.0.0.1:" + published[0].rsplit(":", 1)[1]


def request(
    base_url: str,
    path: str,
    *,
    payload: dict | None = None,
) -> tuple[bytes, str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"control service returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"could not reach the control service: {exc.reason}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        help=f"control service base URL (default {DEFAULT_URL})",
    )
    parser.add_argument(
        "--instance",
        default=os.environ.get("NEWTON_INSTANCE", ""),
        help="isolated emulator instance to talk to; its port is looked up",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")

    for name in ("screen", "window"):
        image = subparsers.add_parser(name)
        image.add_argument("output", type=Path)

    for name in ("tap", "window-tap"):
        tap = subparsers.add_parser(name)
        tap.add_argument("x", type=int)
        tap.add_argument("y", type=int)

    text = subparsers.add_parser("text")
    text.add_argument("value")

    key = subparsers.add_parser("key")
    key.add_argument("value")

    args = parser.parse_args()
    if not args.url:
        args.url = instance_url(args.instance) if args.instance else DEFAULT_URL

    if args.command == "status":
        body, _ = request(args.url, "/health")
        print(json.dumps(json.loads(body), indent=2))
    elif args.command in {"screen", "window"}:
        body, content_type = request(args.url, f"/{args.command}.png")
        if content_type != "image/png":
            raise SystemExit(f"expected image/png, got {content_type}")
        args.output.write_bytes(body)
        print(args.output)
    elif args.command in {"tap", "window-tap"}:
        path = "/tap" if args.command == "tap" else "/window/tap"
        body, _ = request(args.url, path, payload={"x": args.x, "y": args.y})
        print(body.decode("utf-8"))
    elif args.command == "text":
        body, _ = request(args.url, "/text", payload={"text": args.value})
        print(body.decode("utf-8"))
    elif args.command == "key":
        body, _ = request(args.url, "/key", payload={"key": args.value})
        print(body.decode("utf-8"))


if __name__ == "__main__":
    main()
