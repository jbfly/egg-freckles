#!/usr/bin/env python3
"""Small self-check for pkg_publisher.py."""

from __future__ import annotations

import http.client
import json
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import pkg_publisher

CLIENT_SOURCE = (Path(__file__).parent / "examples/harness-client/Main.newt").read_text()


class PublisherTest(unittest.TestCase):
    def test_codex_binary_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / "codex"
            override.write_text("#!/bin/sh\n")
            override.chmod(0o700)
            with mock.patch.dict(
                pkg_publisher.os.environ, {"NEWTON_CODEX_BIN": str(override)}, clear=True
            ):
                self.assertEqual(pkg_publisher._codex_bin(), str(override.resolve()))

            home = Path(tmp) / "home"
            local = home / ".local" / "bin" / "codex"
            with mock.patch.dict(pkg_publisher.os.environ, {}, clear=True), \
                    mock.patch.object(pkg_publisher.Path, "home", return_value=home), \
                    mock.patch.object(pkg_publisher.shutil, "which", return_value=None):
                with self.assertRaises(RuntimeError) as raised:
                    pkg_publisher._codex_bin()
            self.assertIn(str(local), str(raised.exception))
            self.assertIn("PATH", str(raised.exception))

    def test_page_package_headers_and_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "examples" / "harness-client" / "egg-freckles.pkg"
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

                    status, headers, body, _ = self.fetch(port, "/egg-freckles.pkg")
                    self.assertEqual(status, 200)
                    self.assertEqual(body, b"first package")
                    self.assertEqual(headers["Content-Length"], str(len(body)))
                    self.assertEqual(
                        headers["Content-Type"],
                        "application/x-newton-compatible-pkg",
                    )

                    package_path.write_bytes(b"second package")
                    status, headers, body, _ = self.fetch(port, "/egg-freckles.pkg")
                    self.assertEqual(status, 200)
                    self.assertEqual(body, b"second package")
                    self.assertEqual(headers["Content-Length"], str(len(body)))

                    # Track L1 renamed the package; the old path stays an alias
                    # so a loader on the device with "harness-client.pkg" still
                    # typed into it keeps working after the rename.
                    status, headers, body, _ = self.fetch(port, "/harness-client.pkg")
                    self.assertEqual(status, 200)
                    self.assertEqual(body, b"second package")

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

    def test_ink_hint_line_is_optional_and_reaches_the_prompt(self) -> None:
        """A mixed note is ONE request: S lines for the strokes, one H line for the text."""
        with tempfile.TemporaryDirectory() as tmp:
            with pkg_publisher.make_server("127.0.0.1", 0, ink_path=Path(tmp) / "ink.png") as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    mixed = b"NSI1 320 480 1\r\nM text\r\nH feed the cat\r\nS 2 10 20 20 30\r\n"
                    with mock.patch.object(pkg_publisher, "interpret",
                                           return_value="A cat.") as vision:
                        status, _, response, _ = self.fetch(port, "/ink", "POST", mixed)
                    self.assertEqual((status, response), (200, b"INK A cat.\r\n"))
                    self.assertEqual(vision.call_args.args[1:], ("feed the cat", "text"))

                    # No H line is still valid: the physical MP2000 runs an
                    # older client that has never sent one.
                    with mock.patch.object(pkg_publisher, "interpret",
                                           return_value="A line.") as vision:
                        self.fetch(port, "/ink", "POST", b"NSI1 320 480 1\r\nS 2 10 20 20 30\r\n")
                    self.assertEqual(vision.call_args.args[1:], ("", "ask"))

                    for bad in (
                        b"NSI1 320 480 1\r\nH \r\nS 2 10 20 20 30\r\n",            # empty hint
                        b"NSI1 320 480 1\r\nH " + b"x" * 201 + b"\r\nS 2 10 20 20 30\r\n",
                        b"NSI1 320 480 1\r\nH one\r\nH two\r\nS 2 10 20 20 30\r\n",  # two H lines
                        b"NSI1 320 480 1\r\nS 2 10 20 20 30\r\nH trailing\r\n",     # H after S
                        b"NSI1 320 480 1\r\nM nope\r\nS 2 10 20 20 30\r\n",       # unknown mode
                        b"NSI1 320 480 1\r\nH one\r\nM text\r\nS 2 10 20 20 30\r\n", # M after H
                    ):
                        status, _, response, _ = self.fetch(port, "/ink", "POST", bad)
                        self.assertEqual((status, response), (400, b"invalid ink\n"), bad)
                finally:
                    server.shutdown()
                    thread.join()

    def test_ink_zero_strokes_is_answered_from_the_text(self) -> None:
        """Track L2: "Send to AI" on a text-only note sends NSI1 with 0 strokes."""
        with tempfile.TemporaryDirectory() as tmp:
            ink_path = Path(tmp) / "ink.png"
            with pkg_publisher.make_server("127.0.0.1", 0, ink_path=ink_path) as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    # This is the exact shape PrepareInkPages now builds for
                    # Notes-menu Ask AI: EncodeInk([], 0, hint, 'ask, 1, 1).
                    self.assertIn(":EncodeInk([], 0, hint, mode, 1, 1);", CLIENT_SOURCE)
                    self.assertIn('StrMunger(body, 536870911, nil, "M ask\\r\\n", 0, nil)', CLIENT_SOURCE)
                    self.assertIn('StrMunger(body, 536870911, nil, "H " & hint & "\\r\\n", 0, nil);', CLIENT_SOURCE)
                    body = b"NSI1 320 480 0\r\nM ask\r\nH what is a newton\r\n"
                    with mock.patch.object(pkg_publisher, "ask_model",
                                           return_value="A 1990s PDA.") as model, \
                            mock.patch.object(pkg_publisher, "interpret") as vision:
                        status, _, response, _ = self.fetch(port, "/ink", "POST", body)
                    self.assertEqual((status, response), (200, b"INK A 1990s PDA.\r\n"))
                    self.assertEqual(model.call_args.args, ("what is a newton",))
                    # No drawing, so no vision call and no PNG written at all.
                    vision.assert_not_called()
                    self.assertFalse(ink_path.exists())

                    with mock.patch.object(pkg_publisher, "ask_model",
                                           side_effect=RuntimeError("model down")):
                        status, _, response, _ = self.fetch(port, "/ink", "POST", body)
                    self.assertEqual((status, response),
                                     (502, b"INK No reading: model down\r\n"))

                    # Convert to Text on an already-typed note is deterministic:
                    # return its usable text without spending a model call.
                    text_body = b"NSI1 320 480 0\r\nM text\r\nH exact words\r\n"
                    with mock.patch.object(pkg_publisher, "ask_model") as model, \
                            mock.patch.object(pkg_publisher, "interpret") as vision:
                        status, _, response, _ = self.fetch(port, "/ink", "POST", text_body)
                    self.assertEqual((status, response), (200, b"INK exact words\r\n"))
                    model.assert_not_called()
                    vision.assert_not_called()

                    # A zero-stroke body with no H line asks nothing.
                    status, _, response, _ = self.fetch(
                        port, "/ink", "POST", b"NSI1 320 480 0\r\n")
                    self.assertEqual((status, response), (400, b"invalid ink\n"))
                finally:
                    server.shutdown()
                    thread.join()

    def test_ink_parts_are_ordered_rendered_separately_and_concatenated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ink_path = Path(tmp) / "ink.png"
            with pkg_publisher.make_server("127.0.0.1", 0, ink_path=ink_path) as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    pages = [
                        (f"NSI1 320 480 1\r\nM text\r\nP {index:02d} 04\r\n"
                         f"S 2 {index * 10} 20 20 30\r\n").encode()
                        for index in range(1, 5)
                    ]
                    readings = ["FIRST", "SECOND", "THIRD", "FOURTH"]
                    with mock.patch.object(pkg_publisher, "interpret",
                                           side_effect=readings) as vision:
                        for index, page in enumerate(pages, 1):
                            status, _, response, _ = self.fetch(port, "/ink", "POST", page)
                            expected = (f"INKP {index:02d} 04\r\n".encode() if index < 4
                                        else b"INK FIRST SECOND THIRD FOURTH\r\n")
                            self.assertEqual((status, response), (200, expected))
                    self.assertEqual(
                        [call.args[0].name for call in vision.call_args_list],
                        [f"ink-part-{index:02d}.png" for index in range(1, 5)],
                    )
                    for index in range(1, 5):
                        self.assertTrue((Path(tmp) / f"ink-part-{index:02d}.png").exists())
                    self.assertEqual(server.ink_parts, {})

                    # A missing first part is rejected before any model call.
                    with mock.patch.object(pkg_publisher, "interpret") as vision:
                        status, _, response, _ = self.fetch(port, "/ink", "POST", pages[1])
                    self.assertEqual((status, response), (400, b"invalid ink part\n"))
                    vision.assert_not_called()
                finally:
                    server.shutdown()
                    thread.join()

    def test_ink_part_ack_does_not_wait_for_interpretation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with pkg_publisher.make_server(
                "127.0.0.1", 0, ink_path=Path(tmp) / "ink.png"
            ) as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                started, release = threading.Event(), threading.Event()

                def vision(path, _hint, _mode):
                    if path.name.endswith("01.png"):
                        started.set()
                        self.assertTrue(release.wait(2))
                    return path.stem[-2:]

                try:
                    page = "NSI1 320 480 1\r\nP {} 02\r\nS 2 10 20 20 30\r\n"
                    with mock.patch.object(pkg_publisher, "interpret", side_effect=vision):
                        status, _, response, _ = self.fetch(
                            port, "/ink", "POST", page.format("01").encode()
                        )
                        self.assertTrue(started.wait(1))
                        self.assertEqual((status, response), (200, b"INKP 01 02\r\n"))
                        release.set()
                        status, _, response, _ = self.fetch(
                            port, "/ink", "POST", page.format("02").encode()
                        )
                    self.assertEqual((status, response), (200, b"INK 01 02\r\n"))
                finally:
                    release.set()
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

    @mock.patch.object(pkg_publisher, "_codex_bin", return_value="/opt/codex")
    def test_interpret_call_boundary(self, _codex) -> None:
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
        self.assertEqual(argv[:2], ["/opt/codex", "exec"])
        self.assertEqual(argv[-4:], ["-i", "/tmp/ink.png", "--", pkg_publisher.ASK_INK_PROMPT])
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

        # Each mode selects its own prompt; H remains context in the same argv slot.
        with mock.patch.object(subprocess, "run", return_value=done) as run:
            pkg_publisher.interpret(Path("/tmp/ink.png"), "feed the cat", "text")
        self.assertEqual(run.call_args.args[0][-1],
                         pkg_publisher.TEXT_INK_PROMPT
                         + pkg_publisher.INK_HINT_PROMPT + "feed the cat")

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

    def test_tools_persistent_heartbeat(self) -> None:
        with pkg_publisher.make_server("127.0.0.1", 0) as server:
            server.tools.heartbeat_seconds = 0.01
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            newton = socket.create_connection(server.server_address)
            stream = newton.makefile("rb")
            try:
                newton.sendall(b"POLL\r\n")
                self.assertEqual(stream.readline(), b"TOOLS 0 ping \r\n")
                newton.sendall(b"0\r\nresult\r\npong\r\nPOLL\r\n")
            finally:
                newton.close()
                server.shutdown()
                thread.join()

    def test_tools_persistent_socket_reused(self) -> None:
        with pkg_publisher.make_server("127.0.0.1", 0) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            newton = socket.create_connection(("127.0.0.1", port))
            stream = newton.makefile("rb")
            try:
                newton.sendall(b"POLL\r\n")
                for expected_id, value in (("1", "pong"), ("2", "line\\nvalue")):
                    observed = []
                    caller = threading.Thread(target=lambda: observed.append(self.fetch(
                        port, "/tools?timeout=2", "POST",
                        b'{"op":"ping","args":{}}')))
                    caller.start()
                    fields = stream.readline().decode().split()
                    self.assertEqual(fields[:3], ["TOOLS", expected_id, "ping"])
                    newton.sendall(
                        f"{expected_id}\r\nresult\r\n{value}\r\nPOLL\r\n".encode())
                    caller.join()
                    self.assertEqual(observed[0][0], 200)
                    expected = value.replace("\\n", "\n")
                    self.assertEqual(json.loads(observed[0][2])["result"], expected)
            finally:
                newton.close()
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
