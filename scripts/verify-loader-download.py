#!/usr/bin/env python3
"""Serve one loader download and require every response byte to be TCP-ACKed."""
import argparse
import socket
import struct
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("body", type=Path)
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()
    body = args.body.read_bytes()
    header = (
        "HTTP/1.0 200 OK\r\n"
        "Content-Type: application/octet-stream\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    ).encode()
    response = header + body

    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("", 18081))
        listener.listen(1)
        print(f"serving {len(header)}-byte header + {len(body)}-byte body", flush=True)
        conn, peer = listener.accept()
        with conn:
            conn.settimeout(args.timeout)
            request = conn.recv(4096)
            if not request.startswith(b"GET "):
                raise SystemExit(f"unexpected request from {peer}: {request[:80]!r}")
            conn.sendall(response)
            try:
                while conn.recv(256):
                    pass
            except TimeoutError:
                pass
            info = conn.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 256)
            acked = struct.unpack_from("<Q", info, 120)[0]

    print(f"client acked {acked} of {len(response)} bytes", flush=True)
    if acked != len(response):
        raise SystemExit(1)
    print("PASS: loader ACKed the complete response")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
