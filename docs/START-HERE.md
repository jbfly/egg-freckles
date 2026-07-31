# START HERE — orientation for a new agent session

Read this first. It is the only doc that tries to tell you *where the truth is*.

## What this project is

An agentic AI harness for a 1997 Apple Newton MessagePad 2000 running NewtonOS
2.1 — "Claude Code for the Newton". A host server (`server.py`, port 6801)
speaks a framed ASCII protocol to a native NewtonScript client app that the
human runs on real hardware or in the Einstein emulator. The Newton side is a
fixed-operation tool client, not a code-eval target: arbitrary
`Compile(string)` does not work on this ROM.

## Read-first order

Four docs matter. Read them in this order and stop.

1. **This file.**
2. **`docs/newton-networking-lessons.md`** — the distilled, evidence-carrying
   summary of everything the networking arc taught. Authoritative for: how to
   call `protoBasicEndpoint`, NIE behaviour, error-code meanings, and the
   footgun table in §2. Its §4 explicitly overrides parts of
   `docs/phase3-client-plan.md`. If you are about to write Newton networking
   code, §2 alone will save you a day.
3. **`docs/phase3-chat-round.md`** — what the working chat client actually is,
   as of 2026-07-26. Authoritative for: current client behaviour, the
   NewtonScript string/view traps in "What cost the most time", and the real
   package-replacement sequence.
4. **`docs/newton-dev-notes.md`** (652 lines, chronological) — the raw
   round-by-round log. Do not read front to back. `grep` it for your symptom;
   every round records its evidence files. Authoritative for: what was tried
   and what the screen actually showed.

Everything else is reference you open only when the task lands on it:

| Doc | Open it when |
|---|---|
| `docs/phase3-protocol.md` | You touch the wire format. **Read-only** — see constraints. |
| `docs/newtonscript-eval.md` | You work on the `POST /tools` fixed-op channel or `ns_eval`. |
| `docs/install-lifeline-plan.md` | Anything about recovering a bare-metal Newton. |
| `docs/hardware-bench-runbook.md` | You are about to touch the real MessagePad. |
| `docs/einstein-automation.md` | You need Einstein internals, serial ports, or the control socket. |
| `docs/newton-client-notes.md` | Package build/toolchain overrides. |
| `docs/ink-client-design.md` | Ink. Entirely unbuilt; its APIs are marked `[verify]` and are not verified. |
| `docs/notes-bridge.md`, `docs/client-network-port.md`, `docs/unna-survey.md` | Narrow topics named by their titles. |

## Ground truth vs plans — read this before trusting any doc

**Verified-findings docs.** Claims carry evidence (a `file:line`, a commit sha,
an evidence file under `runtime/evidence/`, or quoted screen text). Trust them:

- `docs/newton-networking-lessons.md`
- `docs/newton-dev-notes.md`
- `docs/phase3-chat-round.md`
- `docs/newtonscript-eval.md`

**Plans.** Written before the work; parts are already overtaken by it. Do not
treat as current state:

- `PLAN.md` — the phase roadmap. Its "Current checkpoint" ages fastest.
- `docs/phase3-client-plan.md` — largely **superseded** by
  `docs/phase3-chat-round.md`; the client it plans has shipped. Its §3
  transport recommendations are corrected by
  `docs/newton-networking-lessons.md` §4.1–4.9.
- `docs/ink-client-design.md`, `docs/install-lifeline-plan.md` — proposals.

When the two classes disagree, the verified doc wins, and **fixing the stale
one is part of your task** (see `CLAUDE.md`).

## The dev loop

Every command below was executed in this repo on 2026-07-31 and produced the
stated result. Run from the repo root.

**Tests** — 30 pass. `pytest` is not in the system python, so use `uv`:

```sh
uv run --with pytest pytest -q          # 30 passed
```

`make test` now runs the same command. Before 2026-07-31 it ran only
`test_server.py` and `test_emulator_control.py` under `unittest` (18 tests),
silently skipping `test_pkg_publisher.py` and `test_persistent_tools_server.py`
— if you are on an older checkout, do not trust it.

**Build packages** — builds on the host with `~/newton-dev/prefix/bin/tntk`,
no container needed:

```sh
make newton-packages                    # writes runtime/staging/*.pkg + SHA256SUMS
```

`tntk` needs the patch vendored at `tools/tntk-project-version.patch`; without
it every rebuild silently regresses to package version 1
(`docs/phase3-chat-round.md`, "Risk").

**Emulator** — it is normally already running and shared. Check before
starting anything:

```sh
podman ps --format '{{.Names}} {{.Status}}'
curl -fsS http://127.0.0.1:18080/health
```

`newton-harness_emulator_1` is the shared instance. `/health` reports
`"newton_screen":{"width":320,"height":480,...}` — this is the live proof of
the portrait orientation. `make emulator-up` only if nothing is running.

**Screen and input:**

```sh
python3 -m emulator.client status
python3 -m emulator.client screen /tmp/newton.png   # 320x480 4-bit grayscale PNG
python3 -m emulator.client tap 160 240
python3 -m emulator.client text "hello"
```

**Evaluate NewtonScript** — one line, result printed to stdout. The default
`--container` is a scratch emulator that usually does not exist, so pass the
container explicitly:

```sh
runtime/ns_eval.py --container newton-harness_emulator_1 '2+2'   # -> 4
```

**A full install round:** `scripts/newton-round.sh examples/harness-loader r16a`
bumps identities, builds, installs, launches, and screenshots. Use it rather
than hand-rolling the sequence.

## Hard constraints — do not violate these

- **The human types every character on a 1997 touchscreen.** Minimise
  Newton-side typing in anything you design. Typing cost is a real decision
  metric, tabulated at `docs/install-lifeline-plan.md:170-180`.
- **Real hardware needs an explicit human confirmation gate**, and destructive
  operations doubly so (`docs/notes-bridge.md:16`). The emulator is free; a
  hard reset on the MessagePad is a disaster (`docs/install-lifeline-plan.md`).
- **Never reuse a package identity.** The precise rule is in
  `docs/phase3-chat-round.md`, "Package identity — the actual rule": bumping
  the version does *not* permit replacement (`-10402`), and one-argument
  `GetPkgRef` fails silently. Use `scripts/newton-round.sh`, which bumps
  identity for you.
- **Do not change the wire format in `docs/phase3-protocol.md`.** It is
  implemented on both sides and pinned by tests. Extend around it.
- **No sudo on alpha.** Host network/AP changes are prepared for the human to
  apply, never applied by an agent.
- **Worktrees go OUTSIDE the repo directory.** A worktree inside it makes
  pytest collect duplicate test files and the suite breaks.
- **The emulator is shared.** Other sessions are using it. Never stop,
  rebuild, or reconfigure `newton-harness_emulator_1` without asking.

## Current state — 2026-07-31 (ages fastest; verify before trusting)

Working: the framed native client end to end. A prompt typed on the Newton
goes out as a framed `MSG` over TCP 6801 and a real backend reply renders in
the transcript, every frame ACKed both directions
(`docs/phase3-chat-round.md`). Package build, install, and launch are
zero-click through the Einstein control socket. 30 host tests pass.

Actually blocked, needing a human:

- **The NS Basic bootstrap exists only on the physical Newton.** It is the
  human's only working install path from a hard-reset device and its source is
  unrecoverable. Typing it into `docs/nsbasic-bootstrap.bas` is action item 1
  of `docs/install-lifeline-plan.md:265`. Still not done.
- **The serial Dock lifeline is unproven.** It needs one afternoon of hardware
  time and a photograph of the working cable chain
  (`docs/install-lifeline-plan.md`, §4).
- **The `tntk` patch is uncommitted upstream.** Vendored here as
  `tools/tntk-project-version.patch`, but `~/newton-dev/tntk` still builds from
  a dirty working tree.

Known-unverified items are listed honestly in
`docs/newton-networking-lessons.md` §3. Read that before claiming anything in
it is settled.
