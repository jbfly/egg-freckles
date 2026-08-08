#!/usr/bin/env python3
"""Framing checks plus fake-backend socket round trips for server.py."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import server

BASE = Path(__file__).resolve().parent


def socket_line(sock: socket.socket, timeout: float = 5) -> bytes:
    sock.settimeout(timeout)
    data = bytearray()
    while not data.endswith(b"\n"):
        byte = sock.recv(1)
        if not byte:
            break
        data += byte
    return bytes(data)


def read_until(sock: socket.socket, marker: bytes, timeout: float = 15) -> bytes:
    sock.settimeout(timeout)
    data = b""
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


class FrameTest(unittest.TestCase):
    def test_sum8_frame_round_trip(self) -> None:
        encoded = server.frame_line(7, "MSG", "hello")
        self.assertLessEqual(len(encoded), 240)
        self.assertEqual(server.parse_frame(encoded), (7, "MSG", "hello"))

    def test_bad_checksum_is_rejected(self) -> None:
        encoded = server.frame_line(7, "MSG", "hello")[:-4] + b"00\r\n"
        with self.assertRaisesRegex(server.FrameError, "CHECKSUM"):
            server.parse_frame(encoded)

    def test_oversized_frame_is_rejected(self) -> None:
        with self.assertRaisesRegex(server.FrameError, "LENGTH"):
            server.frame_line(0, "MSG", "x" * 240)

    def test_part_payload_grammar(self) -> None:
        self.assertEqual(server.parse_part("01 03 hello there"), (1, 3, "hello there"))
        self.assertEqual(server.parse_part("02 02"), (2, 2, ""))
        self.assertEqual(server.parse_part("02 02 "), (2, 2, ""))
        for bad in ("1 3 x", "00 03 x", "04 03 x", "01 x", "", "01 03x"):
            self.assertIsNone(server.parse_part(bad), bad)

    def test_a_full_part_frame_fits_the_wire_limit(self) -> None:
        encoded = server.frame_line(99, "MSGP", "99 99 " + "x" * 220)
        self.assertEqual(len(encoded), server.MAX_FRAME)


def test_agent_prompt_is_read_fresh(monkeypatch, tmp_path):
    prompt = tmp_path / "agent_prompt.txt"
    monkeypatch.setattr(server, "PROMPT_FILE", prompt)
    prompt.write_text("first", encoding="utf-8")
    assert server.load_agent_prompt() == "first"
    prompt.write_text("second", encoding="utf-8")
    assert server.load_agent_prompt() == "second"


def test_codex_backend_relays_tool_progress_and_failures(monkeypatch, tmp_path):
    events = [
        b'{"type":"thread.started","thread_id":"t1"}\n',
        b'{"type":"item.started","item":{"type":"mcp_tool_call",'
        b'"server":"newton","tool":"build_pkg"}}\n',
        b'{"type":"item.completed","item":{"type":"mcp_tool_call",'
        b'"server":"newton","tool":"build_pkg","status":"failed",'
        b'"result":{"content":[{"type":"text","text":"undefined CellButton\\nmore"}]}}}\n',
        b'{"type":"item.started","item":{"type":"mcp_tool_call",'
        b'"server":"newton","tool":"build_pkg"}}\n',
        b'{"type":"item.started","item":{"type":"mcp_tool_call",'
        b'"server":"newton","tool":"hardware_install"}}\n',
        b'{"type":"item.completed","item":{"type":"agent_message",'
        b'"text":"{\\"visible\\":\\"Package installed\\"}"}}\n',
    ]

    class Stdout:
        async def readline(self):
            return events.pop(0) if events else b""

    class Process:
        stdout = Stdout()
        returncode = 0

        async def wait(self):
            return 0

        def kill(self):  # pragma: no cover - timeout path
            raise AssertionError("backend must not time out")

    async def fake_subprocess(*args, **kwargs):
        return Process()

    progress = []

    async def mark_progress(message):
        progress.append(message)

    event_log = tmp_path / "mcp.jsonl"
    monkeypatch.setattr(server, "MCP_EVENT_LOG", str(event_log))
    monkeypatch.setattr(server.asyncio, "create_subprocess_exec", fake_subprocess)
    reply = asyncio.run(server.CodexBackend(server.Chat(tmp_path)).chat(
        "install it", mark_progress))

    assert progress == [
        "Building package (attempt 1/5)",
        "Building package failed; fixing: undefined CellButton",
        "Building package (attempt 2/5)",
        "Package ready. Open Dock, choose connect via TCP/IP, then tap Connect.",
    ]
    assert reply == "Package installed"
    recorded = [json.loads(line) for line in event_log.read_text().splitlines()]
    assert [(event["type"], event["tool"]) for event in recorded] == [
        ("item.started", "build_pkg"),
        ("item.completed", "build_pkg"),
        ("item.started", "build_pkg"),
        ("item.started", "hardware_install"),
    ]


def test_native_mode_streams_progress_without_polluting_final_text(monkeypatch, tmp_path):
    sent = []

    async def fake_send_frame(reader, writer, state, op, payload=""):
        sent.append((op, payload))
        state["tx_seq"] = (state["tx_seq"] + 1) % 100

    class Backend:
        async def chat(self, user_text, progress=None):
            await progress("Writing source")
            return "final answer"

    class Writer:
        def write(self, data):
            pass

        async def drain(self):
            pass

    async def exercise():
        reader = asyncio.StreamReader()
        reader.feed_data(server.frame_line(0, "HELLO", "NEWTON1 test"))
        reader.feed_data(server.frame_line(1, "MSG", "build it"))
        reader.feed_eof()
        await server.native_mode(reader, Writer(), server.Chat(tmp_path), Backend())

    monkeypatch.setattr(server, "send_frame", fake_send_frame)
    asyncio.run(exercise())
    assert sent == [
        ("STAT", "READY"),
        ("STAT", "THINKING"),
        ("STAT", "PROGRESS Writing source"),
        ("TEXT", "final answer"),
        ("PROMPT", ""),
    ]


def test_codex_backend_reads_event_lines_larger_than_asyncio_default(monkeypatch, tmp_path):
    async def fake_subprocess(*args, **kwargs):
        reader = asyncio.StreamReader(limit=kwargs["limit"])
        reader.feed_data(
            b'{"type":"thread.started","thread_id":"t1","padding":"'
            + b"x" * (2**16) + b'"}\n'
            + b'{"type":"item.completed","item":{"type":"agent_message",'
              b'"text":"{\\"visible\\":\\"done\\"}"}}\n')
        reader.feed_eof()

        class Process:
            stdout = reader
            returncode = 0

            async def wait(self):
                return 0

        return Process()

    monkeypatch.setattr(server.asyncio, "create_subprocess_exec", fake_subprocess)
    assert asyncio.run(server.CodexBackend(server.Chat(tmp_path)).chat("large app")) == "done"


class RegistryTest(unittest.TestCase):
    """Track F4: the sessions registry, offline."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_an_old_single_session_file_becomes_session_one(self) -> None:
        (self.dir / "session.json").write_text(json.dumps({
            "version": 1, "thread_id": "thread-from-before",
            "created_at": "2026-08-01T10:00:00+00:00",
            "updated_at": "2026-08-01T10:05:00+00:00",
            "history": [{"role": "user", "content": "what is a Newton"},
                        {"role": "assistant", "content": "a 1997 PDA"},
                        {"role": "user", "content": "thanks"}]}))
        chat = server.Chat(self.dir)
        entry = chat.entry
        self.assertEqual(len(chat.sessions), 1)
        self.assertEqual(entry["file"], "session.json")
        self.assertEqual(entry["thread_id"], "thread-from-before")
        self.assertEqual(entry["turns"], 2)
        self.assertEqual(entry["name"], "what is a Newton")
        self.assertEqual(entry["created_at"], "2026-08-01T10:00:00+00:00")
        # The transcript itself is left where it was.
        self.assertEqual(len(chat.session.data["history"]), 3)

    def test_a_missing_or_corrupt_registry_starts_one_empty_session(self) -> None:
        (self.dir / "sessions.json").write_text("{not json")
        chat = server.Chat(self.dir)
        self.assertEqual(len(chat.sessions), 1)
        self.assertEqual(chat.entry["turns"], 0)
        self.assertIsNone(chat.thread_id)

    def test_a_registry_round_trips_through_the_file(self) -> None:
        chat = server.Chat(self.dir)
        chat.command("/model 2")
        chat.command("/new second")
        chat.record("user", "hi")
        chat.save()
        again = server.Chat(self.dir)
        self.assertEqual(again.index, 2)
        self.assertEqual(again.entry["name"], "second")
        self.assertEqual(again.sessions[0]["model"], server.MODELS[1])
        self.assertEqual(again.entry["file"], "session-2.json")

    def test_bare_new_on_an_untouched_session_does_not_add_a_row(self) -> None:
        chat = server.Chat(self.dir)
        self.assertEqual(chat.command("/new"), "New session.")
        self.assertEqual(len(chat.sessions), 1)
        chat.record("user", "now this session has a long first turn")
        self.assertEqual(chat.command("/new"), "New session.")
        self.assertEqual(len(chat.sessions), 2)
        # The auto name comes from the first prompt, clipped to the screen.
        self.assertEqual(chat.sessions[0]["name"], "now this session h")

    def test_a_session_name_never_carries_a_star(self) -> None:
        chat = server.Chat(self.dir)
        self.assertEqual(chat.command("/new a*b c"), "New session 2: ab c")
        self.assertNotIn("*", chat.command("/sessions"))

    def test_pick_takes_a_number_a_name_or_a_prefix(self) -> None:
        choices = ["low", "medium", "high"]
        self.assertEqual(server.pick("2", choices), "medium")
        self.assertEqual(server.pick("HIGH", choices), "high")
        self.assertEqual(server.pick("med", choices), "medium")
        for bad in ("0", "4", "", "x", "-1"):
            self.assertIsNone(server.pick(bad, choices), bad)

    def test_the_model_list_is_overridable_by_env(self) -> None:
        out = subprocess.run(
            [sys.executable, "-c", "import server; print(','.join(server.MODELS))"],
            cwd=str(BASE), capture_output=True, text=True,
            env=dict(os.environ, NEWTON_MODELS="alpha-1, beta-2")).stdout.strip()
        self.assertEqual(out, "alpha-1,beta-2")


class ServerSocketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        env = dict(os.environ, NEWTON_FAKE_BACKEND="1",
                   NEWTON_PORT=str(self.port), NEWTON_STATE_DIR=self.tmp.name)
        self.proc = subprocess.Popen(
            [sys.executable, str(BASE / "server.py")], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                sock = socket.create_connection(("127.0.0.1", self.port), timeout=1)
                sock.close()
                break
            except OSError:
                time.sleep(0.05)
        else:
            self.fail("server did not start")

    def tearDown(self) -> None:
        self.proc.terminate()
        self.proc.wait(timeout=5)
        self.tmp.cleanup()

    @property
    def history(self) -> list[dict]:
        path = Path(self.tmp.name) / "session.json"
        return json.loads(path.read_text())["history"] if path.exists() else []

    @property
    def registry(self) -> dict:
        path = Path(self.tmp.name) / "sessions.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def native_socket(self) -> socket.socket:
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        sock.sendall(server.NATIVE_HANDSHAKE + b"\r\n")
        sock.sendall(server.frame_line(0, "HELLO", "NEWTON1 test"))
        self.assertEqual(socket_line(sock), b"ACK 00\r\n")
        seq, op, payload, _ = self.frame(sock)
        self.assertEqual((op, payload), ("STAT", "READY"))
        sock.sendall(f"ACK {seq:02d}\r\n".encode("ascii"))
        return sock

    def frame(self, sock: socket.socket) -> tuple[int, str, str, bytes]:
        while True:
            raw = socket_line(sock)
            if raw.startswith(b":"):
                seq, op, payload = server.parse_frame(raw)
                return seq, op, payload, raw

    def finish_turn(self, sock: socket.socket) -> list[tuple[str, str]]:
        received = []
        while True:
            seq, op, payload, _ = self.frame(sock)
            received.append((op, payload))
            sock.sendall(f"ACK {seq:02d}\r\n".encode("ascii"))
            if op == "PROMPT":
                return received

    def test_valid_frame_is_accepted_and_applied(self) -> None:
        with self.native_socket() as sock:
            sock.sendall(server.frame_line(1, "MSG", "hello newton"))
            self.assertEqual(socket_line(sock), b"ACK 01\r\n")
            received = self.finish_turn(sock)
        self.assertIn(("STAT", "THINKING"), received)
        self.assertTrue(any(op == "TEXT" and "FAKE REPLY TO: hello newton" in text
                            for op, text in received))
        self.assertEqual([item["role"] for item in self.history], ["user", "assistant"])

    def test_bad_checksum_is_naked_then_identical_sequence_completes(self) -> None:
        with self.native_socket() as sock:
            good = server.frame_line(1, "MSG", "recover me")
            bad = good[:-4] + (b"00" if good[-4:-2] != b"00" else b"01") + b"\r\n"
            sock.sendall(bad)
            self.assertEqual(socket_line(sock), b"NAK 01 CHECKSUM\r\n")
            self.assertEqual(self.history, [])
            sock.sendall(good)
            self.assertEqual(socket_line(sock), b"ACK 01\r\n")
            received = self.finish_turn(sock)
        self.assertIn(("STAT", "THINKING"), received)
        self.assertTrue(any(op == "TEXT" and "FAKE REPLY TO: recover me" in text
                            for op, text in received))
        self.assertEqual([item["content"] for item in self.history if item["role"] == "user"],
                         ["recover me"])

    def test_oversized_frame_is_naked_without_applying(self) -> None:
        with self.native_socket() as sock:
            sock.sendall(b":01 MSG " + b"x" * 240 + b"*00\r\n")
            self.assertEqual(socket_line(sock), b"NAK 01 LENGTH\r\n")
        self.assertEqual(self.history, [])

    def test_duplicate_frame_is_acked_again_and_applied_once(self) -> None:
        with self.native_socket() as sock:
            msg = server.frame_line(1, "MSG", "once")
            sock.sendall(msg)
            self.assertEqual(socket_line(sock), b"ACK 01\r\n")
            seq, op, payload, _ = self.frame(sock)
            self.assertEqual((op, payload), ("STAT", "THINKING"))
            sock.sendall(msg)
            self.assertEqual(socket_line(sock), b"ACK 01\r\n")
            sock.sendall(f"ACK {seq:02d}\r\n".encode("ascii"))
            self.finish_turn(sock)
        self.assertEqual([item["content"] for item in self.history if item["role"] == "user"],
                         ["once"])

    def test_dropped_ack_retries_identical_frame_and_applies_once(self) -> None:
        with self.native_socket() as sock:
            sock.sendall(server.frame_line(1, "MSG", "retry once"))
            self.assertEqual(socket_line(sock), b"ACK 01\r\n")
            seq, op, payload, first = self.frame(sock)
            self.assertEqual((op, payload), ("STAT", "THINKING"))
            _, _, _, retry = self.frame(sock)  # deliberately withhold the first ACK
            self.assertEqual(retry, first)
            sock.sendall(f"ACK {seq:02d}\r\n".encode("ascii"))
            self.finish_turn(sock)
        self.assertEqual([item["content"] for item in self.history if item["role"] == "user"],
                         ["retry once"])

    def test_dropped_ack_stops_after_three_identical_retries(self) -> None:
        with self.native_socket() as sock:
            sock.sendall(server.frame_line(1, "MSG", "retry limit"))
            self.assertEqual(socket_line(sock), b"ACK 01\r\n")
            attempts = [self.frame(sock)[3] for _ in range(server.FRAME_RETRIES + 1)]
            self.assertEqual(attempts, [attempts[0]] * 4)
            self.assertEqual(socket_line(sock, server.FRAME_TIMEOUT + 1), b"")

    def test_reserved_new_message_resets_session(self) -> None:
        with self.native_socket() as sock:
            sock.sendall(server.frame_line(1, "MSG", "/new"))
            self.assertEqual(socket_line(sock), b"ACK 01\r\n")
            received = self.finish_turn(sock)
        self.assertIn(("TEXT", "New session."), received)
        self.assertEqual(self.history, [])

    def say(self, sock: socket.socket, seq: int, text: str) -> list[str]:
        """Send one MSG and return the TEXT payloads of the completed turn."""
        sock.sendall(server.frame_line(seq, "MSG", text))
        self.assertEqual(socket_line(sock), f"ACK {seq:02d}\r\n".encode())
        return [payload for op, payload in self.finish_turn(sock) if op == "TEXT"]

    def test_help_lists_every_command(self) -> None:
        with self.native_socket() as sock:
            lines = self.say(sock, 1, "/help")
        for name in ("/help", "/status", "/model", "/effort", "/sessions",
                     "/new", "/resume"):
            self.assertTrue(any(line.startswith(name) for line in lines), name)
        self.assertTrue(all(len(line) <= 45 for line in lines), lines)

    def test_status_reports_the_current_session(self) -> None:
        with self.native_socket() as sock:
            lines = self.say(sock, 1, "/status")
        self.assertEqual(lines[0].split(":")[0], "Session 1/1")
        self.assertIn("Model: codex default", lines)
        self.assertIn("Effort: codex default", lines)
        self.assertIn("Turns: 0", lines)

    def test_model_by_number_is_used_and_persisted(self) -> None:
        wanted = server.MODELS[1]
        with self.native_socket() as sock:
            self.assertEqual(self.say(sock, 1, "/model"),
                             ["Model: codex default"]
                             + [f"{i}. {name}" for i, name
                                in enumerate(server.MODELS, 1)]
                             + ["/model <n> to set"])
            self.assertEqual(self.say(sock, 2, "/model 2"), [f"Model: {wanted}"])
            self.assertEqual(self.say(sock, 3, "/effort low"), ["Effort: low"])
            reply = " ".join(self.say(sock, 4, "ping"))
        # The fake backend echoes what the turn was actually handed.
        self.assertIn(f"[m={wanted} e=low]", reply)
        entry = self.registry["sessions"][0]
        self.assertEqual((entry["model"], entry["effort"]), (wanted, "low"))

    def test_a_bad_model_or_effort_is_refused(self) -> None:
        with self.native_socket() as sock:
            self.assertEqual(self.say(sock, 1, "/model 99"),
                             ["No model '99'. /model to list."])
            self.assertEqual(self.say(sock, 2, "/effort turbo"),
                             ["No effort 'turbo'. /effort to list."])
        self.assertIsNone(self.registry["sessions"][0]["model"])

    def test_new_named_keeps_the_old_session_in_the_registry(self) -> None:
        with self.native_socket() as sock:
            self.say(sock, 1, "remember me")
            self.assertEqual(self.say(sock, 2, "/new test"),
                             ["New session 2: test"])
            listing = self.say(sock, 3, "/sessions")
        names = [entry["name"] for entry in self.registry["sessions"]]
        self.assertEqual(names, ["remember me", "test"])
        self.assertEqual(self.registry["sessions"][0]["thread_id"], "fake-thread-1")
        self.assertEqual(self.registry["current"], 1)
        self.assertEqual(len(listing), 2)
        self.assertTrue(any(line.startswith("2.>test 0t") for line in listing), listing)
        # No reply may contain `*`: the client truncates the line at the first
        # one (Main.newt:432, found live in the Track F4 round).
        self.assertNotIn("*", "".join(listing))

    def test_resume_switches_the_codex_thread(self) -> None:
        with self.native_socket() as sock:
            self.say(sock, 1, "first")
            self.say(sock, 2, "/new second")
            self.say(sock, 3, "hello again")
            threads = [entry["thread_id"] for entry in self.registry["sessions"]]
            self.assertEqual(threads, ["fake-thread-1", "fake-thread-2"])
            self.assertEqual(self.say(sock, 4, "/resume 1"),
                             ["Session 1: first 1t model default"])
            self.say(sock, 5, "back on one")
        entries = self.registry["sessions"]
        self.assertEqual(self.registry["current"], 0)
        self.assertEqual(entries[0]["thread_id"], "fake-thread-1")
        self.assertEqual((entries[0]["turns"], entries[1]["turns"]), (2, 1))
        self.assertEqual(
            [item["content"] for item in self.history if item["role"] == "user"],
            ["first", "back on one"])

    def test_unknown_command_is_refused_but_a_slash_prompt_is_not(self) -> None:
        with self.native_socket() as sock:
            self.assertEqual(self.say(sock, 1, "/nope"),
                             ["Unknown command /nope. /help for the list."])
            reply = " ".join(self.say(sock, 2, "/ 2+2"))
        self.assertIn("FAKE REPLY TO: / 2+2", reply)
        self.assertEqual(
            [item["content"] for item in self.history if item["role"] == "user"],
            ["/ 2+2"])

    def test_the_registry_survives_a_reconnect(self) -> None:
        with self.native_socket() as sock:
            self.say(sock, 1, "/model 1")
            self.say(sock, 2, "/new later")
        with self.native_socket() as sock:
            lines = self.say(sock, 1, "/status")
            self.assertEqual(lines[0], "Session 2/2: later")
            self.assertIn("Model: codex default", lines)   # per session, not global
            self.assertEqual(self.say(sock, 2, "/resume 1")[0].split(" model ")[1],
                             server.MODELS[0])

    def test_the_pt100_path_answers_the_same_commands(self) -> None:
        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as sock:
            read_until(sock, b"N> ")
            sock.sendall(b"/model 2\r\n")
            self.assertIn(server.MODELS[1].encode(), read_until(sock, b"N> "))
            sock.sendall(b"/status\r\n")
            self.assertIn(b"Session 1/1", read_until(sock, b"N> "))

    def part(self, seq: int, k: int, n: int, chunk: str) -> bytes:
        return server.frame_line(seq, "MSGP", f"{k:02d} {n:02d} {chunk}")

    def test_message_parts_assemble_into_one_prompt(self) -> None:
        chunks = ["a" * 220, "b" * 220, "tail"]
        with self.native_socket() as sock:
            for index, chunk in enumerate(chunks):
                sock.sendall(self.part(index + 1, index + 1, len(chunks), chunk))
                self.assertEqual(socket_line(sock), f"ACK {index + 1:02d}\r\n".encode())
            received = self.finish_turn(sock)
        self.assertIn(("STAT", "THINKING"), received)
        reply = "".join(text for op, text in received if op == "TEXT")
        self.assertIn("FAKE REPLY TO: " + "a" * 220, reply)
        self.assertEqual([item["content"] for item in self.history if item["role"] == "user"],
                         ["".join(chunks)])

    def test_out_of_order_part_is_naked_and_nothing_is_applied(self) -> None:
        with self.native_socket() as sock:
            sock.sendall(self.part(1, 1, 3, "first "))
            self.assertEqual(socket_line(sock), b"ACK 01\r\n")
            sock.sendall(self.part(2, 3, 3, "third"))
            self.assertEqual(socket_line(sock), b"NAK 02 PART\r\n")
            sock.sendall(server.frame_line(3, "MSGP", "2 3 bad digits"))
            self.assertEqual(socket_line(sock), b"NAK 03 PART\r\n")
            # The buffer survives the rejects: the real part 2 still completes.
            sock.sendall(self.part(4, 2, 3, "second "))
            self.assertEqual(socket_line(sock), b"ACK 04\r\n")
            sock.sendall(self.part(5, 3, 3, "third"))
            self.assertEqual(socket_line(sock), b"ACK 05\r\n")
            self.finish_turn(sock)
        self.assertEqual([item["content"] for item in self.history if item["role"] == "user"],
                         ["first second third"])

    def test_plain_message_resets_a_partial_part_buffer(self) -> None:
        with self.native_socket() as sock:
            sock.sendall(self.part(1, 1, 2, "dropped half "))
            self.assertEqual(socket_line(sock), b"ACK 01\r\n")
            sock.sendall(server.frame_line(2, "MSG", "plain wins"))
            self.assertEqual(socket_line(sock), b"ACK 02\r\n")
            self.finish_turn(sock)
            # Part 2 of the abandoned prompt is now out of order.
            sock.sendall(self.part(3, 2, 2, "orphan"))
            self.assertEqual(socket_line(sock), b"NAK 03 PART\r\n")
        self.assertEqual([item["content"] for item in self.history if item["role"] == "user"],
                         ["plain wins"])

    def test_assembled_prompt_over_the_cap_is_refused(self) -> None:
        chunk = "z" * 220
        parts = server.MAX_PROMPT // len(chunk) + 1
        with self.native_socket() as sock:
            for index in range(parts):
                seq = index + 1
                sock.sendall(self.part(seq, seq, 99, chunk))
                self.assertEqual(socket_line(sock), f"ACK {seq:02d}\r\n".encode())
            received = self.finish_turn(sock)
        self.assertEqual(received[0],
                         ("STAT", f"ERROR prompt over {server.MAX_PROMPT} bytes"))
        self.assertEqual(self.history, [])

    def test_parts_before_hello_are_refused(self) -> None:
        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as sock:
            sock.sendall(server.NATIVE_HANDSHAKE + b"\r\n")
            sock.sendall(self.part(1, 1, 2, "no hello yet"))
            self.assertEqual(socket_line(sock), b"NAK 01 OP\r\n")

    def test_pt100_session_bytes_are_unchanged(self) -> None:
        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as sock:
            greeting = read_until(sock, b"N> ")
            self.assertEqual(greeting, server.wire_text(server.GREETING) + b"\r\nN> ")
            sock.sendall(b"\xff\xfb\x01hello agent\r\n")
            reply = read_until(sock, b"N> ")
            self.assertIn(b"FAKE REPLY TO: hello agent", reply)
            self.assertTrue(all(byte < 128 for byte in reply))
            for line in reply[:-3].split(b"\r\n"):
                self.assertLessEqual(len(line), 45)


if __name__ == "__main__":
    unittest.main(verbosity=2)
