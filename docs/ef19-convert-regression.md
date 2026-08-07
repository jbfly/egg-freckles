# EF19 Convert-to-Text regression fix

Date: 2026-08-07. Emulator only; no Mars or physical Newton was touched.

## Bottom line

EF18's new `T <build_ms> -1` header path, not the progress view, caused the
Convert-to-Text failure. `StampInkTime` called `StrPos(body, marker)` with two
arguments; NewtonOS 2.1 requires the start offset (`refs/NewtonProgrammerRef20.txt:65373-65391`). The resulting literal
"wrong number of arguments" `-48803` occurred while building the first body,
before `InetGrabLink`, so the publisher saw no `/ink` request.

EF19 changes that call to `StrPos(body, marker, 0)`. The non-modal
`protoFloatNGo` progress view and the `T` header both remain. Existing EF6/EF14
network armor is unchanged and regression-pinned: all NIE callbacks catch their
own exceptions, bind gets one five-second retry, and `ReleaseLink` returns while
any chat, ink, or tools endpoint is live
(`test_newton_client_source.py:143-217,220-244`).

## Trigger bisect

All three temporary packages used unique identities, the same EF13 proof flash,
the same seeded note, and stock Notes -> envelope -> Convert to Text. The full
timestamped UI transcript is `runtime/evidence/ef19-ui-bisect.log`; the server
transcript is `runtime/evidence/ef19-bisect-publisher.log`.

| Variant | Only change from EF18 | Result | `/ink` POSTs |
|---|---|---|---:|
| `EggFrecklesEF18B:jbfly` | none | immediate Newton `-48803` | 0 |
| `EggFrecklesEF18NP:jbfly` | omit `OpenProgress()` | immediate Newton `-48803` | 0 |
| `EggFrecklesEF18NT:jbfly` | omit the `T` header/stamp | progress showed `Sending page 1/8`; all parts returned 200 | 8 |

Screenshots carry the visible evidence:

- `runtime/evidence/ef19-baseline-progress.png` — unchanged EF18, `-48803`.
- `runtime/evidence/ef19-noprogress-after-tap.png` — progress disabled,
  `-48803` remains.
- `runtime/evidence/ef19-noheader-after-tap.png` — header disabled, progress
  view present and sending page 1/8.

The two-argument call was the only two-argument `StrPos` in the client; all
established calls already supplied a start offset. The source regression check
is `test_newton_client_source.py::test_ink_pages_log_build_and_send_milliseconds`.

## Final EF19 emulator validation

A fresh isolated `ef19bisect` instance was restored from the EF13 proof flash.
The final `EggFrecklesEF19:jbfly` package was installed through the emulator
control API, then stock Notes was driven only with `python3 -m emulator.client`
taps and screenshots. No large soup entry was read through `ns_eval`.

- `runtime/evidence/ef19-final-menu.png` shows the stock action picker with
  **Convert to Text**.
- `runtime/evidence/ef19-final-progress.png` shows the retained non-modal view:
  **Sending page 1/8**.
- `runtime/evidence/ef19-final-publisher.log` records exactly **8**
  `POST /ink HTTP/1.0` responses, all **200**, and exactly **8** `INKTIME` lines.
  Build values were 416, 400, 383, 383, 383, 383, 383, and 200 ms.
- `runtime/evidence/ef19-final-after.png` is the settled Notes screen after the
  final answer and 1.5-second progress close.
- `runtime/evidence/ef19-final-emulator.log` is the bounded, timestamped UI run;
  `runtime/evidence/ef19-final-container.log` is the matching emulator log
  slice. Neither those logs nor the OCR text captures contain `-48803`.

The publisher used a deterministic temporary Codex stub returning
`emulator transcription ok`; the proof therefore covers Newton collection,
body construction, `T` stamping, NIE acquisition, multipart endpoint lifecycle,
HTTP parsing/rendering, status streaming, reply filing, progress updates, and
teardown without depending on external model latency.

## Build and tests

- Full suite: **113 passed in 17.25 s**
  (`runtime/evidence/ef19-full-tests.txt`).
- Two consecutive `make newton-packages` runs produced identical
  `runtime/staging/SHA256SUMS`
  (`runtime/evidence/ef19-build-{1,2}-SHA256SUMS`).
- EF19 package SHA-256:
  `6a5f14e5b24c96bbab146bba4bb13ed100a4a176a591cc3603f722fd6445de29`.
- Paired publisher SHA-256:
  `1c9278090cb16824126d899472ceee6814f3c1c966948797c2e7da1e436e71e5`.

Hardware remains human-gated: install EF19 on the MP2000, run Convert to Text on
a real ink note, confirm all publisher parts arrive with `INKTIME`, no modal
`-48803` appears, the answer files in AI, and EF14 turns the radio off after
idle. Do not infer that physical proof from the emulator result.
