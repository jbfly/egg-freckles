#!/usr/bin/env python3
"""Disposable persistent Newton tools spike; never replaces raw_pkg_server.py."""

from __future__ import annotations

import argparse
import json
import re
import socket
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

TOOL_OP = re.compile(r"[A-Za-z0-9_]+\Z")


def unescape(value: str) -> str:
    out, i = [], 0
    escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"'}
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value) and value[i + 1] in escapes:
            i += 1
            out.append(escapes[value[i]])
        else:
            out.append(value[i])
        i += 1
    return "".join(out)


class PersistentTools:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.connection: socket.socket | None = None
        self.connected_at: float | None = None
        self.next_id = 1
        self.call_lock = threading.Lock()
        self.pending: tuple[str, str] | None = None
        self.response: tuple[str, str, str] | None = None

    def attach(self, connection: socket.socket) -> None:
        connection.settimeout(None)
        with self.condition:
            if self.connection:
                self.connection.close()
            self.connection = connection
            self.connected_at = time.monotonic()
            self.response = None
            self.condition.notify_all()
        threading.Thread(target=self._serve, args=(connection,), daemon=True).start()

    def detach(self, connection: socket.socket) -> None:
        with self.condition:
            if self.connection is connection:
                self.connection = None
                self.connected_at = None
                self.pending = None
                self.condition.notify_all()
        connection.close()

    @staticmethod
    def _line(stream) -> str:
        line = stream.readline(4097)
        if not line or len(line) > 4096 or not line.endswith(b"\n"):
            raise ConnectionError("persistent Newton connection closed mid-response")
        return line.rstrip(b"\r\n").decode("utf-8")

    def _serve(self, connection: socket.socket) -> None:
        stream = connection.makefile("rb")
        try:
            while self._line(stream) == "POLL":
                with self.condition:
                    self.condition.wait_for(
                        lambda: self.connection is not connection or self.pending is not None
                    )
                    if self.connection is not connection:
                        return
                    request_id, command = self.pending
                connection.sendall(command.encode("ascii"))
                returned_id, status, value = (self._line(stream) for _ in range(3))
                with self.condition:
                    self.pending = None
                    self.response = (returned_id, status, value)
                    self.condition.notify_all()
        except (ConnectionError, OSError, UnicodeError):
            pass
        finally:
            stream.close()
            self.detach(connection)

    def submit(self, op: str, args: dict[str, object], timeout: float) -> dict[str, object]:
        argument = ""
        if op == "get_note":
            note_id = args.get("id")
            if isinstance(note_id, bool) or not isinstance(note_id, int):
                raise ValueError("get_note args.id must be an integer")
            argument = str(note_id)
        deadline = time.monotonic() + timeout
        with self.call_lock:
            with self.condition:
                if not self.condition.wait_for(lambda: self.connection is not None,
                                               max(0, deadline - time.monotonic())):
                    raise TimeoutError("no persistent Newton connection")
                request_id = str(self.next_id)
                self.next_id += 1
                self.response = None
                self.pending = (request_id, f"TOOLS {request_id} {op} {argument}\r\n")
                started = time.monotonic()
                self.condition.notify_all()
                if not self.condition.wait_for(
                    lambda: self.connection is None or self.response is not None,
                    max(0, deadline - time.monotonic()),
                ):
                    if self.pending and self.pending[0] == request_id:
                        self.pending = None
                    raise TimeoutError("Newton did not answer the long poll")
                if self.response is None:
                    raise ConnectionError("persistent Newton connection closed")
                returned_id, status, value = self.response
            if returned_id != request_id or status not in {"result", "error", "unknown_op"}:
                raise ConnectionError("invalid persistent Newton response")
            key = "result" if status == "result" else "error"
            return {"request_id": request_id, "status": status, key: unescape(value),
                    "latency_ms": round((time.monotonic() - started) * 1000, 3)}


class NewtonListener(threading.Thread):
    def __init__(self, tools: PersistentTools, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.tools, self.host, self.port = tools, host, port
        self.listener: socket.socket | None = None

    def run(self) -> None:
        with socket.create_server((self.host, self.port)) as listener:
            self.listener = listener
            print(f"Newton listener {self.host}:{self.port}", flush=True)
            while True:
                connection, address = listener.accept()
                print(f"Newton connected {address[0]}:{address[1]}", flush=True)
                self.tools.attach(connection)


class ControlHandler(BaseHTTPRequestHandler):
    server_version = "persistent-newton-tools/1"

    def log_message(self, format: str, *args: object) -> None:
        print(f"control {self.address_string()} {format % args}", flush=True)

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlsplit(self.path).path != "/health":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        tools = self.server.tools  # type: ignore[attr-defined]
        self.send_json(HTTPStatus.OK, {"connected": tools.connection is not None})

    def do_POST(self) -> None:
        split = urlsplit(self.path)
        if split.path != "/tools":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 4096:
                raise ValueError("invalid request length")
            payload = json.loads(self.rfile.read(length))
            op, args = payload["op"], payload.get("args", {})
            if not isinstance(op, str) or not TOOL_OP.fullmatch(op) or not isinstance(args, dict):
                raise ValueError("invalid tool request")
            timeout = float(parse_qs(split.query).get("timeout", ["20"])[0])
            if not 0 < timeout <= 120:
                raise ValueError("timeout must be between 0 and 120 seconds")
            outcome = self.server.tools.submit(op, args, timeout)  # type: ignore[attr-defined]
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(exc)})
            return
        except TimeoutError as exc:
            self.send_json(HTTPStatus.GATEWAY_TIMEOUT, {"status": "timeout", "error": str(exc)})
            return
        except ConnectionError as exc:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "error", "error": str(exc)})
            return
        status = {"result": HTTPStatus.OK, "error": HTTPStatus.UNPROCESSABLE_ENTITY,
                  "unknown_op": HTTPStatus.BAD_REQUEST}[str(outcome["status"])]
        self.send_json(status, outcome)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--newton-host", default="10.42.0.1")
    parser.add_argument("--newton-port", type=int, default=18082)
    parser.add_argument("--control-host", default="127.0.0.1")
    parser.add_argument("--control-port", type=int, default=18083)
    args = parser.parse_args()
    tools = PersistentTools()
    NewtonListener(tools, args.newton_host, args.newton_port).start()
    server = ThreadingHTTPServer((args.control_host, args.control_port), ControlHandler)
    server.tools = tools  # type: ignore[attr-defined]
    print(f"Control listener http://{args.control_host}:{args.control_port}/tools", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
