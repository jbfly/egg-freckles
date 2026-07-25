#!/usr/bin/env python3
"""Bench listener for the real-hardware round-7 test.

Binds 10.42.0.1:6801 and logs, with timestamps, every connection and every
byte the Newton sends. This is deliberately dumber than server.py: the whole
question is "do payload bytes leave the Newton at all", so anything that could
itself swallow or reframe bytes is out of the picture.

Signature to compare against the emulator (rounds 4/6):
  ACCEPT -> TIMEOUT -> TOTAL b''   == same failure on real hardware (NIE bug)
  ACCEPT -> RECV b'...'            == emulator-only bug (Einstein)

ponytail: plain blocking socket, one connection at a time. That is all a
bench test needs; add threading if we ever want two Newtons at once.
"""
import socket
import sys
import time

HOST, PORT = "10.42.0.1", 6801
LOG = "runtime/logs/round7-hw-bench.log"


def main() -> None:
    log = open(LOG, "a", buffering=1)

    def say(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        log.write(line + "\n")

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    say(f"LISTEN {HOST}:{PORT} -- waiting for the Newton")

    try:
        while True:
            conn, addr = srv.accept()
            say(f"ACCEPT {addr[0]}:{addr[1]}  <- TCP handshake completed")
            conn.settimeout(30)
            total = b""
            try:
                while True:
                    buf = conn.recv(4096)
                    if not buf:
                        say("CLOSED by peer")
                        break
                    total += buf
                    say(f"RECV {buf!r}")
                    # Echo back so the Newton screen proves the round trip.
                    conn.sendall(buf)
            except socket.timeout:
                say("TIMEOUT after 30s with no data")
            except OSError as exc:
                say(f"ERROR {exc!r}")
            say(f"TOTAL {total!r}")
            if total:
                say("VERDICT: payload ARRIVED -> real hardware works, emulator-only bug")
            else:
                say("VERDICT: connected but ZERO payload -> same failure as the emulator")
            conn.close()
    except KeyboardInterrupt:
        say("stopped")
    finally:
        srv.close()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
