#!/usr/bin/env python3
"""Tiny HTTP/1.0 publisher for the updater spike."""

from __future__ import annotations

import argparse
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_HOST = os.environ.get("NEWTON_PUBLISHER_HOST", "10.42.0.1")
DEFAULT_PORT = int(os.environ.get("NEWTON_PUBLISHER_PORT", "18081"))
DEFAULT_PACKAGE_PATH = Path(
    os.environ.get(
        "NEWTON_PUBLISHER_PACKAGE",
        BASE_DIR / "examples" / "harness-client" / "harness-client.pkg",
    )
)
STATUS_BODY = b"Harness server v1.1 OK\n"
INK_BODY = b"A simple curved line.\r\n"
DEFAULT_INK_PATH = BASE_DIR / "runtime" / "evidence" / "s3-ink-render.png"
PAGE_BODY = (
    b"<!doctype html><html><body>"
    b"<h1>Newton Harness Client</h1>"
    b"<p><a href=\"/harness-client.pkg\">Download package</a></p>"
    b"</body></html>"
)


class PublisherHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    package_path = DEFAULT_PACKAGE_PATH
    ink_path = DEFAULT_INK_PATH

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        if urlsplit(self.path).path != "/ink":
            self._not_found("not found\n")
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 16384:
                raise ValueError
            lines = self.rfile.read(length).decode("ascii").splitlines()
            header = lines[0].split()
            if len(header) != 4 or header[0] != "NSI1":
                raise ValueError
            canvas_width, canvas_height, stroke_count = map(int, header[1:])
            if (canvas_width, canvas_height) != (320, 480) or stroke_count < 0 or len(lines) != stroke_count + 1:
                raise ValueError
            strokes = []
            for line in lines[1:]:
                fields = line.split()
                count = int(fields[1]) if len(fields) >= 2 and fields[0] == "S" else -1
                if count < 0 or len(fields) != 2 + count * 2:
                    raise ValueError
                values = list(map(int, fields[2:]))
                points = []
                if count:
                    x, y = values[:2]
                    points.append((x, y))
                    for index in range(2, len(values), 2):
                        x += values[index]
                        y += values[index + 1]
                        points.append((x, y))
                if any(not (0 <= x < canvas_width and 0 <= y < canvas_height) for x, y in points):
                    raise ValueError
                strokes.append(points)
        except (IndexError, UnicodeDecodeError, ValueError):
            self._send_bytes(HTTPStatus.BAD_REQUEST, b"invalid ink\n", "text/plain; charset=us-ascii")
            return
        image = Image.new("L", (320, 480), "white")
        draw = ImageDraw.Draw(image)
        for points in strokes:
            # ponytail: straight black segments are enough until Stage 4 asks for polish.
            if len(points) == 1:
                draw.point(points[0], fill="black")
            elif points:
                draw.line(points, fill="black", width=2)
        self.ink_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(self.ink_path)
        self._send_bytes(HTTPStatus.OK, INK_BODY, "text/plain; charset=us-ascii")

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._send_bytes(HTTPStatus.OK, PAGE_BODY, "text/html; charset=utf-8")
            return
        if path == "/status":
            self._send_bytes(HTTPStatus.OK, STATUS_BODY, "text/plain; charset=us-ascii")
            return
        if path == "/harness-client.pkg":
            try:
                body = self.package_path.read_bytes()
            except OSError:
                self._not_found("package not found\n")
                return
            self._send_bytes(
                HTTPStatus.OK,
                body,
                "application/x-newton-compatible-pkg",
            )
            return
        self._not_found("not found\n")

    def log_message(self, fmt: str, *args: object) -> None:
        print(
            "%s - - [%s] %s"
            % (self.address_string(), self.log_date_time_string(), fmt % args),
            flush=True,
        )

    def _not_found(self, message: str) -> None:
        self._send_bytes(HTTPStatus.NOT_FOUND, message.encode("utf-8"), "text/plain; charset=utf-8")

    def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)


class PublisherServer(HTTPServer):
    allow_reuse_address = True


def make_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    package_path: Path = DEFAULT_PACKAGE_PATH,
    ink_path: Path = DEFAULT_INK_PATH,
) -> PublisherServer:
    PublisherHandler.package_path = Path(package_path)
    PublisherHandler.ink_path = Path(ink_path)
    return PublisherServer((host, port), PublisherHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE_PATH)
    args = parser.parse_args()
    with make_server(args.host, args.port, args.package) as server:
        print(f"serving http://{args.host}:{args.port} package={args.package}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
