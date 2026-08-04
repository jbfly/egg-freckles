# Next hardware session — ordered script

> **SUPERSEDED 2026-08-02.** This is a pre-ZC40 session plan; the hardware
> session it was written for already happened on 2026-08-02. **Do not follow
> Step 5's "keep only ZC34 Loader 2.0" instruction** — ZC40 is the current
> loader, ZC39 the documented live fallback; deleting down to ZC34 would
> destroy six generations of progress. For what is actually on the device,
> see `docs/installed-package-inventory.md`. For the current bench procedure,
> see `docs/hardware-bench-runbook.md`. The rest of this file is kept for its
> NIE/AP appendices, still cited elsewhere.

Written 2026-07-31 while the Newton was not present and mars was offline.
Nothing below has been run against the device. This is the *session script*:
what to do, in what order, when you next sit down with the MessagePad 2000.

It does **not** repeat `docs/hardware-bench-runbook.md`. That runbook is the
reference for AP bring-up, the package tables, and the Dock/serial mechanics;
this file is the ordering, the typing cost, and the stop conditions. Where a
step is already documented there, this file gives the line reference and the
expected output only.

## Bottom line, and one change to the stated priority order

The order you proposed is right, with **one correction to step 1** and **one
correction to the preflight command**.

1. **Step 1 cannot be "verify the reconstruction line by line", because there is
   no reconstruction to verify.** `task/nsbasic-bootstrap` is still at
   `4469610` — the same commit as `master`, zero files added. Verified:
   `git rev-parse task/nsbasic-bootstrap` = `git rev-parse master`, and
   `git show task/nsbasic-bootstrap:bootstrap/nsbasic-bootstrap.bas` does not
   resolve. Nothing to diff against. Re-check before the session; if the worker
   has landed by then, use the variant in step 1b.
   The replacement is strictly better anyway: **photograph the program, do not
   read it aloud.** A camera converts scarce device time into unlimited offline
   agent time, and transcription errors get caught in the repo instead of on the
   screen. Reading line by line burns the one resource you cannot get more of.
2. **`curl -sI` is the wrong preflight command and will look like a hang.**
   `runtime/dual_send.py:70` branches on `text.startswith("GET ")`. A `HEAD`
   request does not start with `GET `, so it falls into the *bootstrap* branch
   and the server writes 15,000 padded bytes of `harness-loader.pkg` at you.
   Use a real GET (exact command in the preflight below).

Everything else stands. Two facts that pin the whole session:

- **Every Newton-side address in this repo is hardcoded to `10.42.0.1:18081`** —
  `examples/harness-loader/Main.newt:99` (`local address := [10, 42, 0, 1]`),
  `:22` (`serverPort: 18081`), and `examples/harness-tools/Main.newt:72`
  (`arglist: [10, 42, 0, 1, 18081]` — that package was deleted in Track L1; the
  same hardcoded address now lives in the tools-channel section of
  `examples/harness-client/Main.newt`). So the answer to the mars/vacation
  question is: **bring up the AP and put mars on 10.42.0.1.** Do not try to make
  the house LAN work — it costs one 17-character NS Basic edit to unify on
  `10.42.0.1`, and then every other step costs zero typed characters. Chasing
  `192.168.1.x` saves those 17 characters and then forces you to rebuild and
  re-push two packages to change addresses that are compiled in.
- **The staged loader is newer than anything on the device.**
  `runtime/staging/hardware/harness-loader.pkg` (13,568 bytes, SHA-256
  `6922d4b8…`) is byte-identical to `examples/harness-loader/harness-loader.pkg`
  and is `ZC34 Loader 2.0`, identity `-HarnessLoaderZC34:jbfly`
  (`examples/harness-loader/Main.newt:1-3`). The eight loaders in Extras are
  older rounds. Its filename field already defaults to `harness-tools.pkg`
  (`:320`) and its button is labelled `Install` (`:327`) — so once ZC34 is on
  the device, proving install-and-run costs **zero** typed characters.

---

## Preflight — on mars, before the Newton is switched on

All host-side. Getting this wrong wastes device time, which is the expensive
kind. Nothing here touches the Newton.

**P1. Power on mars and confirm you can reach it.**

```sh
ssh jbfly@10.13.13.12 hostname      # or 192.168.1.242 on the house LAN
```

Expect `mars`. If this fails, nothing else in this document is possible —
**blocks everything**.

**P2. Check nothing else is holding the emulator's address, and accept the
tradeoff.**

Bringing the AP up **moves `10.42.0.1` from loopback to `wlan0`**, which stops
any running Einstein work (`docs/hardware-bench-runbook.md:11-19`). Other people
are using `newton-harness_emulator_1`. Confirm you are clear to take the address
before `apply.sh`, and tell them. Reverting is `sudo ap/teardown.sh` then
`sudo ap/emulator-only.sh` — a couple of minutes, not a rebuild.

**P3. Bring the AP up.** Per `docs/hardware-bench-runbook.md:67-87`:

```sh
cd ~/git/newton-harness
sudo ap/emulator-only.sh down
sudo ap/apply.sh
./ap/hardware-preflight.sh            # expect all ok, exit 0
sudo nft -f ap/newton-ap.nft          # opens 3679 for Dock, needed at step 4
```

If `apply.sh` fails with a firmware reset, the `modprobe -r iwlmvm iwlwifi`
recipe is at runbook line 83.

**P4. Start the package server.** Either form:

```sh
cd ~/git/newton-harness && nohup python3 runtime/dual_send.py >/tmp/dual.log 2>&1 &
```

or, to survive a reboot (`runtime/dual-send.service:2-4`):

```sh
cp runtime/dual-send.service ~/.config/systemd/user/
systemctl --user enable --now dual-send && loginctl enable-linger jbfly
```

Expect in `/tmp/dual.log` (or `journalctl --user -u dual-send`):

```text
… bootstrap harness-loader.pkg 15000 bytes sha256=…
… serving /home/jbfly/git/newton-harness/runtime/staging/hardware on 0.0.0.0:18081
```

The `bootstrap harness-loader.pkg` line is the one that matters: it confirms the
raw NS Basic path will hand you **ZC34**, not something stale.

**P5. Prove the HTTP path with a GET, not a HEAD.**

```sh
curl --http1.0 -sS -o /tmp/ht.pkg -w '%{http_code} %{size_download}\n' \
  http://10.42.0.1:18081/harness-tools.pkg
```

Expect exactly `200 18320`. Anything else — especially `200 15000` — means you
sent a non-`GET` and got the bootstrap payload; re-read the corrections above.
**Blocks steps 2 and 3.**

**P6. Have the camera ready and a note file open.** Step 1 is entirely
photography and it is the highest-value thing in the session.

Preflight typing on the Newton: **0 characters.**

---

## Step 1 — Preserve the NS Basic bootstrap (READ-ONLY, do this first)

**Why first:** it exists only on the device, it is your sole install path, and
capturing it is read-only and cannot fail destructively. If you get through
exactly one step today, this is the one that must be it.

**Newton taps:** Extras → NS Basic → open the demo slot / the saved program.
Scroll to the top. Then, for each screenful: photograph, scroll by one screen
**with overlap of at least two visible lines**, photograph again. Repeat to the
end. Do not edit anything. Do not tap Run.

**Expected:** a numbered listing including a line near 70 containing an IP as a
comma-separated array (currently `192.168.1.11`-shaped) and a line near 140 with
a `discardAfter` value that must equal `15000`
(`runtime/dual_send.py:20-22` — "NS Basic line 140's discardAfter must equal
PAD").

**Then, still at the bench:** transfer the photos to mars *before you close NS
Basic*, and confirm the first and last lines are legible on a real screen.
Reading them back later on a phone and finding line 90 blurred is the failure
mode this step exists to prevent.

**If it fails:** if the program is *not there* — the demo slot is empty or holds
something else — stop and say so; that is a much worse day than this document
assumes, and it makes step 4 impossible. **Blocks steps 2 and 4** (both go
through the bootstrap). Steps 3 and 5 remain possible.

**Typing: 0 characters.**

### Step 1b — only if `task/nsbasic-bootstrap` has landed by then

Re-check first:

```sh
git log --all --oneline | head -30
git show task/nsbasic-bootstrap:bootstrap/nsbasic-bootstrap.bas
```

If a file exists, still photograph first (step 1), then use the reconstruction
as a *checklist* while the program is open: read only the lines where the
reconstruction is marked uncertain, rather than all of them. Correct the file on
mars from the photographs, not from memory. **This step depends on unmerged
worker output — verify it exists before relying on it.**

---

## Step 2 — Prove a package installs over WiFi *and runs*

**Why second:** "install queued" is all we have ever seen
(`docs/newton-networking-lessons.md:239-244` — the `-36003` completion failure
is unresolved and "the 'install queued' status is reported, not 'install
succeeded'"). Closing that gap is the crux of the project.

**2a — associate the Newton.** WaveLAN settings → SSID `newton`, encryption
None. Internet Setup → obtain IP automatically. Detail at
`docs/hardware-bench-runbook.md:88-104`. On mars:

```sh
sudo hostapd_cli -p /run/newton-ap/hostapd all_sta
cat /run/newton-ap/dnsmasq.leases
iw dev wlan0 station dump | grep -E 'Station|signal|tx bitrate'
```

Expect a MAC, a `10.42.0.10–.50` lease, and a signal/bitrate figure — **record
the bitrate**, you need it to read any latency number honestly.
Typing: `newton` = **6 characters**, and 0 if the network profile is saved.
**Blocks the rest of step 2, and step 4.**

**2b — push ZC34 with the NS Basic bootstrap.** This is the step that needs the
line-70 edit; see step 4, which you should do *here*, inline. Then run the
program. Expect `/tmp/dual.log` to show:

```text
… peer ('10.42.0.xx', …)
… bootstrap request b'G'
… sent 15000
```

and the Newton to show its normal package-install flow. `ZC34 Loader 2.0`
appears in Extras.

*If ZC34 turns out to be already installed*, skip 2b entirely — check Extras for
a loader whose title bar reads exactly `ZC34 Loader 2.0` before spending the
typing.

**2c — the actual proof: install and then RUN.** Open `ZC34 Loader 2.0`. The
File field already reads `harness-tools.pkg` (`Main.newt:320`). Tap **Install**.

Expect on the Newton a progress path ending in an install report, and in
`/tmp/dual.log`:

```text
… request 'GET /harness-tools.pkg HTTP/1.0'
… HTTP 200 harness-tools.pkg 18320 bytes
```

Then — and this is the part that has never been proven — **open Harness Tools
from Extras** and, on mars:

```sh
ss -tn | grep 18081                                  # expect ONE ESTAB from 10.42.0.xx
python3 runtime/bench_tools.py --op front_app --count 5
```

`front_app` must **name the app that is actually frontmost on the Newton's
screen**. That is the pass condition — a returned string that matches the glass
in front of you. `ping` succeeding is not enough; a package that installed but
did not run cannot answer `front_app`.

**If it fails:**

| Symptom | Reading | Blocks? |
|---|---|---|
| No `GET` line in `/tmp/dual.log` | The request never left the Newton. Historically this was the async-output-spec bug (`docs/newton-networking-lessons.md:120-137`), not a network fault. | Blocks step 5 only |
| `HTTP 200 … 18320 bytes` but no install prompt | Download works, install path does not — the `-36003` question. **Record the exact on-screen text and code.** | Blocks step 5 |
| Installs, but `ss -tn` shows no ESTAB after opening Harness Tools | Installed-but-not-running: exactly the distinction this step exists to test. Valuable negative result. | Blocks step 5 |
| `front_app` returns a stale or wrong app | Do not accept it. Note it verbatim. | Blocks step 5 |

Step 3 does **not** depend on any of this — it uses the ROM Dock, not our
packages. If step 2 fails, go straight to step 3.

**Typing: 6 characters** (SSID, 0 if saved), plus step 4's 17.

---

## Step 3 — Read-only Dock enumeration over TCP

**Why third:** it is read-only and uses the ROM Dock protocol, but TCP/IP is not
a stock Dock transport. It requires NIE plus the separate Dock TCP package.
The verified recovery copy is `downloads/recovery/Dock_TCP-1.2-en.pkg`; if Dock
has no TCP/IP choice, install it with ZC40 before this step. It is still the
cheapest evidence about what is actually on the device once that transport is
active.

`runtime/newton_backup.py` and `docs/newton-backup-runbook.md` are merged on
master. Confirm the offline protocol tests before relying on this step:

```sh
uv run --with pytest pytest -q test_newton_backup.py
```

The tests are offline frame/NSOF tests only; they do not prove the hardware
path.

**Newton taps:** Extras → **Dock** → **TCP/IP** (not Serial, not AppleTalk). If
it asks for the desktop address, enter `10.42.0.1`. Stop at the Connect screen —
**do not tap Connect yet.**

**On mars, first:**

```sh
cd ~/git/newton-harness
runtime/newton_backup.py
```

Expect `Listening on 10.42.0.1:3679; now tap Connect in Dock on the Newton`.
**Now tap Connect.** Expect `Newton connected from …` followed by each store and
lines like `Notes: 17 entries`, then a clean disconnect with **no install or
restore prompt on the Newton**.

**Only if enumeration succeeds**, repeat the Newton taps and run the dump:

```sh
runtime/newton_backup.py --dump "runtime/backups/messagepad-$(date +%Y%m%d-%H%M%S)"
```

It refuses an existing directory, so a retry cannot overwrite an earlier
attempt. Full detail and the failure table are in
`docs/newton-backup-runbook.md`.

**If it fails:** `no Newton connected within 60s` → confirm Dock still says
TCP/IP, the address is exactly `10.42.0.1`, and run `ss -tn | grep 3679` while
tapping Connect. Do not retry more than once without recording the exact error.
Failure here **blocks nothing** — skip to step 5.

**One honest caveat:** the output is a *selective soup export*, not an
NCU-restorable backup. Do not treat a successful dump as permission to hard
reset. That is the runbook's own warning and it is correct.

**Typing: 9 characters** (`10.42.0.1`), or 0 if Dock remembers it.

---

## Step 4 — The line-70 edit (do it inline during step 2b)

This is not really a separate step; it is the one edit that step 2b requires.
It is listed separately because it is the only place in the session where you
**modify the NS Basic program**, and therefore the only place with real risk.

**Do step 1 first. Non-negotiable.** Until the program is photographed and on
mars, editing it risks the only copy.

**The edit:** line 70's address array becomes `[10,42,0,1,18081]` — **17
characters**. That is under the 40-character redesign threshold, so it is not
worth engineering around, and it buys you correct addresses in ZC34
(`Main.newt:99`), Harness Tools (`Main.newt:72`), and Dock all at once.

While you are there, confirm line 140's `discardAfter` reads `15000`. If it does
not, the bootstrap will truncate the package. Changing it is another ~5
characters; leave it alone if it is already right.

**What NOT to do:** do not retype the program, do not "clean it up", do not save
over the demo slot with a variant. One line, one edit.

**If it fails** (mistyped, program won't run): you have the photographs from
step 1, so it is recoverable — that is the entire reason step 1 comes first.
Failure **blocks step 2b and 5**, not step 3.

**Typing: 17 characters.**

### If the AP will not come up

Fallback, house LAN, zero Newton typing: on mars,
`sudo ip addr add 192.168.1.11/24 dev <house-iface>` so that mars answers on the
address line 70 *already* contains. `runtime/dual_send.py:60` binds `("", 18081)`
— all interfaces — so the bootstrap will work unchanged.

**But be clear about what this buys you:** the NS Basic bootstrap will install
packages, and nothing else will work. ZC34 and Harness Tools both hardcode
`10.42.0.1`, so step 2c's run-proof is impossible on the house LAN, and step 3
needs `--address 192.168.1.242` (`newton_backup.py:300` accepts `--address`).
This is an install-only fallback, not an equivalent path.

---

## Step 5 — Delete the stale loaders (LAST, and only on a clean pass)

**Precondition, absolute:** step 2c passed — `front_app` named the correct app.
Not "installed". Not "queued". Ran.

**Newton taps:** Extras → confirm exactly one loader titled `ZC34 Loader 2.0`
is present and working. Then, for each of the other loaders: tap its icon's
routing/Delete action and confirm. Delete the older ones **one at a time**,
checking after each that ZC34 still opens.

**Why last:** they cost nothing but clutter, and each one is a fallback if ZC34
turns out to be broken in a way step 2c did not catch. Deleting them early
converts a cluttered Extras drawer into a bricked install path. Note also that
`docs/newton-dev-notes.md:345` warns the Extras drawer is paged and a nearby
text label is not reliable identification — read the title bar of the app you
open, not the icon caption.

**If it fails:** a delete that errors is harmless; stop and leave the rest.
**Blocks nothing.**

**Typing: 0 characters.**

---

## Typing budget

Characters typed on the 1997 touchscreen. Taps are free.

| Step | What is typed | Chars | Avoidable? |
|---|---|---:|---|
| Preflight | nothing | 0 | — |
| 1 — photograph bootstrap | nothing | 0 | — |
| 2a — associate | SSID `newton` | 6 | Yes, 0 if the network profile is saved |
| 2b/2c — push ZC34, install, run | nothing (File field defaults to `harness-tools.pkg`) | 0 | — |
| 3 — Dock enumeration | desktop address `10.42.0.1` | 9 | Yes, 0 if Dock remembers it |
| 4 — NS Basic line 70 | `[10,42,0,1,18081]` | 17 | No — and worth paying, see step 4 |
| 5 — delete loaders | nothing | 0 | — |
| **Total** | | **32** | **17 if the SSID and Dock address are remembered** |

No step exceeds the ~40-character redesign threshold, so nothing here needs to
be engineered around. The two things that *would* have blown the budget are
already designed out: the loader's File field defaults to the package we want
(`Main.newt:320`), and `dual_send.py` sniffs the protocol so the port never has
to be swapped by hand — a manual swap that "already cost two hardware test
cycles" (`docs/newton-networking-lessons.md:213`).

The 32 characters assume the bootstrap does not need retyping. If step 1 finds
the demo slot empty, the budget is "the whole program, hundreds to thousands"
(`docs/install-lifeline-plan.md:178`) and this session becomes a different
session.

---

## Abort and safety — what NOT to do

- **Do not hard reset.** Not to clear a wedged NIE link, not to fix a failed
  install, not for any reason in this document. A hard reset erases the internal
  store, which is where the NS Basic bootstrap lives, and nothing here restores
  it. The serial lifeline that would make a reset survivable **has never been run
  against the physical Newton** (`docs/install-lifeline-plan.md:24, 92-93`).
- **Do not overwrite the NS Basic demo slot until step 1's photographs are on
  mars and legible.** This has already happened once.
- **Do not delete any loader until step 2c passes.** "Install queued" is not a
  pass.
- **Do not treat step 3's export as a backup you can restore from.** It is a
  selective soup export; it does not carry packages or system data.
- **Do not remove or insert a PCMCIA card during a reset.** The FAQ warns you can
  destroy the card (`docs/install-lifeline-plan.md:97-99`).
- **Do not reinstall a package under an identity already on the device.** Newton
  rejects same-name reinstalls as "already installed", and `tntk` hardcodes
  version 1 so bumping the version does not help
  (`docs/newton-networking-lessons.md:230`). Use the ZC34 build as-is.
- **Do not stop, restart, or reconfigure `newton-harness_emulator_1`.** Other
  workers are on it. The AP bring-up will already take `10.42.0.1` away from
  them — that is expected and reversible; touching their container is not.
- **If a step fails twice with the same symptom, stop that step and move on.**
  Do not start a debugging round at the bench. Record and go; the offline agent
  session is where debugging is cheap.

## Capture list — evidence, not recollection

Everything here goes into `runtime/evidence/` on mars, named with the date, so
the next agent session works from artefacts.

**Must capture:**

1. **The NS Basic listing** — overlapping photographs, every line, both ends
   legible. This is the session's primary deliverable.
2. **The exact text of every error**, on screen and on the host — including the
   numeric code. The error-code table at
   `docs/newton-networking-lessons.md:72-78` exists because these codes have
   repeatedly meant something other than what they looked like.
3. **`/tmp/dual.log` in full**, copied out at the end of the session. It is the
   only record of what the Newton actually requested.
4. **`iw dev wlan0 station dump`** signal and tx bitrate, once after
   association. Without it no latency number can be interpreted.
5. **A photograph of the Newton screen** at each pass/fail moment — there is no
   screenshot API on real hardware (`docs/hardware-bench-runbook.md:284-285`).
6. **`bench_tools.py` output verbatim**, with the name of the app that was
   actually frontmost written next to the `front_app` result.

**Worth capturing if there is time:**

7. The full Extras drawer, page by page, so the eight loaders are identified by
   title rather than by icon.
8. `runtime/newton_backup.py` enumeration output — the store/soup/entry counts
   are a device inventory we have never had.
9. Rough wall-clock for each step, so the next session can be planned against
   real durations instead of guesses.

## What is unmerged, and must be re-checked before you rely on it

| Step | Depends on | Branch | State at time of writing |
|---|---|---|---|
| 1b | `bootstrap/nsbasic-bootstrap.bas` | `task/nsbasic-bootstrap` | **Nothing committed** — branch is at `4469610`, identical to `master`. Step 1 is written to not need it. |
| 3 | `runtime/newton_backup.py`, `docs/newton-backup-runbook.md` | `task/dock-backup-tcp` | Committed at `8756f3d`, not merged. Offline tests only; never run against hardware. |

Re-run `git log --all --oneline | head -30` before the session and adjust.
