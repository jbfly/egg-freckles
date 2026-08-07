#!/usr/bin/env python3
"""Print one injected NewtonScript result without taking a screenshot."""

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import time

DEFAULT_CONTAINER = "newton-scratch2_emulator_1"
RESULT = "/state/einstein-ns-result"
GUARD_ROOT = Path(tempfile.gettempdir()) / f"newton-harness-ns-eval-{os.getuid()}"
SEND = """import socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.connect('/state/einstein-control.sock')
s.sendall(sys.stdin.buffer.read()); print(s.recv(4096).decode().strip())
"""


def _paths(container: str) -> tuple[Path, Path]:
    key = hashlib.sha256(container.encode()).hexdigest()[:16]
    return GUARD_ROOT / f"{key}.lock", GUARD_ROOT / f"{key}.poisoned"


def _instance_token(container: str) -> str:
    inspected = subprocess.run(
        ["podman", "inspect", "--format", "{{.Id}} {{.State.StartedAt}}", container],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    token = inspected.stdout.decode("utf-8", "replace").strip()
    if inspected.returncode or not token:
        detail = inspected.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(detail or f"emulator container {container!r} is not running")
    return token


def _mark_poisoned(path: Path, token: str) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(token)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run(container: str, source: str, timeout: float) -> str:
    command = f"ns {source}\n".encode()
    if "\n" in source or "\r" in source or len(command) > 8193:
        raise SystemExit("source must be one line and at most 8190 UTF-8 bytes")

    GUARD_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path, poison_path = _paths(container)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(
                f"NewtonScript eval already in flight for {container}; wait for it to finish"
            ) from None

        token = _instance_token(container)
        if poison_path.exists():
            if poison_path.read_text() == token:
                raise SystemExit(
                    f"NewtonScript eval channel for {container} is POISONED by an eval "
                    "that did not complete; restart this isolated emulator instance before "
                    "running another eval"
                )
            poison_path.unlink()

        # ponytail: this state file also makes a killed client fail closed; a
        # successful correlated C++ channel can replace it if eval becomes load-bearing.
        _mark_poisoned(poison_path, token)
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
                poison_path.unlink()
                return text.rstrip("\r\n")
            time.sleep(0.05)
        raise SystemExit(
            f"timed out after {timeout:g}s waiting for NewtonScript result; "
            f"channel for {container} is now POISONED, restart this isolated emulator instance"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="one-line NewtonScript source")
    parser.add_argument("--container", help=f"default {DEFAULT_CONTAINER}")
    parser.add_argument(
        "--instance",
        default=os.environ.get("NEWTON_INSTANCE", ""),
        help="isolated emulator instance to evaluate in",
    )
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    container = args.container
    if not container:
        container = (
            f"newton-harness-{args.instance}_emulator_1"
            if args.instance
            else DEFAULT_CONTAINER
        )
    print(run(container, args.source, args.timeout))


if __name__ == "__main__":
    main()
