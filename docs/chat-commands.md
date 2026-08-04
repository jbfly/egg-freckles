# Chat commands — session and model control from the Newton

ROADMAP Track F4, live-proven 2026-08-03. Everything here is **server-side**:
`server.py` answers these before the backend is called, and the replies are
ordinary `TEXT` frames. There is no client change and no wire change, so it
works from **hardware Chat A3 unchanged** and from emulator Chat A9 alike
(`/help` re-proved on A9, `runtime/evidence/a9ask-14-help-bottom.png`), and so
also from A9's successor **Egg Freckles** (`EggFrecklesEF1:jbfly`) —
and from the PT100 terminal path, which shares the same code.

## The command set

| Command | Reply (as it renders on the Newton) |
|---|---|
| `/help` | the seven lines below, one per `TEXT` frame |
| `/status` | `Session 1/3: use your newton to` / `Model: gpt-5.4-mini` / `Effort: low` / `Turns: 3` |
| `/model` | `Model: codex default`, then `1. gpt-5.6-sol` … `5. gpt-5.4-mini`, then `/model <n> to set` |
| `/model 2` | `Model: gpt-5.6-terra` |
| `/effort` | `Effort: codex default`, then `1. low` … `4. xhigh` |
| `/effort low` | `Effort: low` |
| `/sessions` | `3.>demo 0t 2m` / `2. chat 21:13 0t 4m` / `1. use your newton to 1t 1h` |
| `/new` | `New session.` — **byte-identical to before F4**, which is what the chat client's New button sends |
| `/new demo` | `New session 3: demo` |
| `/resume 1` | `Session 1: use your newton to 1t model gpt-5.6-terra` |
| `/nope` | `Unknown command /nope. /help for the list.` |

`/quit` stays what it was: a PT100-only disconnect, handled before this table.

Numbers are the point. `/model 2` costs two characters on a 1997 touchscreen;
`gpt-5.6-terra` costs thirteen. Every selector (`/model`, `/effort`, `/resume`)
takes a number, a full name, or an unambiguous prefix, case-insensitively.

In `/sessions`, the number is the session's **registry ordinal** — stable, so
`/resume 1` always means the same session — while the rows are ordered
most-recent-first and capped at 8 (`(+N older)` follows if there are more).
`>` marks the current session. Ages are real wall-clock: `now`, `7m`, `3h`,
`2d`.

## What is and is not a command

`Chat.command` (`server.py`) splits the input on the first whitespace:

1. If the first token is a known command name, it is a command.
2. If it is not known **and the input is that one token alone**, it is an
   error — `Unknown command /foo. /help for the list.`
3. Otherwise the whole input goes to the agent untouched.

So `/ 2+2` and `/usr/bin/env lives there` reach the agent; a lone `/foo` does
not. The cost of rule 2 is that a one-word prompt starting with `/` — a bare
path, say — is refused instead of answered; say it in a sentence and it goes
through.

## State: the sessions registry

`$NEWTON_STATE_DIR/sessions.json` (atomic write, same `.tmp` + `replace`
pattern as the transcript file):

```json
{"version": 1, "current": 0,
 "sessions": [{"name": "use your newton to", "auto": false,
               "file": "session.json", "thread_id": "019fc923-…",
               "model": "gpt-5.4-mini", "effort": "low", "turns": 3,
               "created_at": "…", "last_used": "…"}]}
```

- Model and effort are **per session**, not global, and persist across a server
  restart.
- Session 1 keeps the historic filename `session.json`; later sessions are
  `session-2.json`, `session-3.json`, … Each is the transcript only; the
  registry is authoritative for thread id, model and effort.
- **Migration is automatic.** On the first start with no registry, an existing
  `state/session.json` becomes session 1 with its `thread_id`, its user-turn
  count and a name taken from its first prompt. Nothing is moved or rewritten.
  Proven on the Track D3 round's real state file
  (`runtime/evidence/f4round-registry-after-migration.json`).
- A session with no name yet is `chat HH:MM` and renames itself to the first
  18 characters of its first prompt. Slash commands do not name a session —
  only a real turn does.
- **Bare `/new` on an untouched session resets in place** instead of appending
  an empty row, so tapping A7's New button repeatedly does not grow the file.

## What codex actually does — measured on this host

codex-cli 0.146.0, ChatGPT-account auth. Full transcripts:
`runtime/evidence/f4round-round.txt` §1.

- **Valid model names** come from `~/.codex/models_cache.json` (the ones with
  `visibility: list`). The shipped default list is
  `gpt-5.6-sol, gpt-5.6-terra, gpt-5.5, gpt-5.4, gpt-5.4-mini`; override it
  with `NEWTON_MODELS="a,b,c"`. An unknown name is not a CLI error — the turn
  starts and then fails with HTTP 400 *"The 'x' model is not supported when
  using Codex with a ChatGPT account."*
- **Effort** is `-c model_reasoning_effort=<level>`. `low/medium/high/xhigh`
  work on every listed model. `minimal` parses but the API refuses it —
  *"The following tools cannot be used with reasoning.effort 'minimal':
  web_search."* — so it is not offered. `max`/`ultra` exist only on the 5.6
  family and are left out to keep the list short.
- **A resumed thread honours both.** Turn 1 of a thread ran
  `gpt-5.4-mini/low`; the same thread resumed with `-m gpt-5.5 -c
  model_reasoning_effort=xhigh` recorded `gpt-5.5/xhigh` in its rollout
  `turn_context`, and codex itself announced the switch. **A model change does
  not need `/new`** — it takes effect on the next turn.
- **Order matters**: `codex exec resume -m X` fails with *"unexpected argument
  '--sandbox' found"*. Both flags go **before** the `resume` subcommand, where
  `--sandbox`/`--cd` already are. `CodexBackend.chat` builds them there and
  logs the whole argv (`codex argv: …`) on every turn.

## The one host-side rule the client imposes

**No reply may contain `*`.** `examples/harness-client/Main.newt:432` finds the
*first* `*` in a frame and treats it as the checksum delimiter, so a payload
containing one is truncated on screen — silently, since the frame still ACKs.
The host's own `parse_frame` uses the last `*` and
`docs/phase3-protocol.md` permits it in a payload, so this is a client
limitation and hardware A3 has the same code. Found live in the F4 round when
`/sessions` rendered as a bare `3.`; the marker is now `>` and `snippet()`
strips `*` from session names. Two tests pin it.

## Tests

`test_server.py`, 16 tests: `RegistryTest` covers migration from the old single
file, a corrupt registry, a round trip through disk, the bare-`/new` guard, the
`*` rule, `pick()` and the `NEWTON_MODELS` override; the socket tests drive
`/help`, `/status`, `/model` by number (asserting the fake backend was handed
that model), a refused model/effort, `/new <name>` preserving the old session,
`/resume` switching the thread id, the unknown-command rule, persistence across
a reconnect, and the PT100 path. Suite total 78.
