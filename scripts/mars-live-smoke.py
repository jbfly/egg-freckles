#!/usr/bin/env python3
"""One bounded native-protocol turn against the already-running mars service."""
import argparse
import json
import socket
import time


def line(sock, deadline):
    data = bytearray()
    while not data.endswith(b"\n"):
        if time.monotonic() >= deadline:
            raise TimeoutError("live authoring turn timed out")
        sock.settimeout(min(5, deadline - time.monotonic()))
        try:
            chunk = sock.recv(1)
        except socket.timeout:
            continue
        if not chunk:
            raise ConnectionError("chat service disconnected")
        data += chunk
    return bytes(data)


def checksum(body):
    return sum(body) & 255


def frame(seq, op, payload):
    body = f"{seq:02d} {op} {payload}".encode("ascii")
    return b":" + body + f"*{checksum(body):02X}\r\n".encode()


def parse(raw):
    body, marker = raw[1:].rstrip(b"\r\n").rsplit(b"*", 1)
    if not raw.startswith(b":") or checksum(body) != int(marker, 16):
        raise ValueError(f"bad frame: {raw!r}")
    seq, op, payload = body.decode("ascii").split(" ", 2)
    return int(seq), op, payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=6801)
    ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("prompt")
    args = ap.parse_args()
    deadline = time.monotonic() + args.timeout
    events, sent = [], False
    with socket.create_connection((args.host, args.port), timeout=10) as sock:
        sock.sendall(b"~NEWTONCLI 1\r\n")
        sock.sendall(frame(0, "HELLO", "NEWTON1"))
        while True:
            raw = line(sock, deadline)
            if raw.startswith(b"ACK "):
                continue
            seq, op, payload = parse(raw)
            sock.sendall(f"ACK {seq:02d}\r\n".encode())
            events.append({"op": op, "payload": payload})
            print(f"{op} {payload}", flush=True)
            if op == "STAT" and not sent:
                chunks = [args.prompt[i:i + 180] for i in range(0, len(args.prompt), 180)]
                for index, chunk in enumerate(chunks, 1):
                    payload = chunk if len(chunks) == 1 else f"{index:02d} {len(chunks):02d} {chunk}"
                    sock.sendall(frame(index, "MSG" if len(chunks) == 1 else "MSGP", payload))
                sent = True
            elif sent and op == "PROMPT":
                break
    if any(e["payload"].startswith("ERROR ") for e in events):
        raise SystemExit("live turn returned ERROR")
    print(json.dumps(events))


if __name__ == "__main__":
    main()
