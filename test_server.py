#!/usr/bin/env python3
"""Self-check: start server.py with the fake backend, do a socket roundtrip,
assert a wrapped CRLF 7-bit ASCII reply (and IAC stripping + state save)."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
PORT = 16801


def read_until(sock: socket.socket, marker: bytes, timeout: float = 15) -> bytes:
    sock.settimeout(timeout)
    data = b""
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def main() -> None:
    env = dict(os.environ, NEWTON_FAKE_BACKEND="1", NEWTON_PORT=str(PORT))
    with tempfile.TemporaryDirectory() as tmp:
        env["NEWTON_STATE_DIR"] = tmp
        proc = subprocess.Popen(
            [sys.executable, str(BASE / "server.py")], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            sock = None
            for _ in range(50):
                try:
                    sock = socket.create_connection(("127.0.0.1", PORT), timeout=1)
                    break
                except OSError:
                    time.sleep(0.1)
            if sock is None:
                raise SystemExit("FAIL: server did not start")
            with sock:
                greeting = read_until(sock, b"N> ")
                assert b"newton-harness ready" in greeting, greeting

                # leading IAC WILL ECHO must be stripped from the line
                sock.sendall(b"\xff\xfb\x01hello agent\r\n")
                reply = read_until(sock, b"N> ")
                body = reply[:-3]
                assert all(b < 128 for b in body), reply
                assert b"\r\n" in body, reply
                assert b"FAKE REPLY TO: hello agent" in body, reply
                for line in body.split(b"\r\n"):
                    assert len(line) <= 45, line

                state_file = Path(tmp) / "session.json"
                history = json.loads(state_file.read_text())["history"]
                assert history[0]["content"] == "hello agent", history
                assert history[1]["role"] == "assistant", history

                sock.sendall(b"/new\r\n")
                reply = read_until(sock, b"N> ")
                assert b"New session" in reply, reply
                history = json.loads(state_file.read_text())["history"]
                assert history == [], history
        finally:
            proc.terminate()
            proc.wait(timeout=5)
    print("test_server: PASS")


if __name__ == "__main__":
    main()
