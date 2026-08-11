# EF22 active server, preferences, and Advanced slip

> **M2 integration update, 2026-08-09.** The EF22/EF22Probe package identities
> below are historical evidence for the independent client line. M2 replayed
> all seven commits onto immutable base `2fbbd4b`, retained this picker and
> minimized HS-A/HS-B/HS-C probe, added transient `STAT PROGRESS` rendering, and
> rebuilt from source as fresh `EggFrecklesEF23:jbfly`, title **Egg Freckles
> 1.0-ef23**, package version 37. The integrated package is 114,704 bytes,
> SHA-256 `093d7784c8d097646cfdd1e7cb7b38cb68ef23e8330cc0fd6af9fc5b3cbe6d53`;
> 139 tests and isolated-emulator proof are in
> `runtime/evidence/m2-ef23-integration/`. **M4 complete, 2026-08-11:** the
> operator performed the one-Send iPad procedure once on 2026-08-09 and directly
> observed the exact visible message `Connect error -16005`. No screenshot was
> captured. Sanitized packet evidence independently proves five successful TCP
> handshakes, five Mars greetings, and zero iPad application bytes. The human
> explicitly waived the photo acceptance artifact; no visual evidence is
> claimed. Evidence: `runtime/evidence/m4-ipad-ef23-20260809/`. Do not infer iOS
> NIE behavior from Linux Einstein.

Date: 2026-08-09; M4 acceptance updated 2026-08-11. The Output-boundary probe
was built with the isolated host toolchain. M4 later installed it on the iPad
and performed one human-gated Send; it did not change the physical Newton, Mars
service, or any live/shared emulator.

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

The marker-first ordering from `3f1bcdc` remains unchanged, but it is a
preserved experiment rather than a proven root cause. M4's later result did not
show an HS-A/HS-B/HS-C stage: the operator saw `Connect error -16005`, while the
wire showed established connections and no client application bytes.

### Minimal visible Output-boundary probe

The independent EF22 probe commits changed no endpoint, timeout, protocol,
server, or callback ordering. The later M2 integration did change the primary
chat connect `reqTimeout` from 45,000 ms to 10,000 ms; the earlier wording was
too broad. EF24 restores only that connect timeout to 45,000 ms while retaining
the existing 12-second post-connect handshake watchdog and 10-second
marker-output request timeout. Its isolated Linux Einstein handshake passes
(`runtime/evidence/ef24-chat-timeout/README.md`), but the first physical iPad
run did not: one `/status` Send with no retry showed `Connecting to server...
will send` then `Connect error -16013`, with no photo, HS-A/B/C stage, or reply.
The pcap ended before the Send and is not network evidence; the sanitized Mars
journal records seven accepted connections and no protocol/application bytes.
Hardware proof failed (`runtime/evidence/ef24-ipad-physical-20260811/README.md:9-38`; `runtime/evidence/ef24-ipad-physical-20260811/mars-journal-summary.txt:7-14`).
One `handshakeStage` slot and status text mark exactly the required boundaries
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

## M4 complete — one Send, no retry, photo waived

On 2026-08-09 the operator installed and opened EF23 package version 37, pinned
the Mars LAN endpoint, entered `/status`, and tapped **Send exactly once**. The
operator directly observed the exact visible message `Connect error -16005`;
there was no retry. No screenshot or photo was captured, and no visual evidence
is claimed. On 2026-08-11 the human explicitly waived the photo acceptance
artifact, making this observation plus the independent packet/journal evidence
the complete M4 record.

| Captured fact | Result | Evidence |
|---|---:|---|
| Packets captured / dropped | 29 / 0 | `ef23-ipad-handshake-20260809T231742Z.capture.log:5-6` |
| Successful TCP handshakes | 5 | `packet-summary.txt:22-29`; `service-journal-excerpt.txt:7-11` |
| Mars greetings | 5 × 48 bytes | `packet-summary.txt:22-32` |
| iPad application payload | 0 frames / 0 bytes | `packet-summary.txt:33` |
| `~NEWTONCLI` / `HELLO` / `ACK` / `STAT` | 0 matches | `packet-summary.txt:34` |
| Directly observed visible message | `Connect error -16005` | `packet-summary.txt:9-10` |

All evidence paths above are relative to
`runtime/evidence/m4-ipad-ef23-20260809/`. The committed derivatives replace
private addresses and ephemeral ports with connection labels. The source
pcapng is not committed because it contains private capture metadata; its
SHA-256 is retained in `packet-summary.txt:37-43` so the curated derivative can
be traced to the preserved source.

Automated `idevicescreenshot` failed at the screenshotr/developer-disk step.
That failure and the absence of a screen artifact are recorded in
`packet-summary.txt:9-14`. The waiver accepts the missing artifact; it does not
turn the direct observation into a photograph.

## Human-gated iPad sequence (performed once; retained for provenance)

The executed plan is retained below for provenance with device-local values
replaced by placeholders. Do not repeat the one-Send attempt: M4 is complete.

### A. Back up Einstein flash first

```sh
set -euo pipefail
UDID='<ipad-udid>'
BUNDLE='<einstein-bundle-id>'
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
UDID='<ipad-udid>'
BUNDLE='<einstein-bundle-id>'
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
UDID='<ipad-udid>'
BUNDLE='<einstein-bundle-id>'
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

The planned **single physical Send** was: open **Egg Freckles** (title **Egg
Freckles 1.0-ef23**), enter `/status`, and tap **Send exactly once**, with no
setup Send or retry. The planned success signature was one TCP connect on port
6801, client `~NEWTONCLI 1`, client framed `HELLO NEWTON1 1.0-ef23`, server
`ACK 00`, and server framed `STAT READY`, followed by the normal `/status`
reply. The M4 result above records what occurred instead.
