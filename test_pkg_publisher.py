#!/usr/bin/env python3
"""Small self-check for pkg_publisher.py."""

from __future__ import annotations

import http.client
import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import pkg_publisher


class PublisherTest(unittest.TestCase):
    def test_page_package_headers_and_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "examples" / "harness-client" / "harness-client.pkg"
            package_path.parent.mkdir(parents=True)
            package_path.write_bytes(b"first package")

            with pkg_publisher.make_server("127.0.0.1", 0, package_path) as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    status, headers, body, version = self.fetch(port, "/")
                    self.assertEqual(status, 200)
                    self.assertEqual(version, 10)
                    self.assertEqual(body, pkg_publisher.PAGE_BODY)
                    self.assertEqual(headers["Content-Length"], str(len(body)))
                    self.assertEqual(headers["Connection"], "close")
                    self.assertIn("text/html", headers["Content-Type"])

                    status, headers, body, version = self.fetch(port, "/status")
                    self.assertEqual(status, 200)
                    self.assertEqual(version, 10)
                    self.assertEqual(body, pkg_publisher.STATUS_BODY)
                    self.assertEqual(headers["Content-Length"], str(len(body)))
                    self.assertEqual(headers["Connection"], "close")
                    self.assertEqual(headers["Content-Type"], "text/plain; charset=us-ascii")

                    status, headers, body, _ = self.fetch(port, "/harness-client.pkg")
                    self.assertEqual(status, 200)
                    self.assertEqual(body, b"first package")
                    self.assertEqual(headers["Content-Length"], str(len(body)))
                    self.assertEqual(
                        headers["Content-Type"],
                        "application/x-newton-compatible-pkg",
                    )

                    package_path.write_bytes(b"second package")
                    status, headers, body, _ = self.fetch(port, "/harness-client.pkg")
                    self.assertEqual(status, 200)
                    self.assertEqual(body, b"second package")
                    self.assertEqual(headers["Content-Length"], str(len(body)))

                    status, headers, body, _ = self.fetch(port, "/../../etc/passwd")
                    self.assertEqual(status, 404)
                    self.assertEqual(body, b"not found\n")
                    self.assertEqual(headers["Content-Length"], str(len(body)))
                finally:
                    server.shutdown()
                    thread.join()

    def test_note_validation_and_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            note_path = Path(tmp) / "note.json"
            with pkg_publisher.make_server("127.0.0.1", 0, note_path=note_path) as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    note = {"id": 42, "title": "", "modified": 123,
                            "text": "The Newton sees this note.", "truncated": False}
                    with mock.patch.object(pkg_publisher, "ask_model", return_value="It is scrambled.") as ask:
                        status, _, response, _ = self.fetch(
                            port, "/note", "POST", json.dumps(note).encode("utf-8"))
                    self.assertEqual((status, response), (200, b"NOTE It is scrambled.\r\n"))
                    ask.assert_called_once_with(note["text"])
                    self.assertEqual(json.loads(note_path.read_text()), note)
                    status, _, _, _ = self.fetch(
                        port, "/note", "POST",
                        json.dumps({**note, "text": "x" * 8193}).encode("utf-8"))
                    self.assertEqual(status, 400)
                    self.assertEqual(json.loads(note_path.read_text()), note)
                finally:
                    server.shutdown()
                    thread.join()

    def test_note_model_failure_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with pkg_publisher.make_server("127.0.0.1", 0, note_path=Path(tmp) / "note.json") as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                note = {"id": 1, "title": "", "modified": 2,
                        "text": "hello", "truncated": False}
                try:
                    with mock.patch.object(pkg_publisher, "ask_model",
                                           side_effect=RuntimeError("model down")):
                        status, _, response, _ = self.fetch(
                            port, "/note", "POST", json.dumps(note).encode())
                    self.assertEqual(status, 502)
                    self.assertEqual(response, b"NOTE No answer: model down\r\n")
                finally:
                    server.shutdown()
                    thread.join()

    def test_ink_reading_and_backend_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with pkg_publisher.make_server("127.0.0.1", 0, ink_path=Path(tmp) / "ink.png") as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                body = b"NSI1 320 480 2\r\nS 3 10 20 1 2 -1 -2\r\nS 1 30 40\r\n"
                try:
                    with mock.patch.object(pkg_publisher, "interpret", return_value="A spiral."):
                        status, headers, response, version = self.fetch(port, "/ink", "POST", body)
                    self.assertEqual((status, version, response), (200, 10, b"INK A spiral.\r\n"))
                    self.assertEqual(headers["Content-Type"], "text/plain; charset=us-ascii")

                    with mock.patch.object(pkg_publisher, "interpret",
                                           side_effect=RuntimeError("codex exited 1")):
                        status, _, response, _ = self.fetch(port, "/ink", "POST", body)
                    self.assertEqual(status, 502)
                    self.assertEqual(response, b"INK No reading: codex exited 1\r\n")
                finally:
                    server.shutdown()
                    thread.join()

    def test_ink_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ink_path = Path(tmp) / "ink.png"
            with pkg_publisher.make_server("127.0.0.1", 0, ink_path=ink_path) as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    with mock.patch.object(pkg_publisher, "interpret", return_value="x"):
                        self.fetch(port, "/ink", "POST", b"NSI1 320 480 1\r\nS 2 10 20 20 30\r\n")
                    png = ink_path.read_bytes()
                    self.assertEqual(png[:24], b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01@\x00\x00\x01\xe0")
                finally:
                    server.shutdown()
                    thread.join()

    def test_interpret_call_boundary(self) -> None:
        """The real-backend edge: argv shape, JSON pick, cleanup, failure. No tokens spent."""
        events = (
            b'{"type":"thread.started","thread_id":"t1"}\n'
            b'{"type":"item.completed","item":{"type":"reasoning","text":"ignore me"}}\n'
            b'{"type":"item.completed","item":{"type":"agent_message",'
            b'"text":"A wavy line\\nwith a  \\u2014 dash."}}\n'
            b'{"type":"turn.completed"}\n'
        )
        done = subprocess.CompletedProcess([], 0, stdout=events, stderr=b"")
        with mock.patch.object(subprocess, "run", return_value=done) as run:
            self.assertEqual(pkg_publisher.interpret(Path("/tmp/ink.png")),
                             "A wavy line with a ? dash.")
        argv = run.call_args.args[0]
        self.assertEqual(argv[:2], ["codex", "exec"])
        self.assertEqual(argv[-4:], ["-i", "/tmp/ink.png", "--", pkg_publisher.INK_PROMPT])
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

        failed = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"boom")
        with mock.patch.object(subprocess, "run", return_value=failed):
            with self.assertRaises(RuntimeError):
                pkg_publisher.interpret(Path("/tmp/ink.png"))

        with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, stdout=b'{"type":"turn.completed"}\n', stderr=b"")):
            with self.assertRaises(RuntimeError):
                pkg_publisher.interpret(Path("/tmp/ink.png"))

    def test_tools_classification_and_validation(self) -> None:
        with pkg_publisher.make_server("127.0.0.1", 0) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                for outcome, expected in (
                    ({"status": "result", "result": "pong"}, (200, "result")),
                    ({"status": "error", "error": "-48807"}, (422, "error")),
                    ({"status": "unknown_op", "error": "unknown op: nope"}, (400, "unknown_op")),
                ):
                    observed: list[tuple[int, dict[str, object]]] = []
                    caller = threading.Thread(target=lambda: observed.append((lambda response: (
                        response[0], json.loads(response[2])))(self.fetch(
                            port, "/tools?timeout=2", "POST",
                            b'{"op":"ping","args":{}}'))))
                    caller.start()
                    for _ in range(100):
                        status, _, body, _ = self.fetch(port, "/tools/poll")
                        fields = body.decode().split()
                        if len(fields) >= 3:
                            break
                        threading.Event().wait(0.01)
                    self.assertEqual((status, fields[:1]), (200, ["TOOLS"]))
                    request_id = fields[1]
                    value = outcome.get("result", outcome.get("error", ""))
                    posted = f"{request_id}\r\n{outcome['status']}\r\n{value}".encode()
                    self.assertEqual(self.fetch(
                        port, "/tools/outcome", "POST", posted)[0], 200)
                    caller.join()
                    self.assertEqual((observed[0][0], observed[0][1]["status"]), expected)
                    self.assertEqual(observed[0][1]["request_id"], request_id)

                status, _, body, _ = self.fetch(
                    port, "/tools?timeout=0.02", "POST",
                    b'{"op":"ping","args":{}}')
                self.assertEqual((status, json.loads(body)["status"]), (504, "timeout"))
                for body in (b'{"op":"bad-op","args":{}}',
                             b'{"op":"get_note","args":{"id":true}}'):
                    self.assertEqual(self.fetch(port, "/tools", "POST", body)[0], 400)
            finally:
                server.shutdown()
                thread.join()

    @staticmethod
    def fetch(
        port: int, path: str, method: str = "GET", body: bytes | None = None
    ) -> tuple[int, http.client.HTTPMessage, bytes, int]:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            conn.request(method, path, body=body)
            response = conn.getresponse()
            body = response.read()
            return response.status, response.headers, body, response.version
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
