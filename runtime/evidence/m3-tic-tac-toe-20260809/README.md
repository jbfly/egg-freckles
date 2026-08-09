# M3 fresh tic-tac-toe generation — emulator result

Run date: 2026-08-09 UTC. Branch base: published master
`3b2be4f5c44aafde7d981352a9d87105a6c4c721`. No physical Newton, iPad, Mars,
shared emulator, shared service, remote branch, M2 branch, or history branch was
changed.

## Result

A real `EggFrecklesEF23:jbfly` client on disposable instance `m3ttt-0809`
sent one native three-part request to an isolated local `server.py`. The
Codex/MCP authoring workflow created one fresh project and source, built once,
installed, launched, and captured the running app. Generation completed
normally in 234 seconds under the 600-second backend budget.

- Source: `generated-Main.newt`, 3,541 bytes, SHA-256
  `60e29bdda4dae31f1ed77bcf1dd9e985e0497c4f90d18c89ea38117dd0d11ddb`.
- Package: `m3-tic-tac-toe-20260809.pkg`, 4,480 bytes, SHA-256
  `c2ff5632c5d2d23ece63674f390149728f2710a26226df8d6170705a429dac56`.
- Title and identity are source/package claims, not screenshot claims:
  `generated-Main.newt` declares title **M3 Tic Tac Toe** and identity
  `M3TicTacToe20260809:nwtn`; the package blob and recorded hash preserve the
  built output.
- `tool-audit.txt` records one `write_source`, one successful `build_pkg`, one
  `emulator_install`, zero `hardware_install`, and zero `emulator_boot`.
- `client-05.png` is the genuine running-app screenshot. It shows the 3×3 board
  and `X to move` status; it does not independently prove the exact title.
- `generated-Main.newt` gives every empty square the same `MakeMove` callback,
  alternates `X`/`O`, and ignores occupied squares.

Runtime taps returned `ok` but produced no pixel change (`tap-probe.txt`).
Playability is therefore source-supported, not interaction-proven; playing one
game on the physical MP2000 remains human-gated.

## Acceptance

| M3 check | Result | Evidence and limit |
|---|---|---|
| Fresh source and one build | Pass | `mcp-events.jsonl`, `tool-audit.txt`, `hashes.txt`; one 3,541-byte source and one successful build, with no byte-identical retry. |
| Install and launch in disposable emulator | Pass | `mcp-events.jsonl`, `server.log`, `instance-up.txt`; no hardware install or emulator boot call. |
| Visible running app | Pass | `client-05.png` shows the genuine 3×3 board and `X to move` status. |
| Exact title and package identity | Source/package-supported | `generated-Main.newt` declares both; the screenshot is not claimed to prove the title. |
| Playable by taps | Not interaction-proven | Source implements alternating legal moves, but runtime taps produced no pixel change. Physical play remains human-gated. |
| Within timeout | Pass | `timeout-proof.txt`; 234 seconds, exit 0, under the 600-second budget. |
| Isolation and cleanup | Pass | `run-metadata.txt`, `boot-health.txt`, `teardown.txt`; private runtime values are normalized. |

## Curated evidence

- `client-00-after-send.png`, `client-01.png`, and `client-05.png` with matching
  OCR are genuine pre-cleanup/pre-teardown captures showing EF23 callback,
  thinking, and the board/status stage. No captures made afterward are part of
  the curated evidence.
- `server.log` and `mcp-events.jsonl` preserve timestamped request assembly and
  tool-stage chronology. Private paths, addresses, request/session values,
  process command, and ephemeral ports are normalized.
- `timeout-proof.txt`, `tool-audit.txt`, `hashes.txt`, `focused-tests.txt`, and
  `full-tests.txt` record timing, call counts, immutable output hashes, and test
  results.
- `run-metadata.txt`, `instance-up.txt`, `boot-health.txt`,
  `ef23-mounted-hash.txt`, and `teardown.txt` record isolation and cleanup;
  host and runtime identifiers are normalized while timestamps and errors are
  retained.

This curated MCP, server, client, source, package, test, and teardown evidence
proves the accepted scope without exposing private provider or session material.
