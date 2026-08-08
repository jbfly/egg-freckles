# Codex stream-limit emulator validation — 2026-08-08

Emulator only. No shared emulator, physical Newton, or model override was used.
Both long jobs ran detached with outer `timeout -k 15` bounds and the existing
per-stage limits in `scripts/test-agent-dev-loop.py`.

- Full suite: `pytest.log` records `128 passed in 17.14s` and exit status 0.
- Counter: `counter/summary.md` records 5/5 PASS. Each `counter-runN.mcp.jsonl`
  contains the required create, write, build, boot, install, launch, and screen
  completions; each PNG/OCR pair visibly contains `Counter` and `Increment`.
- Large source: `large-source/summary.md` records 1/1 PASS. The server log
  records successful single `write_source` event arguments of 88,766, 88,727,
  and 88,870 bytes. The final PNG/OCR pair visibly contains `Large Source`.
  The run self-corrected its first build and first screenshot verification,
  then completed without a human turn.
