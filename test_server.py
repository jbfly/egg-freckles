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
