#!/usr/bin/env python3
"""Print one injected NewtonScript result without taking a screenshot."""

import argparse
import subprocess
import time

RESULT = "/state/einstein-ns-result"
SEND = """import socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.connect('/state/einstein-control.sock')
s.sendall(sys.stdin.buffer.read()); print(s.recv(4096).decode().strip())
"""


def run(container: str, source: str, timeout: float) -> str:
    command = f"ns {source}\n".encode()
    if "\n" in source or "\r" in source or len(command) > 8193:
        raise SystemExit("source must be one line and at most 8190 UTF-8 bytes")
    queued = subprocess.run(
        ["podman", "exec", "-i", container, "python3", "-c", SEND],
        input=command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    reply = queued.stdout.decode("utf-8", "replace").strip()
    if queued.returncode or reply != "queued":
        detail = queued.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(detail or reply or "control socket returned no reply")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        read = subprocess.run(
            ["podman", "exec", container, "cat", RESULT],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        text = read.stdout.decode("mac_roman", "replace")
        lines = text.splitlines()
        if lines and (lines[0] != "Exception" or len(lines) > 1):
            return text.rstrip("\r\n")
        time.sleep(0.05)
    raise SystemExit(f"timed out after {timeout:g}s waiting for NewtonScript result")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="one-line NewtonScript source")
    parser.add_argument("--container", default="newton-scratch2_emulator_1")
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    print(run(args.container, args.source, args.timeout))


if __name__ == "__main__":
    main()
