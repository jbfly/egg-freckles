# Recovered session findings

This file records only findings not already stated elsewhere in the repository. The six requested baseline documents and the rest of `docs/`, `examples/`, and `ap/` were searched before inclusion.

## 1. Corrected error-code meanings

Nothing found beyond the meanings already recorded for `-48803`, `-48807`, `-48808`, `-48809`, and `-36003`. The sessions did recover a corrected *cause* for one `-48200`, recorded under dead ends, but not a new meaning for the code itself.

## 2. Working code shapes

### Arm binary input with `SetInputSpec`; do not force it with `Input()`

**Finding.** For a binary target, install the input spec and let the endpoint invoke `InputScript`. Calling `Input()` to force progress is only valid for `'string` and `'bytes` input forms and can deliver an empty or partial binary buffer immediately.

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/9af07cef-4247-4c35-917e-9f2f2e939d90/tool-results/call_Y16FN12YipOHoA4QqbhpgJKE.json`:

> “ZC25 calls `endpoint:Input()` on a **binary** input spec, although Apple documents `Input()` as valid only for `'string` and `'bytes`. It immediately forces `InputScript` with whatever is buffered (often zero/partial bytes)”

**Why this matters.** This is the difference between waiting for a complete binary termination condition and parsing an unfilled VBO as an HTTP header.

### An `Input()`-forced callback must not replace the active spec or tear down the endpoint

**Finding.** If `Input()` forces an `InputScript`, that callback cannot safely call `SetInputSpec` or `Stop`; doing so violated the documented callback contract and produced the observed `-48200` after “headers incomplete.”

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/9af07cef-4247-4c35-917e-9f2f2e939d90/tool-results/call_Y16FN12YipOHoA4QqbhpgJKE.json`:

> “then that callback calls `SetInputSpec`/`Stop` even though Apple explicitly forbids changing the active spec from an `Input()`-forced callback. That explains the ordered pair: the app first prints ‘headers incomplete,’ then Newton raises object-system error `-48200`.”

**Why this matters.** It prevents cleanup code from hiding the actual receive failure behind a second exception.

### The VBO write/cache/read byte path works exactly

**Finding.** `StuffByte` into a package VBO, followed by `ClearVBOCache` and `ExtractByte`, preserves CR/LF bytes exactly on the emulator Newton.

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/842b8706-8bc6-4a27-83ef-9dc978c2977e/tool-results/call_H0ZtCrlJzj9bmI9NNpMuc8Gj.json`:

> “The scratch emulator confirmed the full VBO path empirically: a 4-byte VBO written as `13,10,13,10`, cache-cleared, then read with `ExtractByte` displayed `13,10,13,10` on-device.”

**Why this matters.** Header-parser failures should not be blamed on VBO byte corruption without new evidence.

### `tntk` compiles `\r`, `\n`, and `\r\n\r\n` correctly

**Finding.** In ordinary string escapes, `tntk` emits the expected big-endian Unicode code units: `\r` → `00 0D`, `\n` → `00 0A`, and `\r\n\r\n` → `00 0D 00 0A 00 0D 00 0A`.

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/842b8706-8bc6-4a27-83ef-9dc978c2977e/tool-results/call_H0ZtCrlJzj9bmI9NNpMuc8Gj.json`:

> “An isolated package compiled these sentinel strings:
>
> | Source literal | Bytes in compiled `.pkg` |
> |---|---|
> | `"A\rB"` | `00 41 00 0D 00 42` |
> | `"C\nD"` | `00 43 00 0A 00 44` |
> | `"E\r\n\r\nF"` | `00 45 00 0D 00 0A 00 0D 00 0A 00 46` |”

**Why this matters.** Do not spend another round replacing normal CRLF escapes in the HTTP loader; inspect callback timing and buffer completeness instead.

## 3. Dock protocol / backup findings

Nothing found that was both evidence-backed and absent from the current repository. The recovered Dock, TCP Dock, NCU, serial restore, and PCMCIA recovery material was already captured in `docs/install-lifeline-plan.md` and `docs/hardware-bench-runbook.md`.

## 4. Hardware quirks

### Real MP2000 Wi-Fi sustained a working chat connection with 4–6 second turns

**Finding.** On the physical MessagePad 2000, the Newton connected over real Wi-Fi to `10.42.0.1:6801`, sent four complete chat turns, and held one TCP connection established for at least seven minutes. The missing replies were a rendering bug, not a transport failure.

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/35bf387d-33a8-4dc1-8c0d-a9cefad6cdb2.jsonl:8`:

> “It shows four complete user/assistant exchanges from the device today, e.g. user "Something distinctive ; )" at 09:44:37 -> assistant "Newton says: Make a new mark!" at 09:44:43. Round trips 4-6 s. The TCP connection 10.42.0.36:33668 -> 10.42.0.1:6801 has stayed ESTAB since 09:37. So transport OK, send OK, backend OK, RENDER broken.”

**Why this matters.** The physical WaveLAN/NIE path is capable of complete application round trips; future missing-output bugs should not start by reprovisioning the radio or AP.

### One physical TCP connection survived multiple chat turns

**Finding.** The same physical Newton TCP session remained `ESTAB` from 09:37 through the 09:44 exchange instead of reconnecting per turn.

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/35bf387d-33a8-4dc1-8c0d-a9cefad6cdb2.jsonl:8`:

> “The TCP connection 10.42.0.36:33668 -> 10.42.0.1:6801 has stayed ESTAB since 09:37.”

**Why this matters.** Persistent Newton-initiated sessions work on the real WaveLAN path, not only in Einstein.

### The hand-typed bootstrap installed the exact final ZC25 artifact

**Finding.** The package on the physical Newton was not an older loader: the 14,904-byte staged ZC25 package, padded to the bootstrap’s fixed 15,000-byte transfer, matched the raw sender’s SHA-256 prefix exactly.

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/9af07cef-4247-4c35-917e-9f2f2e939d90/tool-results/call_Y16FN12YipOHoA4QqbhpgJKE.json`:

> “Padding that exact ZC25 package with 96 zero bytes to 15,000 bytes produces:
>
> `c0ad9a1c3eec0f763eefeac345a9c7c9ee75f203852a34f5817949255edbcd4b`
>
> That matches the supplied raw-sender prefix `c0ad9a1c3eec`. Therefore the bootstrapped payload was the final ZC25 package, not an older loader.”

**Why this matters.** It closes the stale-package escape hatch for that hardware failure: diagnosis must address ZC25’s receive path.

## 5. Dead ends with reasons

### The emulator accepted only 1,448 response bytes before closing

**Finding.** The alleged 18,320-byte emulator download ended after Newton acknowledged 1,448 response bytes and sent FIN.

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/9af07cef-4247-4c35-917e-9f2f2e939d90/tool-results/call_Y16FN12YipOHoA4QqbhpgJKE.json`:

> “The emulator did **not** prove an 18,320-byte download. Its packet trace shows the Newton acknowledged only 1,448 response bytes before sending FIN.”

**Why this matters.** A server-side `sendall` or HTTP 200 is not a completed Newton download; packet-level acknowledgement showed the receive path stopped near the first segment.

### “Activating packages” was not proof that the HTTP package downloaded

**Finding.** The emulator’s activation screen was a reboot activating packages already present in Internal storage. It did not prove that ZC25 received or installed the advertised HTTP body.

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/9af07cef-4247-4c35-917e-9f2f2e939d90/tool-results/call_Y16FN12YipOHoA4QqbhpgJKE.json`:

> “The later “Activating packages” screen was a Newton reboot activating all packages already in Internal, not ZC25 reporting successful receipt or installation.”

**Why this matters.** An activation screen after a reboot is not an install acceptance test; require transferred-byte evidence plus a newly absent-before/present-after package identity.

### The CR/LF compiler-escape theory was disproven

**Finding.** HTTP header parsing did not fail because `tntk` mistranslated `\r` or `\n`; both the isolated compiler probe and the rebuilt loader contained correct CRLF bytes.

**Evidence.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/842b8706-8bc6-4a27-83ef-9dc978c2977e/tool-results/call_H0ZtCrlJzj9bmI9NNpMuc8Gj.json`:

> “The CR/LF hypothesis is disproven. `tntk` emits the correct CR and LF code units, and the scratch emulator confirms `ExtractByte` reads the expected bytes from a cache-cleared VBO.”

**Why this matters.** It rules out both the compiler and VBO byte path at once, narrowing the loader fault to endpoint receive semantics.

## Contradictions

### Whether every `InputScript` must re-arm `SetInputSpec`

**Transcript side.** `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/35bf387d-33a8-4dc1-8c0d-a9cefad6cdb2.jsonl:510` says:

> “**InputScript re-arm isn't needed** — `ready` only becomes true via `STAT READY`, which arrives *after* the client already consumed an `ACK` line in a callback that neither outputs nor re-arms. `SetInputSpec` input persists across callbacks. The same argument holds on your hardware log: four sends on one connection required `PROMPT` to clear `inFlight` three times.”

**Current repo side.** `docs/newton-client-notes.md:71` says:

> “Each `InputScript` re-arms `SetInputSpec` before returning”

and `docs/newtonscript-eval.md:434-435` says:

> “`InputScript` installs the next input spec inline before returning”

**Why this matters.** These imply different endpoint contracts. The hardware chat evidence suggests one installed input spec can persist, while the loader/tools docs require explicit inline replacement. Preserve both until a focused test distinguishes input-spec persistence by form, termination type, or endpoint API path.
