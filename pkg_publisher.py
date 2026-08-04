#!/usr/bin/env python3
"""Tiny HTTP/1.0 publisher for the updater spike."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import struct
import subprocess
import tempfile
import threading
import zlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from server import NATIVE_HANDSHAKE, frame_line, parse_frame

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_HOST = os.environ.get("NEWTON_PUBLISHER_HOST", "10.42.0.1")
DEFAULT_PORT = int(os.environ.get("NEWTON_PUBLISHER_PORT", "18081"))
DEFAULT_PACKAGE_PATH = Path(
    os.environ.get(
        "NEWTON_PUBLISHER_PACKAGE",
        BASE_DIR / "examples" / "harness-client" / "egg-freckles.pkg",
    )
)
STATUS_BODY = b"Harness server v1.1 OK\n"
STAGING_DIR = BASE_DIR / "runtime" / "staging" / "hardware"
DEFAULT_INK_PATH = BASE_DIR / "runtime" / "evidence" / "ink-latest.png"
DEFAULT_NOTE_PATH = BASE_DIR / "runtime" / "evidence" / "notes-latest.json"
INK_PROMPT = (
    "The attached PNG is a sketch or handwriting captured from the 320x480 screen "
    "of a Newton MessagePad. Answer with one short plain sentence under 90 "
    "characters saying what is drawn; if it is writing, transcribe it. "
    "No preamble, no markdown."
)
# A mixed note — a drawing with typed words on the same page — arrives as one
# request whose NSI1 body carries the words on an "H" line. A word written under
# a drawing is the most useful token in a vision prompt, so it goes in as
# context rather than being dropped or sent as a second model call.
INK_HINT_PROMPT = " The drawing is accompanied by this note text: "
INK_HINT_LIMIT = 200
INK_TIMEOUT = 120
MODEL_HOST = os.environ.get("NEWTON_MODEL_HOST", "127.0.0.1")
MODEL_PORT = int(os.environ.get("NEWTON_MODEL_PORT", "6801"))
MODEL_TIMEOUT = 120
TOOL_OP = re.compile(r"[A-Za-z0-9_]+\Z")


def unescape(value: str) -> str:
    out, index = [], 0
    escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"'}
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value) and value[index + 1] in escapes:
            index += 1
            out.append(escapes[value[index]])
        else:
            out.append(value[index])
        index += 1
    return "".join(out)


class ToolBroker:
    """One resident-package request, correlated with its eventual outcome."""

    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.next_id = 1
        self.pending: dict[str, object] | None = None
        self.outcome: dict[str, object] | None = None
        self.connection: socket.socket | None = None
        self.heartbeat_seconds = 3.0

    def submit(self, op: str, args: dict[str, object], timeout: float) -> dict[str, object]:
        with self.condition:
            if self.pending is not None:
                raise RuntimeError("tool request already pending")
            request_id = str(self.next_id)
            self.next_id += 1
            self.pending = {"request_id": request_id, "op": op, "args": args}
            self.outcome = None
            self.condition.notify_all()
            if not self.condition.wait_for(lambda: self.outcome is not None, timeout):
                result = {"request_id": request_id, "status": "timeout"}
            else:
                result = self.outcome
            self.pending = None
            self.outcome = None
            return result

    @staticmethod
    def _line(stream) -> str:
        line = stream.readline(4097)
        if not line or len(line) > 4096 or not line.endswith(b"\n"):
            raise ConnectionError("persistent Newton connection closed mid-response")
        return line.rstrip(b"\r\n").decode("utf-8")

    def serve(self, connection: socket.socket, stream) -> None:
        with self.condition:
            if self.connection is not None:
                self.connection.close()
            self.connection = connection
            self.condition.notify_all()
        print(f"Newton tools connected {connection.getpeername()[0]}:{connection.getpeername()[1]}",
              flush=True)
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(
                        lambda: self.connection is not connection or self.pending is not None,
                        self.heartbeat_seconds)
                    if self.connection is not connection:
                        return
                    request = self.pending
                heartbeat = request is None
                if heartbeat:
                    request = {"request_id": "0", "op": "ping", "args": {}}
                argument = request["args"].get("id", "")
                connection.sendall(
                    f"TOOLS {request['request_id']} {request['op']} {argument}\r\n".encode("ascii"))
                request_id, status, value = (self._line(stream) for _ in range(3))
                if request_id != request["request_id"] or status not in {
                    "result", "error", "unknown_op"
                }:
                    return
                if not heartbeat:
                    key = "result" if status == "result" else "error"
                    self.complete({"request_id": request_id, "status": status,
                                   key: unescape(value)})
                if self._line(stream) != "POLL":
                    return
        except (ConnectionError, OSError, UnicodeError):
            pass
        finally:
            with self.condition:
                if self.connection is connection:
                    self.connection = None
                    self.condition.notify_all()
            print("Newton tools disconnected", flush=True)

    def poll(self) -> dict[str, object] | None:
        with self.condition:
            return self.pending

    def complete(self, outcome: dict[str, object]) -> bool:
        with self.condition:
            if self.pending is None or outcome.get("request_id") != self.pending["request_id"]:
                return False
            self.outcome = outcome
            self.pending = None
            self.condition.notify_all()
            return True


PAGE_BODY = (
    b"<!doctype html><html><body>"
    b"<h1>Newton Harness Client</h1>"
    b"<p><a href=\"/egg-freckles.pkg\">Download package</a></p>"
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


def interpret(png_path: Path, hint: str = "") -> str:
    """Return a real vision reading of the rendered ink, or raise RuntimeError."""
    prompt = INK_PROMPT + (INK_HINT_PROMPT + hint if hint else "")
    # The same shape as ask_model's NOTE WIRE lines: the log is where an ops
    # failure gets diagnosed (the hardware 502 was codex missing from PATH).
    print(f"INK PROMPT {prompt!r}", flush=True)
    # ponytail: one blocking subprocess, same boring shape as server.py CodexBackend.
    # Measured ~9 s, well inside the client's timeout, so no job queue or polling.
    with tempfile.TemporaryDirectory(prefix="newton-ink-") as tmp:
        proc = subprocess.run(
            ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check",
             "--cd", tmp, "--json", "-i", str(png_path), "--", prompt],
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

    def parse_request(self) -> bool:
        if self.raw_requestline.rstrip(b"\r\n") == b"POLL":
            self.requestline = self.command = "POLL"
            self.request_version, self.close_connection = "HTTP/0.9", True
            return True
        return super().parse_request()

    def do_POLL(self) -> None:  # noqa: N802 - Newton long-poll transport
        self.server.tools.serve(self.connection, self.rfile)
    package_path = DEFAULT_PACKAGE_PATH
    ink_path = DEFAULT_INK_PATH
    note_path = DEFAULT_NOTE_PATH

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        path = urlsplit(self.path).path
        if path == "/tools":
            self._run_tool()
            return
        if path == "/tools/outcome":
            self._tool_outcome()
            return
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
            if (canvas_width, canvas_height) != (320, 480) or stroke_count < 0:
                raise ValueError
            # NSI1 grammar: the header line, then AT MOST ONE optional
            # "H <text>" line, then exactly stroke_count "S ..." lines. The tag
            # stays NSI1 and the header's four fields do not change, because the
            # physical MP2000 still runs an older client whose bodies have no H
            # line and must keep parsing.
            body_lines, hint = lines[1:], ""
            if body_lines and body_lines[0].startswith("H "):
                hint = body_lines[0][2:]
                if not 0 < len(hint) <= INK_HINT_LIMIT or not hint.isprintable():
                    raise ValueError
                body_lines = body_lines[1:]
            if len(body_lines) != stroke_count:
                raise ValueError
            # A text-only note routed from the Notes envelope menu ("Send to
            # AI", ROADMAP Track L2) arrives as a zero-stroke body: the header,
            # one H line, and nothing else. There is no drawing to render or
            # look at, so it is answered from the text alone. Without the H line
            # a zero-stroke body carries no question at all and is rejected.
            if stroke_count == 0 and not hint:
                raise ValueError
            strokes = []
            for line in body_lines:
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
        # What actually arrived, so a round can check the client's ink budget
        # against the wire instead of against arithmetic. The fifth hardware
        # test's truncation bug was invisible here precisely because nothing
        # logged how much geometry a body carried.
        points = sum(len(stroke) for stroke in strokes)
        rate = f" bytes_per_point={length / points:.2f}" if points else ""
        print(f"INK BODY bytes={length} strokes={stroke_count} points={points}{rate}",
              flush=True)
        if strokes:
            self.ink_path.parent.mkdir(parents=True, exist_ok=True)
            save_ink_png(self.ink_path, strokes)
        try:
            # Zero strokes: skip the PNG and the vision call and put the note's
            # own words to the model as a plain turn. One reply shape either
            # way, so the client needs no branch at all.
            reading = interpret(self.ink_path, hint) if strokes else ask_model(hint)
            status = HTTPStatus.OK
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            reading, status = ascii_line(f"No reading: {exc}", 80), HTTPStatus.BAD_GATEWAY
        # ponytail: "INK " prefix is all the client needs to tell the body
        # apart from the HTTP header lines its endpoint also delivers.
        self._send_bytes(status, f"INK {reading}\r\n".encode("ascii"),
                         "text/plain; charset=us-ascii")

    def _run_tool(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 4096:
                raise ValueError
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(request, dict) or set(request) != {"op", "args"}:
                raise ValueError
            op, args = request["op"], request["args"]
            if not isinstance(op, str) or TOOL_OP.fullmatch(op) is None or not isinstance(args, dict):
                raise ValueError
            if "id" in args and (isinstance(args["id"], bool) or not isinstance(args["id"], int)):
                raise ValueError
            query = urlsplit(self.path).query
            timeout = 20.0
            if query:
                fields = dict(part.split("=", 1) for part in query.split("&") if "=" in part)
                timeout = float(fields.get("timeout", timeout))
            if not 0 < timeout <= 120:
                raise ValueError
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "invalid request"})
            return
        try:
            outcome = self.server.tools.submit(op, args, timeout)
        except RuntimeError as exc:
            self._send_json(HTTPStatus.CONFLICT, {"status": "error", "error": str(exc)})
            return
        status = {"result": HTTPStatus.OK, "error": HTTPStatus.UNPROCESSABLE_ENTITY,
                  "unknown_op": HTTPStatus.BAD_REQUEST, "timeout": HTTPStatus.GATEWAY_TIMEOUT}[
                      str(outcome["status"])]
        self._send_json(status, outcome)

    def _tool_outcome(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 4096:
                raise ValueError
            request_id, status, value = self.rfile.read(length).decode("utf-8").split("\r\n", 2)
            if not request_id or status not in ("result", "error", "unknown_op"):
                raise ValueError
            key = "result" if status == "result" else "error"
            outcome = {"request_id": request_id, "status": status, key: value}
        except (UnicodeDecodeError, ValueError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": "invalid outcome"})
            return
        if not self.server.tools.complete(outcome):
            self._send_json(HTTPStatus.CONFLICT, {"status": "error", "error": "stale outcome"})
            return
        self._send_json(HTTPStatus.OK, {"status": "ok"})

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
        if path == "/tools/poll":
            request = self.server.tools.poll()
            if request is None:
                body = b"TOOLS\r\n"
            else:
                argument = request["args"].get("id", "")
                body = (f"TOOLS {request['request_id']} {request['op']} {argument}\r\n").encode("ascii")
            self._send_bytes(HTTPStatus.OK, body, "text/plain; charset=us-ascii")
            return
        if path.endswith(".pkg") and "/" not in path[1:]:
            # ponytail: the configured package answers to its own name and to
            # the old one, so a loader on the device that still has
            # "harness-client.pkg" typed into it keeps working after the Track L1
            # rename. Any other name is served from runtime/staging/hardware.
            # Name-only, no subdirs.
            source = (
                self.package_path
                if path in ("/egg-freckles.pkg", "/harness-client.pkg")
                else STAGING_DIR / path[1:]
            )
            try:
                body = source.read_bytes()
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

    def _send_json(self, status: HTTPStatus, value: dict[str, object]) -> None:
        self._send_bytes(status, json.dumps(value, separators=(",", ":")).encode("utf-8") + b"\n",
                         "application/json; charset=utf-8")

    def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)


class PublisherServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], handler: type[PublisherHandler]) -> None:
        self.tools = ToolBroker()
        super().__init__(address, handler)


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
