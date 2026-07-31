#!/usr/bin/env python3
"""One listener on 18081 serving both Newton bootstrap paths.

NS Basic's raw client sends a bare 'G' byte and wants exactly 15000 padded
bytes. The Loader sends 'GET /name HTTP/1.0\r\n...' and wants an HTTP
response. Both start with 'G', so dispatch on whether "GET " is present.

ponytail: sniff-and-branch, so the port never has to be swapped by hand
again. That manual swap has already cost two hardware test cycles.
"""
import hashlib
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

STAGING = Path(__file__).resolve().parent / "staging" / "hardware"
# ponytail: env-overridable so the bootstrap can push ANY package without a code edit.
# NS Basic line 140's discardAfter must equal PAD.
BOOTSTRAP = STAGING / os.environ.get("BOOTSTRAP_PKG", "harness-loader.pkg")
PAD = int(os.environ.get("BOOTSTRAP_PAD", "15000"))


def log(message):
    stamp = datetime.now().isoformat(timespec="seconds")
    print(f"{stamp} {message}", flush=True)


def bootstrap_payload():
    raw = BOOTSTRAP.read_bytes()
    if len(raw) > PAD:
        raise ValueError(f"{BOOTSTRAP.name} is {len(raw)} bytes, over the {PAD} cap")
    return raw.ljust(PAD, b"\0")


def serve_http(conn, request):
    name = request.split()[1].lstrip("/") if len(request.split()) > 1 else ""
    target = STAGING / name
    if not name or "/" in name or not target.is_file():
        log(f"HTTP 404 {name!r}")
        conn.sendall(b"HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\n\r\n")
        return
    body = target.read_bytes()
    header = (
        "HTTP/1.0 200 OK\r\n"
        "Content-Type: application/octet-stream\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    ).encode()
    conn.sendall(header + body)
    log(f"HTTP 200 {name} {len(body)} bytes")


def main():
    payload = bootstrap_payload()
    log(f"bootstrap {BOOTSTRAP.name} {PAD} bytes sha256={hashlib.sha256(payload).hexdigest()[:12]}")
    log(f"serving {STAGING} on 0.0.0.0:18081")
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("", 18081))  # ponytail: all interfaces, so wifi AP and LAN/ethernet both work
        listener.listen(4)
        while True:
            conn, peer = listener.accept()
            log(f"peer {peer}")
            try:
                with conn:
                    conn.settimeout(20)
                    first = conn.recv(512)
                    text = first.decode("latin-1", "replace")
                    if text.startswith("GET "):
                        # Loader HTTP request; read the rest of the request line if split.
                        while "\r\n" not in text and len(text) < 512:
                            more = conn.recv(512)
                            if not more:
                                break
                            text += more.decode("latin-1", "replace")
                        log(f"request {text.splitlines()[0]!r}")
                        serve_http(conn, text)
                    else:
                        log(f"bootstrap request {first[:8]!r}")
                        # Re-read staging each time so a freshly built pkg is picked up.
                        conn.sendall(bootstrap_payload())
                        log(f"sent {PAD}")
            except Exception as error:
                log(f"connection error: {error!r}")


if __name__ == "__main__":
    sys.exit(main())
