# EF21 native transcript scrolling

Date: 2026-08-07. Emulator only; no Mars or physical Newton was touched.

## Bottom line

The ROM scroll arrows now scroll the Egg Freckles transcript because the app is a full-screen, non-floating `protoApp`. EF21 maps `ViewScrollUpScript` and `ViewScrollDownScript` onto the existing bounded row window and removes the custom Up/Dn buttons. The earlier A8/L1 result remains correct for `protoFloatNGo`: ROM scroll routing excludes floating views.

## Change

- Identity is `EggFrecklesEF21:jbfly`, title `Egg Freckles 1.0-ef21`, package version 33 (`examples/harness-client/Main.newt`; `examples/harness-client/egg-freckles.nprj`).
- `ViewScrollUpScript` calls `ScrollUp`; `ViewScrollDownScript` calls `ScrollDown`. The proven 12-row window, ten-row page, two-row overlap, transcript cap, and snap-to-bottom behavior are unchanged.
- The two `protoTextButton` Up/Dn children are deleted and the Prompt divider reclaims their width. No radio, ink, progress, Notes, or transport code changed.
- `test_newton_client_source.py::test_the_native_scroll_arrows_page_the_transcript_window` pins the native callbacks and absence of the custom buttons.

## Emulator validation

A fresh isolated `ef21arrows` instance was seeded from `internal-before-round9-loader-20260725-195622.flash`. The exact built EF21 package was installed and opened through the emulator control API. A bounded setup expression appended 30 ordinary transcript lines and called the installed view’s normal `ShowTranscript`; it did not read or write a Notes soup.

| Step | UI action and result | Evidence |
|---|---|---|
| Bottom | 30 wrapped rows, `scrollRow=0`; visible rows end at line 30 | `runtime/evidence/ef21-scroll-bottom-before-up.png`, `.txt` |
| Native up | `python3 -m emulator.client --instance ef21arrows tap 309 446`; `scrollRow=10`; 612 pixels changed in transcript bounds `(33,35)-(194,197)` and visible rows moved to lines 9–20 | `runtime/evidence/ef21-scroll-after-up.png`, `.txt`; `ef21-ui.log` |
| Native down | `tap 309 468`; `scrollRow=0`; screenshot is pixel-identical to the original bottom | `runtime/evidence/ef21-scroll-after-down.png`, `.txt`; `ef21-ui.log` |

The first tap at historical coordinate `(309,461)` hit neither full-screen triangle and changed nothing. The screenshot itself locates the visible triangle centers at `(309,446)` and `(309,468)`; the timestamped log preserves both the failed coordinate check and the corrected proof.

## Build and tests

- Full suite: **113 passed in 18.37 s** (`runtime/evidence/ef21-full-tests.txt`); the focused client-source file is 40 of those tests.
- Clean `tntk` compilation produced `EggFrecklesEF21:jbfly`, package version 33 (`runtime/evidence/ef21-build-1.log`).
- Two consecutive `make newton-packages` runs produced byte-identical packages and identical `SHA256SUMS` (`runtime/evidence/ef21-build-{1,2}.log`, `ef21-build-{1,2}-SHA256SUMS`).
- EF21 package SHA-256: `6652fb0b2e28412cf63caf9cd692359ecee0388206d0bb4131fc1cb9a96a8ebb`.
- Paired publisher SHA-256: `538d6fa41b65373c4cb3040ff3e7512078e93e7f4d6914e8a18e7b583f6ec566`. The publisher source is unchanged by EF21.

## Remaining hardware validation

Human-gated only: install EF21 on the MP2000, create a transcript longer than twelve rows, confirm both native arrows page it and that EF14 turns the radio off after idle. Also recheck EF19/EF20 ink and progress behavior on a real note. Do not infer physical timing or pen behavior from the emulator proof.
