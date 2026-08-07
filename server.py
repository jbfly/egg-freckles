#!/usr/bin/env python3
"""newton-harness phase 1: telnet chat bootstrap for a Newton MP2000 + PT100.

45 cols, 7-bit ASCII, CRLF. Backend: `codex exec` with a JSON output schema
(model100 pattern). Env: NEWTON_FAKE_BACKEND=1 stubs the agent for tests,
NEWTON_PORT / NEWTON_STATE_DIR / NEWTON_CODEX_TIMEOUT / NEWTON_MODELS override
defaults.

Slash commands (`/help`, `/status`, `/model`, `/effort`, `/sessions`, `/new`,
`/resume`) are answered here, before the backend is called, so they need no
client change and no wire change — see docs/chat-commands.md.
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
MAX_FRAME = 240
# MSGP reassembly: a prompt too long for one frame arrives as parts. The cap
# matches the note bridge's 8 KiB note limit (docs/notes-bridge.md).
MAX_PROMPT = 8192
PART_RE = re.compile(r"(\d{2}) (\d{2})(?: ([ -~]*))?")
FRAME_TIMEOUT = 1.0
FRAME_RETRIES = 3

GREETING = "newton-harness ready. /help for commands."
# Model names this host's codex accepts (empirically: an unknown one fails the
# turn with HTTP 400 "model is not supported when using Codex with a ChatGPT
# account"). Override with NEWTON_MODELS="a,b,c".
DEFAULT_MODELS = "gpt-5.6-sol,gpt-5.6-terra,gpt-5.5,gpt-5.4,gpt-5.4-mini"
MODELS = [name.strip() for name in
          os.environ.get("NEWTON_MODELS", DEFAULT_MODELS).split(",") if name.strip()]
# `minimal` parses but the API rejects it while web_search is on, so it is out.
EFFORTS = ["low", "medium", "high", "xhigh"]
MAX_LIST = 8          # sessions shown by /sessions
NAME_MAX = 18         # session name width on a 320px screen


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
    """One conversation's transcript file (session 1 is state/session.json).

    `Chat` below owns which of these is current; the registry, not this file,
    is authoritative for thread id / model / effort.
    """

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


def pick(value: str, choices: list[str]) -> str | None:
    """`2`, a full name, or an unambiguous prefix -> the chosen item."""
    value = value.strip().lower()
    if not value:
        return None
    if value.isdigit():
        index = int(value)
        return choices[index - 1] if 1 <= index <= len(choices) else None
    for choice in choices:
        if choice.lower() == value:
            return choice
    hits = [choice for choice in choices if choice.lower().startswith(value)]
    return hits[0] if len(hits) == 1 else None


def age_text(iso: str) -> str:
    """Real wall-clock age, short enough for a 320px line: now / 7m / 3h / 2d."""
    try:
        seconds = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(iso)).total_seconds()
    except (TypeError, ValueError):
        return "?"
    if seconds < 90:
        return "now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def snippet(text: str) -> str:
    # `*` is dropped, not escaped: the shipped client reads the first `*` in a
    # frame as its checksum delimiter (Main.newt:432) and truncates the line
    # there, so no reply the host builds may contain one.
    clean = " ".join(ascii_clean(text).replace("*", "").split())
    return clean[:NAME_MAX].strip() or "chat"


def new_entry(file: str, name: str = "") -> dict:
    stamp = now_iso()
    return {"name": name or "chat " + stamp[11:16], "auto": not name,
            "file": file, "thread_id": None, "model": None, "effort": None,
            "turns": 0, "created_at": stamp, "last_used": stamp}


class Chat:
    """The session registry (state/sessions.json) plus the current transcript.

    Slash commands are answered here, before any backend call, so the native
    framed client and the PT100 terminal get identical behaviour and neither
    needs a change (docs/chat-commands.md).
    """

    def __init__(self, state_dir: Path) -> None:
        self.dir = state_dir
        self.path = state_dir / "sessions.json"
        self.data = self._load()
        self.session = Session(self.dir / self.entry["file"])

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (isinstance(data, dict) and isinstance(data.get("sessions"), list)
                    and data["sessions"]):
                data["current"] = min(max(int(data.get("current", 0)), 0),
                                      len(data["sessions"]) - 1)
                return data
        except (OSError, ValueError, TypeError):
            pass
        return {"version": 1, "current": 0, "sessions": [self._adopt()]}

    def _adopt(self) -> dict:
        """First run with a registry: an older state/session.json is session 1."""
        entry = new_entry("session.json")
        try:
            old = json.loads((self.dir / "session.json").read_text(encoding="utf-8"))
            history = old["history"]
            if not isinstance(history, list):
                raise ValueError
        except (OSError, ValueError, KeyError, TypeError):
            return entry
        entry["thread_id"] = old.get("thread_id") or None
        turns = [item for item in history
                 if isinstance(item, dict) and item.get("role") == "user"]
        entry["turns"] = len(turns)
        entry["created_at"] = old.get("created_at") or entry["created_at"]
        entry["last_used"] = old.get("updated_at") or entry["last_used"]
        if turns:
            entry["name"] = snippet(str(turns[0].get("content", "")))
            entry["auto"] = False
        return entry

    @property
    def sessions(self) -> list[dict]:
        return self.data["sessions"]

    @property
    def entry(self) -> dict:
        return self.sessions[self.data["current"]]

    @property
    def index(self) -> int:
        return self.data["current"] + 1

    @property
    def thread_id(self) -> str | None:
        return self.entry.get("thread_id") or None

    @property
    def model(self) -> str | None:
        return self.entry.get("model") or None

    @property
    def effort(self) -> str | None:
        return self.entry.get("effort") or None

    def remember_thread(self, thread_id: str) -> None:
        self.entry["thread_id"] = thread_id
        self.session.data["thread_id"] = thread_id

    def record(self, role: str, content: str) -> None:
        self.session.record(role, content)
        self.entry["last_used"] = now_iso()
        if role == "user":
            self.entry["turns"] = self.entry.get("turns", 0) + 1
            if self.entry.get("auto"):
                self.entry["name"] = snippet(content)
                self.entry["auto"] = False

    def save(self) -> None:
        self.session.save()
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def switch(self, index: int) -> None:
        self.data["current"] = index
        self.entry["last_used"] = now_iso()
        self.session = Session(self.dir / self.entry["file"])

    def start(self, name: str = "") -> dict:
        used = {item.get("file") for item in self.sessions}
        number = len(self.sessions) + 1
        while f"session-{number}.json" in used:
            number += 1
        entry = new_entry(f"session-{number}.json", name)
        self.sessions.append(entry)
        self.switch(len(self.sessions) - 1)
        return entry

    def command(self, text: str) -> str | None:
        """Answer a slash command, or return None to send `text` to the agent.

        The rule (documented in docs/chat-commands.md): the first whitespace
        token is looked up in COMMANDS; a miss is an error only when the whole
        input is that one token, so `/ 2+2` and `/usr/bin/env is a path` still
        reach the agent.
        """
        parts = text.strip().split(None, 1)
        if not parts or not parts[0].startswith("/"):
            return None
        handler = COMMANDS.get(parts[0].lower())
        if handler is None:
            if len(parts) > 1:
                return None
            return f"Unknown command {parts[0]}. /help for the list."
        reply = handler(self, parts[1].strip() if len(parts) > 1 else "")
        try:
            self.save()
        except OSError as exc:
            log(f"state save failed: {exc}")
        return reply


def choice_list(command: str, current: str | None, choices: list[str]) -> str:
    lines = [f"{command[1:].capitalize()}: {current or 'codex default'}"]
    lines += [f"{number}. {name}" for number, name in enumerate(choices, 1)]
    lines.append(f"{command} <n> to set")
    return "\n".join(lines)


def cmd_help(chat: Chat, rest: str) -> str:
    return HELP_TEXT


def cmd_status(chat: Chat, rest: str) -> str:
    entry = chat.entry
    return "\n".join([
        f"Session {chat.index}/{len(chat.sessions)}: {entry['name'][:NAME_MAX]}",
        f"Model: {entry.get('model') or 'codex default'}",
        f"Effort: {entry.get('effort') or 'codex default'}",
        f"Turns: {entry.get('turns', 0)}",
    ])


def cmd_model(chat: Chat, rest: str) -> str:
    if not rest:
        return choice_list("/model", chat.model, MODELS)
    choice = pick(rest, MODELS)
    if choice is None:
        return f"No model '{rest[:20]}'. /model to list."
    chat.entry["model"] = choice
    return f"Model: {choice}"


def cmd_effort(chat: Chat, rest: str) -> str:
    if not rest:
        return choice_list("/effort", chat.effort, EFFORTS)
    choice = pick(rest, EFFORTS)
    if choice is None:
        return f"No effort '{rest[:20]}'. /effort to list."
    chat.entry["effort"] = choice
    return f"Effort: {choice}"


def cmd_sessions(chat: Chat, rest: str) -> str:
    rows = sorted(enumerate(chat.sessions, 1),
                  key=lambda row: row[1].get("last_used") or "", reverse=True)
    lines = [f"{number}.{'>' if number == chat.index else ' '}"
             f"{entry['name'][:NAME_MAX]} {entry.get('turns', 0)}t "
             f"{age_text(entry.get('last_used', ''))}"
             for number, entry in rows[:MAX_LIST]]
    if len(rows) > len(lines):
        lines.append(f"(+{len(rows) - len(lines)} older)")
    return "\n".join(lines)


def cmd_new(chat: Chat, rest: str) -> str:
    name = snippet(rest) if rest else ""
    entry = chat.entry
    if not name and not entry.get("thread_id") and not entry.get("turns"):
        # A7's New button on an untouched session: reset in place rather than
        # pile up empty registry rows. Same reply bytes as before Track F4.
        chat.session.reset()
        return "New session."
    started = chat.start(name)
    return "New session." if not name else f"New session {chat.index}: {started['name']}"


def cmd_resume(chat: Chat, rest: str) -> str:
    if not rest:
        return "Usage: /resume <n or name>"
    names = [entry["name"] for entry in chat.sessions]
    choice = pick(rest, names)
    if choice is None:
        return f"No session '{rest[:20]}'. /sessions to list."
    chat.switch(names.index(choice))
    entry = chat.entry
    return (f"Session {chat.index}: {entry['name'][:NAME_MAX]}"
            f" {entry.get('turns', 0)}t"
            f" model {entry.get('model') or 'default'}")


COMMANDS = {"/help": cmd_help, "/status": cmd_status, "/model": cmd_model,
            "/effort": cmd_effort, "/sessions": cmd_sessions, "/new": cmd_new,
            "/resume": cmd_resume}

HELP_TEXT = "\n".join([
    "/help          this list",
    "/status        session, model, effort",
    "/model [n]     show or set the model",
    "/effort [n]    show or set reasoning",
    "/sessions      list sessions",
    "/new [name]    start a session",
    "/resume <n>    switch session",
])


class CodexBackend:
    def __init__(self, ctx: Chat) -> None:
        self.ctx = ctx

    async def chat(self, user_text: str) -> str:
        thread_id = self.ctx.thread_id
        request = "User text: " + ascii_clean(user_text).strip()
        with tempfile.TemporaryDirectory(prefix="newton-codex-") as tmp:
            cmd = ["codex", "exec", "--sandbox", "read-only",
                   "--skip-git-repo-check", "--cd", tmp]
            # Both flags must precede `resume`: the subcommand rejects them
            # ("unexpected argument '--sandbox'"), and a resumed thread does
            # honour them — docs/chat-commands.md, "What codex actually does".
            if self.ctx.model:
                cmd += ["-m", self.ctx.model]
            if self.ctx.effort:
                cmd += ["-c", f"model_reasoning_effort={self.ctx.effort}"]
            if thread_id:
                cmd += ["resume", "--json", "--output-schema",
                        str(SCHEMA_FILE), thread_id, request]
            else:
                prompt = PROMPT_FILE.read_text(encoding="utf-8") + "\n\n" + request
                cmd += ["--json", "--output-schema", str(SCHEMA_FILE), prompt]
            log("codex argv: " + " ".join(cmd[:-1]))
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
        self.ctx.remember_thread(seen)
        return visible


class FakeBackend:
    def __init__(self, ctx: Chat) -> None:
        self.ctx = ctx

    async def chat(self, user_text: str) -> str:
        self.ctx.remember_thread(self.ctx.thread_id or f"fake-thread-{self.ctx.index}")
        # The tag is how tests see which model/effort the backend was handed.
        tag = ""
        if self.ctx.model or self.ctx.effort:
            tag = f" [m={self.ctx.model or '-'} e={self.ctx.effort or '-'}]"
        return ("FAKE REPLY TO: " + ascii_clean(user_text).strip() + tag +
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


def parse_part(payload: str) -> tuple[int, int, str] | None:
    """`MSGP KK NN <chunk>` -> (k, n, chunk); None if the payload is malformed."""
    match = PART_RE.fullmatch(payload)
    if not match:
        return None
    k, n = int(match.group(1)), int(match.group(2))
    if not 1 <= k <= n:
        return None
    return k, n, match.group(3) or ""


async def native_mode(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                      ctx: Chat, backend) -> None:
    # parts/parts_total hold one in-progress MSGP prompt; part 1 always restarts
    # it and any plain MSG drops it, so the state machine has no other resets.
    state = {"last_rx": None, "tx_seq": 0, "hello": False,
             "parts": [], "parts_total": None}
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
        part = None
        if op == "HELLO" and not state["hello"] and (payload == "NEWTON1" or payload.startswith("NEWTON1 ")):
            state["hello"] = True
        elif op == "MSG" and state["hello"]:
            pass
        elif op == "MSGP" and state["hello"]:
            part = parse_part(payload)
            pending = state["parts"]
            if part is None or (part[0] != 1 and (part[0] != len(pending) + 1
                                                  or part[1] != state["parts_total"])):
                writer.write(f"NAK {seq:02d} PART\r\n".encode("ascii"))
                await writer.drain()
                continue
        else:
            writer.write(f"NAK {seq:02d} OP\r\n".encode("ascii"))
            await writer.drain()
            continue
        state["last_rx"] = seq
        writer.write(f"ACK {seq:02d}\r\n".encode("ascii"))
        await writer.drain()
        if op == "HELLO":
            await send_frame(reader, writer, state, "STAT", "READY")
            continue
        if op == "MSGP":
            k, total, chunk = part
            if k == 1:
                state["parts"] = []
                state["parts_total"] = total
            state["parts"].append(chunk)
            size = sum(len(item) for item in state["parts"])
            log(f"MSGP part {k}/{total} {len(chunk)}B total={size}B")
            if size > MAX_PROMPT:
                state["parts"], state["parts_total"] = [], None
                await send_frame(reader, writer, state, "STAT",
                                 f"ERROR prompt over {MAX_PROMPT} bytes")
                await send_frame(reader, writer, state, "PROMPT")
                continue
            if k < total:
                continue
            payload = "".join(state["parts"])
            state["parts"], state["parts_total"] = [], None
            log(f"MSGP assembled {total} parts into {len(payload)}B prompt")
        else:
            state["parts"], state["parts_total"] = [], None
        text = payload.strip()
        command_reply = ctx.command(text)
        if command_reply is not None:
            await send_frame(reader, writer, state, "STAT", "READY")
            for chunk in text_parts(command_reply, state["tx_seq"]):
                await send_frame(reader, writer, state, "TEXT", chunk)
            await send_frame(reader, writer, state, "PROMPT")
            continue
        await send_frame(reader, writer, state, "STAT", "THINKING")
        async with TURN_LOCK:
            ctx.record("user", text)
            try:
                reply = await backend.chat(text)
            except Exception as exc:
                reply = None
                log(f"backend error: {exc!r}")
                error = ascii_clean(str(exc)).strip()[:200] or "backend failure"
            else:
                ctx.record("assistant", reply)
            try:
                ctx.save()
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
        first = await asyncio.wait_for(reader.read(1), 1.0)
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
    ctx = Chat(STATE_DIR)
    backend = FakeBackend(ctx) if FAKE else CodexBackend(ctx)
    editor = LineEditor()
    try:
        native, pending = await initial_input(reader)
        if native:
            await native_mode(reader, writer, ctx, backend)
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
                if text.lower() == "/quit":
                    writer.write(wire_text("Bye."))
                    await writer.drain()
                    return
                out: str | None = ctx.command(text)
                if out is None and text:
                    async with TURN_LOCK:
                        ctx.record("user", text)
                        try:
                            reply = await backend.chat(text)
                        except Exception as exc:  # keep session alive on any failure
                            out = f"ERROR: {ascii_clean(str(exc)).strip()}"
                            log(f"backend error: {exc!r}")
                        else:
                            ctx.record("assistant", reply)
                            out = reply
                        try:
                            ctx.save()
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
