#!/usr/bin/env python3
"""Tiny HTTP/1.0 publisher for the updater spike."""

from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import subprocess
import tempfile
import zlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from server import NATIVE_HANDSHAKE, frame_line, parse_frame

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
DEFAULT_INK_PATH = BASE_DIR / "runtime" / "evidence" / "ink-latest.png"
DEFAULT_NOTE_PATH = BASE_DIR / "runtime" / "evidence" / "notes-latest.json"
INK_PROMPT = (
    "The attached PNG is a sketch or handwriting captured from the 320x480 screen "
    "of a Newton MessagePad. Answer with one short plain sentence under 90 "
    "characters saying what is drawn; if it is writing, transcribe it. "
    "No preamble, no markdown."
)
INK_TIMEOUT = 120
MODEL_HOST = os.environ.get("NEWTON_MODEL_HOST", "127.0.0.1")
MODEL_PORT = int(os.environ.get("NEWTON_MODEL_PORT", "6801"))
MODEL_TIMEOUT = 120
PAGE_BODY = (
    b"<!doctype html><html><body>"
    b"<h1>Newton Harness Client</h1>"
    b"<p><a href=\"/harness-client.pkg\">Download package</a></p>"
    b"</body></html>"
)


def ascii_line(text: str, limit: int = 100) -> str:
    """Collapse to one short us-ascii line the Newton can print verbatim."""
    clean = " ".join(text.encode("ascii", "replace").decode("ascii").split())
    return clean[:limit]


def ask_model(prompt: str, host: str = MODEL_HOST, port: int = MODEL_PORT) -> str:
    """Send one clean MSG turn through the existing real-backend server."""
    def line(stream) -> bytes:
        raw = stream.readline(241)
        if not raw.endswith(b"\n"):
            raise RuntimeError("model protocol ended")
        return raw

    with socket.create_connection((host, port), timeout=MODEL_TIMEOUT) as sock:
        sock.settimeout(MODEL_TIMEOUT)
        stream = sock.makefile("rwb", buffering=0)
        stream.write(NATIVE_HANDSHAKE + b"\r\n" + frame_line(0, "HELLO", "NEWTON1 note"))
        if line(stream) != b"ACK 00\r\n":
            raise RuntimeError("model HELLO rejected")
        seq, op, _ = parse_frame(line(stream))
        if op != "STAT":
            raise RuntimeError("model not ready")
        stream.write(f"ACK {seq:02d}\r\n".encode("ascii"))

        # ponytail: reset the shared chat once; this bridge is one note, one turn.
        for client_seq, message in ((1, "/new"), (2, prompt)):
            print(f"NOTE WIRE C> MSG {message!r}", flush=True)
            stream.write(frame_line(client_seq, "MSG", message))
            if line(stream) != f"ACK {client_seq:02d}\r\n".encode("ascii"):
                raise RuntimeError("model MSG rejected")
            reply = []
            error = ""
            while True:
                seq, op, payload = parse_frame(line(stream))
                print(f"NOTE WIRE S> {op} {payload}".rstrip(), flush=True)
                stream.write(f"ACK {seq:02d}\r\n".encode("ascii"))
                if op == "TEXT":
                    reply.append(payload)
                elif op == "STAT" and payload.startswith("ERROR"):
                    error = payload
                elif op == "PROMPT":
                    break
            if error:
                raise RuntimeError(error)
        answer = ascii_line(" ".join(reply), 200)
        if not answer:
            raise RuntimeError("no model text")
        return answer


def interpret(png_path: Path) -> str:
    """Return a real vision reading of the rendered ink, or raise RuntimeError."""
    # ponytail: one blocking subprocess, same boring shape as server.py CodexBackend.
    # Measured ~9 s, well inside the client's timeout, so no job queue or polling.
    with tempfile.TemporaryDirectory(prefix="newton-ink-") as tmp:
        proc = subprocess.run(
            ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check",
             "--cd", tmp, "--json", "-i", str(png_path), "--", INK_PROMPT],
            cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True,
            timeout=INK_TIMEOUT, check=False,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"codex exited {proc.returncode}")
    text = ""
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text") or text
    reading = ascii_line(text)
    if not reading:
        raise RuntimeError("no model text")
    return reading


def save_ink_png(path: Path, strokes: list[list[tuple[int, int]]]) -> None:
    pixels = bytearray(b"\xff" * (320 * 480))

    def dot(x: int, y: int) -> None:
        for px, py in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)):
            if px < 320 and py < 480:
                pixels[py * 320 + px] = 0

    for points in strokes:
        if len(points) == 1:
            dot(*points[0])
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            # ponytail: integer segments avoid a dependency for one grayscale PNG.
            dx, dy = abs(x1 - x0), -abs(y1 - y0)
            sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
            error = dx + dy
            while True:
                dot(x0, y0)
                if (x0, y0) == (x1, y1):
                    break
                twice = 2 * error
                if twice >= dy:
                    error += dy
                    x0 += sx
                if twice <= dx:
                    error += dx
                    y0 += sy

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    rows = b"".join(b"\0" + pixels[y * 320 : (y + 1) * 320] for y in range(480))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 320, 480, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


class PublisherHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    package_path = DEFAULT_PACKAGE_PATH
    ink_path = DEFAULT_INK_PATH
    note_path = DEFAULT_NOTE_PATH

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        path = urlsplit(self.path).path
        if path == "/note":
            self._save_note()
            return
        if path != "/ink":
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
        self.ink_path.parent.mkdir(parents=True, exist_ok=True)
        save_ink_png(self.ink_path, strokes)
        try:
            reading, status = interpret(self.ink_path), HTTPStatus.OK
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            reading, status = ascii_line(f"No reading: {exc}", 80), HTTPStatus.BAD_GATEWAY
        # ponytail: "INK " prefix is all the client needs to tell the body
        # apart from the HTTP header lines its endpoint also delivers.
        self._send_bytes(status, f"INK {reading}\r\n".encode("ascii"),
                         "text/plain; charset=us-ascii")

    def _save_note(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 9216:
                raise ValueError
            raw = self.rfile.read(length)
            note = json.loads(raw.decode("utf-8"))
            if not isinstance(note, dict) or set(note) != {"id", "title", "modified", "text", "truncated"}:
                raise ValueError
            if note["id"] is not None and (isinstance(note["id"], bool) or not isinstance(note["id"], int)):
                raise ValueError
            if note["modified"] is not None and (isinstance(note["modified"], bool) or not isinstance(note["modified"], int)):
                raise ValueError
            if not isinstance(note["title"], str) or not isinstance(note["text"], str):
                raise ValueError
            if not isinstance(note["truncated"], bool):
                raise ValueError
            if len(note["title"].encode("utf-8")) > 512 or len(note["text"].encode("utf-8")) > 8192:
                raise ValueError
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            self._send_bytes(HTTPStatus.BAD_REQUEST, b"invalid note\n", "text/plain; charset=us-ascii")
            return
        self.note_path.parent.mkdir(parents=True, exist_ok=True)
        # ponytail: one validated document, atomically replaced; no note database.
        temp = self.note_path.with_suffix(self.note_path.suffix + ".tmp")
        temp.write_text(json.dumps(note, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.note_path)
        try:
            answer, status = ask_model(note["text"]), HTTPStatus.OK
        except (OSError, RuntimeError, ValueError) as exc:
            answer, status = ascii_line(f"No answer: {exc}", 80), HTTPStatus.BAD_GATEWAY
        self._send_bytes(status, f"NOTE {answer}\r\n".encode("ascii"),
                         "text/plain; charset=us-ascii")

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
    note_path: Path = DEFAULT_NOTE_PATH,
) -> PublisherServer:
    PublisherHandler.package_path = Path(package_path)
    PublisherHandler.ink_path = Path(ink_path)
    PublisherHandler.note_path = Path(note_path)
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
