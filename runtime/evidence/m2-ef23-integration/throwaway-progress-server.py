#!/usr/bin/env python3
import os
import socket, time
from datetime import datetime, timezone


def frame(seq, op, payload=""):
    body = f"{seq:02d} {op}" + (f" {payload}" if payload else "")
    return f":{body}*{sum(body.encode('ascii')) & 0xff:02X}\r\n".encode("ascii")


def stamp(message):
    print(datetime.now(timezone.utc).isoformat(), message, flush=True)


def line(conn, buf):
    while b"\n" not in buf:
        data = conn.recv(4096)
        if not data:
            return b"", b""
        buf += data
    value, buf = buf.split(b"\n", 1)
    return value.rstrip(b"\r"), buf


def send(conn, seq, op, payload, buf):
    wire = frame(seq, op, payload)
    conn.sendall(wire)
    stamp(f"SEND {wire.rstrip()!r}")
    ack, buf = line(conn, buf)
    stamp(f"RECV {ack!r}")
    assert ack == f"ACK {seq:02d}".encode()
    return buf

with socket.create_server(("0.0.0.0", int(os.environ["EPHEMERAL_PORT"])), reuse_port=False) as listener:
    stamp("LISTEN 0.0.0.0:<ephemeral-port>")
    conn, address = listener.accept()
    with conn:
        stamp(f"ACCEPT {address}")
        buf = b""
        marker, buf = line(conn, buf)
        stamp(f"RECV {marker!r}")
        assert marker == b"~NEWTONCLI 1"
        hello, buf = line(conn, buf)
        stamp(f"RECV {hello!r}")
        hello_seq = int(hello[1:3])
        conn.sendall(f"ACK {hello_seq:02d}\r\n".encode())
        stamp(f"SEND ACK {hello_seq:02d}")
        buf = send(conn, 0, "STAT", "READY", buf)
        prompt, buf = line(conn, buf)
        stamp(f"RECV {prompt!r}")
        prompt_seq = int(prompt[1:3])
        conn.sendall(f"ACK {prompt_seq:02d}\r\n".encode())
        stamp(f"SEND ACK {prompt_seq:02d}")
        buf = send(conn, 1, "STAT", "PROGRESS Writing source", buf)
        time.sleep(10)
        buf = send(conn, 2, "STAT", "PROGRESS Building package", buf)
        time.sleep(10)
        buf = send(conn, 3, "TEXT", "LOCAL PROGRESS OK", buf)
        buf = send(conn, 4, "PROMPT", "", buf)
        time.sleep(2)
        stamp("DONE")
