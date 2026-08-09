# EF22 active server, preferences, and Advanced slip

> **M2 integration update, 2026-08-09.** The EF22/EF22Probe package identities
> below are historical evidence for the independent client line. M2 replayed
> all seven commits onto immutable base `2fbbd4b`, retained this picker and
> minimized HS-A/HS-B/HS-C probe, added transient `STAT PROGRESS` rendering, and
> rebuilt from source as fresh `EggFrecklesEF23:jbfly`, title **Egg Freckles
> 1.0-ef23**, package version 37. The integrated package is 114,704 bytes,
> SHA-256 `093d7784c8d097646cfdd1e7cb7b38cb68ef23e8330cc0fd6af9fc5b3cbe6d53`;
> 139 tests and isolated-emulator proof are in
> `runtime/evidence/m2-ef23-integration/`. M4 remains hardware-gated: run the
> one-Send iPad procedure below with this EF23 package and photograph the final
> HS-A/HS-B/HS-C status. Do not infer iOS NIE behavior from Linux Einstein.

Date: 2026-08-09. **Prepared only:** the current Output-boundary probe was built
with the isolated host toolchain; nothing was deployed to the iPad, physical
Newton, Mars service, or any live/shared emulator.

## Result and provenance

The diagnostic package uses fresh identity `EggFrecklesEF22Probe:jbfly`, Extras
label and title **Egg Freckles 22 Probe**, and package version 36
(`examples/harness-client/egg-freckles.nprj:8-9`). The fresh identity is required
because NewtonOS does not replace an installed package identity. The
single-active-server design and 12-second post-connect handshake watchdog from
`9647e4f` remain. There is no server probing or fallback.

### EF21 comparison and narrowed question

Live iPad wire evidence showed TCP establishment but zero EF22 client
application bytes. Commit `3f1bcdc` moved the native marker ahead of
`SetInputSpec`, but comparison with the last known working iOS/NIE client rules
out ordering alone as the explanation:

- EF21 source commit `cc73acc` calls `Connected()` -> `Hello()`, then
  `ArmInput()` **before** marker `Output()` (`Main.newt` at that commit,
  lines 1042-1056). Its marker completion invokes `HelloMarkerSent()`, which
  queues framed `HELLO` (lines 1057-1100).
- Merge commit `d12dfff` records that exact source as "hardware-confirmed";
  the merged file is byte-identical to `cc73acc` (SHA-256
  `95c40ea067ca6ee8816ff4bce6ddd63375902726d4355c7c843a316257da685d`).
  The served physical package is independently recorded as the
  hardware-confirmed EF21 build at `docs/install-paths.md:108-116`.

The marker-first ordering from `3f1bcdc` remains unchanged, but it is now a
preserved experiment rather than a proven root cause. The next physical test
must distinguish whether EF22 never reaches marker `Output()` from whether
`Output()` is called but its `CompletionScript` never runs.

### Minimal visible Output-boundary probe

No endpoint, timeout, protocol, server, or callback ordering changed. One
`handshakeStage` slot and status text mark exactly the required boundaries
(`examples/harness-client/Main.newt:1480-1513,1535-1541`); the existing
12-second watchdog turns a runnable stalled stage into a persistent visible
verdict (`examples/harness-client/Main.newt:1045-1054`).

Commit `4814eec` also tried to distinguish an `Output()` call that had not
returned, but that verdict depended on this same delayed watchdog running while
the app task was blocked. Physical iOS NIE already showed a blocking endpoint
call holds the event loop (`docs/ROADMAP.md:11` and
`docs/newton-networking-lessons.md:243`), so `HS-X NO RETURN` could not be a
reliable final verdict. It was removed as unnecessary; the audit is recorded in
`runtime/evidence/ef22-output-probe/minimality-audit.txt`.

| Visible status after one Send | Exact observation | Interpretation |
|---|---|---|
| `HS-A NOT CALLED` after 12 s | `Connected()` ran, but execution did not reach the marker invocation boundary before the watchdog | **A:** marker `Output()` was never called |
| `HS-B CALLED` still visible after 12 s | execution reached the marker invocation boundary and the call is holding the app task, so the watchdog cannot repaint | **B:** `Output()` was called; no `CompletionScript` fired |
| `HS-B NO CALLBACK` after 12 s | `Output()` yielded/returned without its callback, allowing the watchdog to run | **B:** `Output()` was called; no `CompletionScript` fired |
| `HS-C CALLBACK` followed by normal `Ready` | `HelloMarkerSent()` ran, then input and framed `HELLO` continued | Neither failure; marker completion fired |
| explicit `Handshake error N` / `Handshake exception` | output completion returned an error / the call threw | Explicit endpoint error, not A or B |

The focused runnable check
`test_newton_client_source.py::test_ef22_handshake_probe_distinguishes_output_and_completion`
pins the three stage assignments and the exact invocation-boundary adjacency
(`test_newton_client_source.py:124-139`).

## Root cause and fix

The `-12` Advanced failure was a fresh/stale app-preferences nil read.
`GetAppPrefs` creates a new entry from its default frame, but it does not merge
new slots into an entry that already exists. EF22 then read `favorites` and
`defaultIndex` directly, so an empty older `EggFrecklesPrefs:jbfly` entry left
the slip with nil state and blank fields. `LoadFavorites` now guards the entry
and each slot, creates writable default rows for AirPort `10.42.0.1:6801` and
LAN `<lan-ip>:6801`, sets active index 0, and writes both through the
existing `EntryChange` path (`examples/harness-client/Main.newt`,
`DefaultFavorites`, `PrefsIndex`, `LoadFavorites`, `PersistFavorites`).

Runtime investigation found two adjacent bugs hidden by the old source-only
check:

- On this ROM, the saved favorites value reports `ClassOf(...) = 'array`; the
  prior `IsArray(...)` predicate returned nil, so every reopen discarded the
  valid saved rows and reset index 0. Evidence:
  `runtime/evidence/ef22-slip/favorites-class-probe.txt`.
- The loop parser rejected both seeded dotted addresses at runtime. `ParseIP`
  now locates exactly three dots with `StrPos`, converts four decimal octets,
  and rejects extra dots or values outside 0-255. Searchable text normalizes
  the accepted private test address as `<lan-ip>`. The original
  `runtime/evidence/ef22-slip/lan-ip-accepted-saved.png` remains byte-identical
  historical evidence and may visibly retain that address.

`GetRichString()` may return either a plain string or a rich string
(`refs/NewtonProgrammerRef20.txt:24101-24106`). `InputText` now returns a plain
string unchanged and calls `DecodeRichString(...).text` only for a rich value;
the old unconditional decode could wedge on ordinary typed text. The successful
LAN Save above exercises the plain-string runtime path.

## Advanced slip cleanup

The native `protoFloatNGo` slip now has a fixed two-line favorites summary,
full-width label and IP fields, a compact port field, two aligned button rows,
a wide bold **Save** button, explicit **Pin active** wording, and initial focus
in the IP field (label field for Add). No framework or new UI abstraction was
added. Evidence: `runtime/evidence/ef22-slip/after-advanced.png`.

## Verification record

| Check | Result | Evidence |
|---|---|---|
| Isolated ROM boot | healthy in 20 s; 320x480 image | `runtime/evidence/ef22-slip/boot.png`, `boot-up.log` |
| Before fix | Advanced raised the reproduced problem slip with blank controls | `runtime/evidence/ef22-slip/before-slip.png` |
| Fresh preferences | Advanced opened without `-12`; both defaults populated | `runtime/evidence/ef22-slip/after-advanced.png` |
| IPv4 and Save | Private LAN IPv4 accepted with no validation alert | `runtime/evidence/ef22-slip/lan-ip-accepted-saved.png` |
| Active LAN | LAN selected and marked active | `runtime/evidence/ef22-slip/lan-selected-pinned.png` |
| Persistence | close/reopen retained LAN, its fields, and active marker | `runtime/evidence/ef22-slip/lan-persisted-reopen.png` |
| Native mode | marker received in 0.284 s; `MODE NATIVE`; HELLO completed | `runtime/evidence/ef22-native/native-mode-server.log` |
| Completed client turn | `/status` reply displayed; status returned to Ready | `runtime/evidence/ef22-native/native-handshake.png`, `runtime/evidence/ef22-native/runtime-state.txt` |
| Clean idle teardown | server logged disconnect; no port-6801 socket remained | `runtime/evidence/ef22-native/teardown-proof.txt`, `runtime/evidence/ef22-native/native-mode-server.log` |
| Exact EF21 / `3f1bcdc` / corrected-probe comparison | recorded | `runtime/evidence/ef22-output-probe/endpoint-output-comparison.txt` |
| Minimality audit of `4814eec` | removed unreachable X state | `runtime/evidence/ef22-output-probe/minimality-audit.txt` |
| Focused Output probe check | 1 passed | `runtime/evidence/ef22-output-probe/focused-test.log` |
| Full suite | 123 passed | `runtime/evidence/ef22-output-probe/full-tests.log` |
| Clean build | package created as `EggFrecklesEF22Probe:jbfly` | `runtime/evidence/ef22-output-probe/build.log` |
| Reproducible build | two normalized builds byte-identical | `runtime/evidence/ef22-output-probe/reproducible-build.txt` |

The earlier runtime rows above verify commit `3f1bcdc`; the current probe was
not installed in any emulator because its only unresolved behavior is specific
to the iPad NIE runtime. The throwaway server was `/tmp/ef22-native-server.py`,
copied from tracked `server.py` and instrumented only to log the mode, initial
bytes and HELLO. The
tracked server was not modified. Its log records the exact marker, 0.284-second
arrival, `MODE NATIVE`, and completed HELLO; entering line mode or sending the
48-byte greeting would have failed this gate. The screenshot and runtime-state
text show the resulting `/status` turn completed in the client.

## Package proof

| Field | Value |
|---|---|
| Path | `examples/harness-client/egg-freckles.pkg` |
| SHA-256 | `093d7784c8d097646cfdd1e7cb7b38cb68ef23e8330cc0fd6af9fc5b3cbe6d53` |
| Size | 114,704 bytes |
| Identity | `EggFrecklesEF23:jbfly` |
| Version | 37 |
| Format | `package0`; Newton NOS 1.x; NoCompression |

Full machine-readable evidence is
`runtime/evidence/m2-ef23-integration/reproducible-package.txt`.

## Human-gated iPad sequence

These commands target only physical iPad UDID
`00008027-000678A91130402E` and Einstein bundle
`com.matthiasm.einstein.VPZ3H95WQJ`. Run each labeled block in order.

### A. Back up Einstein flash first

```sh
set -euo pipefail
UDID=00008027-000678A91130402E
BUNDLE=com.matthiasm.einstein.VPZ3H95WQJ
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="$HOME/newton-ipad-backups/einstein-$STAMP"
mkdir -p "$BACKUP"

idevice_id -l | grep -Fx "$UDID"
afcclient --container "$BUNDLE" -u "$UDID" info Documents/flash
# Read-only copy from the app container; this is the rollback image.
afcclient --container "$BUNDLE" -u "$UDID" get Documents/flash "$BACKUP/flash"
test -s "$BACKUP/flash"
sha256sum "$BACKUP/flash" | tee "$BACKUP/flash.sha256"
afcclient --container "$BUNDLE" -u "$UDID" ls Documents \
  | tee "$BACKUP/Documents.list.txt"
printf 'BACKUP=%s\n' "$BACKUP"
```

Rollback, only with Einstein fully cold/closed on the iPad:

```sh
afcclient --container "$BUNDLE" -u "$UDID" put "$BACKUP/flash" Documents/flash
```

### B. Remove document debris, then uninstall flash-resident packages

Deleting `.pkg` files prevents another install scan, but does **not** uninstall
what is already in Newton flash.

```sh
set -euo pipefail
UDID=00008027-000678A91130402E
BUNDLE=com.matthiasm.einstein.VPZ3H95WQJ
LIST=$(mktemp)
afcclient --container "$BUNDLE" -u "$UDID" ls Documents | tee "$LIST"

# Remove loader.pkg, egg-freckles.pkg, egg-freckles-ipad.pkg and every
# *.pkg.hold (plus any other stale *.pkg) returned by the listing.
awk '$NF ~ /\.pkg(\.hold)?$/ {print $NF}' "$LIST" | while IFS= read -r name; do
  afcclient --container "$BUNDLE" -u "$UDID" rm "Documents/$name"
done
rm -f "$LIST"
afcclient --container "$BUNDLE" -u "$UDID" ls Documents
```

There is no known clean baseline flash in Documents that both removes the junk
and preserves the configured NIE network stack: `flash.pre-nie-*` is explicitly
pre-NIE. Therefore do the minimal safe uninstall in Newton Extras before the
new package is copied:

1. Open **Extras** in icon mode.
2. For each item below, tap and hold until the squeak, drag across it until it is
   highlighted, then choose **Delete** from the routing picker and confirm:
   - every **Harness Loader** / **ZC… Loader** / `harness-loader` copy
     (`-HarnessLoader*` / `-Loader*` identities);
   - **Harness Probe** (`HarnessProbe:jbfly`);
   - **PT100** (`PT100:Scrawl`);
   - **Minico** (`Minico:Scrawl`);
   - every old **Egg Freckles** (`EggFrecklesEF*:jbfly`), **Chat A…** /
     **Newton Chat** (`HarnessClient*`), including any existing
     **Egg Freckles 22**.
3. Do **not** remove Internet Setup, Newton Internet Enabler, NIE Ethernet
   Module, or the Ethernet/WaveLAN driver packages; they are required for the
   handshake.
4. Re-open Extras and verify no user-installed harness/chat/test icon remains.
   Built-in Newton apps and the required network setup/driver entries are not
   part of this cleanup count.

### C. Copy and cold-launch-install the one EF23 package

```sh
set -euo pipefail
UDID=00008027-000678A91130402E
BUNDLE=com.matthiasm.einstein.VPZ3H95WQJ
PKG=/path/to/reviewed-m2-worktree/examples/harness-client/egg-freckles.pkg

test -s "$PKG"
python3 - "$PKG" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
data = p.read_bytes()
import hashlib
assert data[:8] == b"package0" and len(data) == 114_704
assert b"EggFrecklesEF23:jbfly" in data
assert hashlib.sha256(data).hexdigest() == \
    "093d7784c8d097646cfdd1e7cb7b38cb68ef23e8330cc0fd6af9fc5b3cbe6d53"
print(len(data), p)
PY

afcclient --container "$BUNDLE" -u "$UDID" put "$PKG" \
  Documents/egg-freckles-ef23.pkg
# Force Einstein's next cold-launch scanner to consider the sole .pkg.
afcclient --container "$BUNDLE" -u "$UDID" rm Documents/.lastInstall || true
afcclient --container "$BUNDLE" -u "$UDID" ls Documents
```

Do not force-quit Einstein. Perform the copy only in a human-approved window
when Einstein is already fully closed (for example, after a normal iPad
restart); if it is running, stop here. Then tap Einstein once, wait for NewtonOS
to finish its first pause, open Extras, and verify the only harness/test package
icon is clearly labeled **Egg Freckles**; its title must read **Egg Freckles 1.0-ef23**.

### D. One test: capture the 6801 handshake on Mars

On Mars, verify the existing service and start one port-only capture. Do not
filter by peer address; the iPad address is DHCP-assigned.

```sh
set -euo pipefail
ss -ltnp | grep ':6801 '
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
CAP="$HOME/ef22-ipad-handshake-$STAMP.pcap"
TXT="$HOME/ef22-ipad-handshake-$STAMP.txt"

# Leave this foreground capture running while doing the single iPad action
# below; press Ctrl-C after the iPad shows the reply, or let 90 seconds finish.
sudo timeout --signal=INT 90 tcpdump -i any -nn -s0 -U -w "$CAP" 'tcp port 6801'
sudo tcpdump -nn -tttt -s0 -A -r "$CAP" > "$TXT"
sudo chown "$USER":"$(id -gn)" "$CAP" "$TXT"
grep -aE 'Flags \[S\]|~NEWTONCLI 1|HELLO NEWTON1|ACK 00|STAT READY' "$TXT" \
  | tee "$TXT.handshake"
printf 'pcap=%s\ntext=%s\n' "$CAP" "$TXT"
```

The **single physical Send** during that capture is: open **Egg Freckles** (title **Egg Freckles 1.0-ef23**), enter `/status`, and tap **Send exactly once**. Do not tap Send for any
setup or retry; if the attempt fails, preserve the visible `HS-...` status and
capture, then stop. Success evidence is one TCP connect on
port 6801, client `~NEWTONCLI 1`, client framed `HELLO NEWTON1 1.0-ef23`, server
`ACK 00`, and server framed `STAT READY`; the iPad then receives the normal
`/status` reply in the transcript.
