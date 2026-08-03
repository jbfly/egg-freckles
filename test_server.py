#!/usr/bin/env python3
"""Framing checks plus fake-backend socket round trips for server.py."""

from __future__ import annotations

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
