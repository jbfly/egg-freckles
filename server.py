#!/usr/bin/env python3
"""newton-harness phase 1: telnet chat bootstrap for a Newton MP2000 + PT100.

45 cols, 7-bit ASCII, CRLF. Backend: `codex exec` with a JSON output schema
(model100 pattern). Env: NEWTON_FAKE_BACKEND=1 stubs the agent for tests,
NEWTON_PORT / NEWTON_STATE_DIR / NEWTON_CODEX_TIMEOUT override defaults.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

WIDTH = 45
PROMPT = "N> "
MAX_INPUT = WIDTH * 12
BASE_DIR = Path(__file__).resolve().parent
PROMPT_FILE = BASE_DIR / "agent_prompt.txt"
SCHEMA_FILE = BASE_DIR / "response_schema.json"
STATE_DIR = Path(os.environ.get("NEWTON_STATE_DIR", BASE_DIR / "state"))
PORT = int(os.environ.get("NEWTON_PORT", "6801"))
CODEX_TIMEOUT = float(os.environ.get("NEWTON_CODEX_TIMEOUT", "120"))
FAKE = os.environ.get("NEWTON_FAKE_BACKEND") == "1"
NATIVE_HANDSHAKE = b"~NEWTONCLI 1"
MAX_FRAME = 240  # ponytail: one-frame prompts; add MSG parts only when needed
FRAME_TIMEOUT = 1.0
FRAME_RETRIES = 3

GREETING = "newton-harness ready. /help for commands."
HELP_TEXT = (
    "Commands: /new resets the conversation, /quit disconnects, "
    "/help shows this text. Anything else goes to the agent."
)


class BackendError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def log(message: str) -> None:
    print(f"[newton] ts={now_iso()} {message}", file=sys.stderr, flush=True)


def ascii_clean(text: str) -> str:
    out = []
    for ch in text:
        o = ord(ch)
        if ch in "\r\n\t":
            out.append(ch)
        elif 32 <= o <= 126:
            out.append(ch)
        elif o < 128:
            continue
        else:
            out.append("?")
    return "".join(out)


def wrap_text(text: str, width: int = WIDTH) -> list[str]:
    lines: list[str] = []
    for raw in ascii_clean(text).replace("\r", "\n").split("\n"):
        raw = raw.replace("\t", " ").strip()
        if raw:
            lines.extend(
                textwrap.wrap(raw, width=width, break_long_words=True,
                              break_on_hyphens=False) or [""]
            )
        else:
            lines.append("")
    return lines


def wire_text(text: str) -> bytes:
    return "".join(line + "\r\n" for line in wrap_text(text)).encode("ascii")


class FrameError(ValueError):
    def __init__(self, reason: str, seq: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.seq = seq


def frame_line(seq: int, op: str, payload: str = "") -> bytes:
    body = f"{seq:02d} {op}" + (f" {payload}" if payload else "")
    try:
        encoded = f":{body}*{sum(body.encode('ascii')) & 0xff:02X}\r\n".encode("ascii")
    except UnicodeEncodeError as exc:
        raise FrameError("ASCII") from exc
    if not 0 <= seq <= 99 or not re.fullmatch(r"[A-Z]+", op):
        raise FrameError("PARSE")
    if len(encoded) > MAX_FRAME:
        raise FrameError("LENGTH", seq)
    return encoded


def parse_frame(raw: bytes) -> tuple[int, str, str]:
    seq = int(raw[1:3]) if len(raw) >= 3 and raw[1:3].isdigit() else None
    if len(raw) > MAX_FRAME:
        raise FrameError("LENGTH", seq)
    if raw.endswith(b"\r\n"):
        raw = raw[:-2]
    elif raw.endswith(b"\n"):
        raw = raw[:-1]
    else:
        raise FrameError("PARSE", seq)
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise FrameError("ASCII", seq) from exc
    match = re.fullmatch(r":(\d{2}) ([A-Z]+)(?: ([ -~]*))?\*([0-9A-F]{2})", text)
    if not match:
        raise FrameError("PARSE", seq)
    body = text[1:text.rfind("*")]
    seq = int(match.group(1))
    # SUM8 is byte-oriented so Newton and host compute the same checksum.
    if int(match.group(4), 16) != sum(body.encode("ascii")) & 0xff:
        raise FrameError("CHECKSUM", seq)
    return seq, match.group(2), match.group(3) or ""


async def read_wire_line(reader: asyncio.StreamReader) -> bytes:
    data = bytearray()
    while len(data) <= MAX_FRAME:
        byte = await reader.read(1)
        if not byte:
            return bytes(data)
        data += byte
        if byte == b"\n":
            return bytes(data)
    return bytes(data)


class LineEditor:
    """Per-byte input: strip telnet IAC sequences, force 7-bit, CR/LF, backspace."""

    def __init__(self, max_chars: int = MAX_INPUT) -> None:
        self.max_chars = max_chars
        self.buf: list[str] = []
        self.ignore_next_terminator = False
        self.telnet_state = 0

    def feed(self, b: int) -> tuple[bytes, str | None]:
        if self.telnet_state == 1:
            self.telnet_state = 2 if b in (251, 252, 253, 254) else 0
            return b"", None
        if self.telnet_state == 2:
            self.telnet_state = 0
            return b"", None
        if b == 255:
            self.telnet_state = 1
            return b"", None
        if b >= 128:
            return b"", None
        if b in (13, 10):
            if self.ignore_next_terminator:
                self.ignore_next_terminator = False
                return b"", None
            line = "".join(self.buf)
            self.buf.clear()
            self.ignore_next_terminator = True
            return b"\r\n", line
        self.ignore_next_terminator = False
        if b in (8, 127):
            if self.buf:
                self.buf.pop()
                return b"\b \b", None
            return b"", None
        if 32 <= b <= 126:
            if len(self.buf) < self.max_chars:
                ch = chr(b)
                self.buf.append(ch)
                return ch.encode("ascii"), None
            return b"", None
        return b"", None


class Session:
    """Single persisted conversation (state/session.json)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("history"), list):
                return data
        except (OSError, ValueError):
            pass
        return {"version": 1, "thread_id": None,
                "created_at": now_iso(), "history": []}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = now_iso()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    @property
    def thread_id(self) -> str | None:
        return self.data.get("thread_id") or None

    def record(self, role: str, content: str) -> None:
        self.data["history"].append(
            {"role": role, "content": content, "ts": now_iso()})

    def reset(self) -> None:
        self.data = {"version": 1, "thread_id": None,
                     "created_at": now_iso(), "history": []}
        self.save()


class CodexBackend:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def chat(self, user_text: str) -> str:
        thread_id = self.session.thread_id
        request = "User text: " + ascii_clean(user_text).strip()
        with tempfile.TemporaryDirectory(prefix="newton-codex-") as tmp:
            cmd = ["codex", "exec", "--sandbox", "read-only",
                   "--skip-git-repo-check", "--cd", tmp]
            if thread_id:
                cmd += ["resume", "--json", "--output-schema",
                        str(SCHEMA_FILE), thread_id, request]
            else:
                prompt = PROMPT_FILE.read_text(encoding="utf-8") + "\n\n" + request
                cmd += ["--json", "--output-schema", str(SCHEMA_FILE), prompt]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, cwd=tmp,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT)
            except OSError as exc:
                raise BackendError(f"could not run codex: {exc}") from exc
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), CODEX_TIMEOUT)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise BackendError("agent timed out")
        text = out.decode("utf-8", "replace")
        if proc.returncode != 0:
            tail = ascii_clean(text).strip()[-160:]
            raise BackendError(tail or f"codex exited {proc.returncode}")
        return self._parse(text, thread_id)

    def _parse(self, output: str, thread_id: str | None) -> str:
        final_text = None
        seen = thread_id
        for raw in output.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if (event.get("type") == "thread.started"
                    and isinstance(event.get("thread_id"), str)):
                seen = event["thread_id"]
            item = event.get("item")
            if (event.get("type") == "item.completed"
                    and isinstance(item, dict)
                    and item.get("type") == "agent_message"
                    and isinstance(item.get("text"), str)):
                final_text = item["text"]
        if final_text is None:
            raise BackendError("agent returned no message")
        try:
            visible = json.loads(final_text)["visible"]
            if not isinstance(visible, str) or not visible.strip():
                raise ValueError
        except (ValueError, KeyError, TypeError):
            # ponytail: schema enforces JSON; fall back to raw text rather
            # than drop the whole turn.
            visible = final_text
        if not seen:
            raise BackendError("agent reported no thread id")
        self.session.data["thread_id"] = seen
        return visible


class FakeBackend:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def chat(self, user_text: str) -> str:
        self.session.data["thread_id"] = self.session.thread_id or "fake-thread-1"
        return ("FAKE REPLY TO: " + ascii_clean(user_text).strip() +
                " -- the quick brown fox jumps over the lazy dog 0123456789.")


TURN_LOCK = asyncio.Lock()  # one agent turn at a time; session file is shared


async def send_frame(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                     state: dict, op: str, payload: str = "") -> None:
    seq = state["tx_seq"]
    encoded = frame_line(seq, op, payload)
    for _ in range(FRAME_RETRIES + 1):
        writer.write(encoded)
        await writer.drain()
        while True:
            try:
                raw = await asyncio.wait_for(read_wire_line(reader), FRAME_TIMEOUT)
            except asyncio.TimeoutError:
                break
            if not raw:
                raise ConnectionError("native client disconnected")
            text = raw.rstrip(b"\r\n")
            if text == f"ACK {seq:02d}".encode("ascii"):
                state["tx_seq"] = (seq + 1) % 100
                return
            nak = f"NAK {seq:02d}".encode("ascii")
            if text == nak or text.startswith(nak + b" "):
                break
            try:
                rx_seq, _, _ = parse_frame(raw)
            except FrameError as exc:
                if exc.seq is not None:
                    writer.write(f"NAK {exc.seq:02d} {exc.reason}\r\n".encode("ascii"))
                    await writer.drain()
                continue
            if rx_seq == state["last_rx"]:
                writer.write(f"ACK {rx_seq:02d}\r\n".encode("ascii"))
                await writer.drain()
            else:
                writer.write(f"NAK {rx_seq:02d} BUSY\r\n".encode("ascii"))
                await writer.drain()
    raise ConnectionError(f"no ACK for {op}")


def text_parts(text: str, seq: int) -> list[str]:
    clean = ascii_clean(text).replace("\r", "\n")
    limit = MAX_FRAME - len(frame_line(seq, "TEXT")) - 1
    # ponytail: TEXT is flat ASCII chunks; richer transcript structure is deferred.
    parts = []
    for line in clean.split("\n"):
        parts.extend([line[i:i + limit] for i in range(0, len(line), limit)] or [""])
    return parts


async def native_mode(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                      session: Session, backend) -> None:
    state = {"last_rx": None, "tx_seq": 0, "hello": False}
    while True:
        raw = await read_wire_line(reader)
        if not raw:
            return
        try:
            seq, op, payload = parse_frame(raw)
        except FrameError as exc:
            if exc.seq is not None:
                writer.write(f"NAK {exc.seq:02d} {exc.reason}\r\n".encode("ascii"))
                await writer.drain()
            if exc.reason == "LENGTH":
                return
            continue
        if seq == state["last_rx"]:
            writer.write(f"ACK {seq:02d}\r\n".encode("ascii"))
            await writer.drain()
            continue
        if op == "HELLO" and not state["hello"] and (payload == "NEWTON1" or payload.startswith("NEWTON1 ")):
            state["hello"] = True
        elif op != "MSG" or not state["hello"]:
            writer.write(f"NAK {seq:02d} OP\r\n".encode("ascii"))
            await writer.drain()
            continue
        state["last_rx"] = seq
        writer.write(f"ACK {seq:02d}\r\n".encode("ascii"))
        await writer.drain()
        if op == "HELLO":
            await send_frame(reader, writer, state, "STAT", "READY")
            continue
        text = payload.strip()
        if text.lower() == "/new":
            session.reset()
            await send_frame(reader, writer, state, "STAT", "READY")
            await send_frame(reader, writer, state, "TEXT", "New session.")
            await send_frame(reader, writer, state, "PROMPT")
            continue
        await send_frame(reader, writer, state, "STAT", "THINKING")
        async with TURN_LOCK:
            session.record("user", text)
            try:
                reply = await backend.chat(text)
            except Exception as exc:
                reply = None
                log(f"backend error: {exc!r}")
                error = ascii_clean(str(exc)).strip()[:200] or "backend failure"
            else:
                session.record("assistant", reply)
            try:
                session.save()
            except OSError as exc:
                log(f"state save failed: {exc}")
        if reply is None:
            await send_frame(reader, writer, state, "STAT", "ERROR " + error)
        else:
            for part in text_parts(reply, state["tx_seq"]):
                await send_frame(reader, writer, state, "TEXT", part)
        await send_frame(reader, writer, state, "PROMPT")


async def initial_input(reader: asyncio.StreamReader) -> tuple[bool, bytes]:
    try:
        first = await asyncio.wait_for(reader.read(1), 0.15)
    except asyncio.TimeoutError:
        return False, b""
    if first != b"~":
        return False, first
    data = bytearray(first)
    try:
        while len(data) <= len(NATIVE_HANDSHAKE) + 2 and data[-1:] != b"\n":
            byte = await asyncio.wait_for(reader.read(1), 0.5)
            if not byte:
                break
            data += byte
    except asyncio.TimeoutError:
        pass
    native = bytes(data) == NATIVE_HANDSHAKE + b"\r\n"
    return native, b"" if native else bytes(data)


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    addr = writer.get_extra_info("peername")
    log(f"connect {addr}")
    session = Session(STATE_DIR / "session.json")
    backend = FakeBackend(session) if FAKE else CodexBackend(session)
    editor = LineEditor()
    try:
        native, pending = await initial_input(reader)
        if native:
            await native_mode(reader, writer, session, backend)
            return
        writer.write(wire_text(GREETING) + b"\r\n" + PROMPT.encode("ascii"))
        await writer.drain()
        while True:
            data, pending = (pending, b"") if pending else (await reader.read(256), b"")
            if not data:
                break
            for b in data:
                echo, line = editor.feed(b)
                if echo:
                    writer.write(echo)
                if line is None:
                    continue
                text = line.strip()
                low = text.lower()
                if low == "/quit":
                    writer.write(wire_text("Bye."))
                    await writer.drain()
                    return
                if low == "/new":
                    session.reset()
                    out: str | None = "New session."
                elif low == "/help":
                    out = HELP_TEXT
                elif not text:
                    out = None
                else:
                    async with TURN_LOCK:
                        session.record("user", text)
                        try:
                            reply = await backend.chat(text)
                        except Exception as exc:  # keep session alive on any failure
                            out = f"ERROR: {ascii_clean(str(exc)).strip()}"
                            log(f"backend error: {exc!r}")
                        else:
                            session.record("assistant", reply)
                            out = reply
                        try:
                            session.save()
                        except OSError as exc:
                            log(f"state save failed: {exc}")
                if out is not None:
                    writer.write(wire_text(out) + b"\r\n")
                writer.write(PROMPT.encode("ascii"))
                await writer.drain()
    except (ConnectionError, BrokenPipeError):
        pass
    finally:
        log(f"disconnect {addr}")
        writer.close()


async def main() -> None:
    server = await asyncio.start_server(handle, "0.0.0.0", PORT)
    log(f"serving on 0.0.0.0:{PORT} fake={FAKE} state={STATE_DIR}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
