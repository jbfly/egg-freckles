# Install lifeline plan — never hand-type a bootstrap again

Research date 2026-07-31. Nothing here was tested on hardware: Mars is offline
and the Newton is not with the human. Every claim is marked **verified** (a
source or a file in this repo says so) or **inferred** (my reasoning from
those facts). Section 6 lists what only hardware can settle.

## Bottom line

**Newt's Cape does what you hoped — but it is not the lifeline.** It really can
install a `.pkg` from a URL, and the unexpiring build is legitimately free.
What it cannot do is get you off bare metal, because it is a 296 KB package
that runs on top of the Newton Internet Enabler, and neither Newt's Cape nor
NIE is in the MP2000 ROM. After a hard reset you would need to install five
packages before you could use it to install anything. It is a **convenience
layer**, and a good one — it is the right replacement for typing into the NS
Basic demo slot — but it is not a recovery path.

The recovery path you actually already own is the **serial Dock**. The Dock
application is in the MP2000 ROM, needs no package installed, survives a hard
reset by definition, and costs **zero typed characters** on the Newton — it is
three taps. This repo already contains the host side of it
(`runtime/install-newton-serial`, wrapping a vendored UnixNPI). It has never
been run against the physical Newton.

Recommendation: **primary = serial Dock; fallback = a PCMCIA storage card
carrying the recovery package set.** Both survive a hard reset and fail for
unrelated reasons (a cable/adapter chain vs. a card). They are not perfectly
independent, and section 5 is honest about exactly where they touch.

## 1. Newt's Cape: the facts

| Question | Answer | Evidence |
|---|---|---|
| Can it install `.pkg` from an HTTP URL? | **Yes.** | "You can download a package to the Newton if the URL ends with .pkg, and its MIME type matches current (evolving) package conventions -- preferably `application/x-newton-compatible-pkg`; however, several other types will work… After downloading, you can confirm if you want to replace and/or install it immediately, or add to Inbox (default store) for later." <https://communicrossings.com/html/newton/newtscape/docs/setup.htm> |
| Is a non-demo build obtainable? | **Yes, and free.** | "24 Apr 2018: Newt's Cape is now freeware -- for all users (not just formerly registered users). this page includes unexpiring versions of Newt's Cape… the password for the .zip archive files is: `turkeylurky` (not needed for .pkg)" <https://communicrossings.com/html/newton/regnewtscape.htm> |
| What is the demo restriction? | A 45-day expiry, not a feature lock. | "This version expires 45 days after installation" — <https://communicrossings.com/html/newton/newtscape.htm> |
| Is package download gated on registration? | **No.** The setup docs describe it with no registration condition; only the Graphic Converter tool is called out as registered-users-only. | setup.htm, as above |
| Which build do we want? | `regnewtscape/pkg/nwcp21e2.pkg` — the unexpiring one. | See below |

**The two builds are genuinely different files**, which is the strongest
evidence that the freeware one is not just the beta relabelled. Verified by
HTTP HEAD on 2026-07-31:

| URL | Bytes | Which |
|---|---:|---|
| `https://communicrossings.com/html/newton/regnewtscape/pkg/nwcp21e2.pkg` | 296,128 | **unexpiring — take this one** |
| `https://communicrossings.com/html/newton/newtscape/pkg/nwcp21e2.pkg` | 297,220 | expiring 45-day public beta |
| `https://communicrossings.com/html/newton/regnewtscape/DOS/nwcp21e2.zip` | 152,357 | same, zipped, password `turkeylurky` |

Both returned HTTP 200 with `last-modified: Sun, 24 Mar 2013`. The site is
Drupal-fronted and the `/html/newton/` prefix matters — the bare
`/newtscape/pkg/…` paths 404.

Version 2.1e-2 is NewtonOS 2.x only, which is what we have.
(<https://communicrossings.com/html/newton/newtscape.htm>) Source is mirrored
at <https://github.com/saweyer/newtscape>, which points back to
communicrossings for the binaries.

**Where the premise breaks.** Newt's Cape needs NIE. Its own setup page lists
"install Newton Internet Enabler (NIE)" as a prerequisite, and NIE is not in
the MP2000/2100 ROM — it is four separate packages
(`Enetsup.pkg`, `Inetenbl.pkg`, `Newtdev.pkg`, `Inetstup.pkg`), plus a card
driver. Verified: "Ethernet connectivity requires version 2.0 of the Newton
Internet Enabler… NOTE: The four packages mentioned below are required no
matter what type of Ethernet card you plan to use."
(<https://archive.org/details/newton_ethernet_drivers>) That matches this
repo's own staging list in `docs/hardware-bench-runbook.md:31-40`.

So the chain to a working Newt's Cape from bare metal is: 4 NIE packages +
WaveLAN driver + Newt's Cape = **6 packages, ~600 KB**, all of which must
arrive by some *other* mechanism. Newt's Cape cannot bootstrap itself. That is
the whole reason it is demoted below.

## 2. The alternatives, honestly compared

Ranked by what they cost you at 3am on a bricked device.

### a. Serial Dock (ROM) — `runtime/install-newton-serial`
The MP2000 ROM's Dock application speaks the package-upload protocol over
serial with **nothing installed on the Newton**. Host side is already in this
repo: `runtime/install-newton-serial` compiles and runs a vendored UnixNPI
against `/dev/ttyUSB0`. Newton-side interaction is Dock → Serial → 38400 →
Connect: taps only, **0 characters typed**. Procedure is
`docs/hardware-bench-runbook.md:204-251`.
Survives hard reset: **yes, trivially** — it is ROM.
Hardware dependency: an InterConnect cable that actually exposes the serial
pins, a DIN-to-DB adapter, and an FTDI FT232R (`0403:6001`). We own an FTDI
and a PL2303; the runbook itself flags the InterConnect piece as unverified
("If the InterConnect piece is ambiguous, describe or photograph both ends
before proceeding; a power/dock-only cable will not work" — line 210).
**Never run against the physical Newton.** Commit `cee15bb` added it; no
evidence file records a hardware run.

### b. PCMCIA storage card holding the recovery set
A hard reset erases internal store only. "This hard reset WILL ERASE
EVERYTHING ON YOUR NEWTON… Before you perform a hard reset, first remove all
PCMCIA cards from the Newton (this is _really_ important, otherwise you may
destroy the card!)" (<http://old.chuma.org/newton/faq/newton-faq-nos.html>).
Packages on a card reactivate on insertion — the FAQ's entry "How do I stop
packages from activating when I insert a storage card?" presupposes that they
do (<http://newtonfaq.com/newton-faq-nos.html>).
Survives hard reset: **yes**, and it needs no host, no cable, no software.
**0 characters typed.**
**The catch, and it is a real one:** "Some of the packages are copy protected
and will therefore refuse to install on a PCMCIA card. For the same reason you
will not be able to 'beam' them from one Newton to another or file them on a
PCMCIA card once you have installed them on the Newton's Internal Storage."
(<https://archive.org/details/newton_ethernet_drivers>) That sentence is
specifically about the Apple NIE quartet. If it holds, a card can carry our
own packages, the WaveLAN driver and Newt's Cape, but **not** NIE — so the
card alone cannot restore networking. This is the single biggest unknown in
this document.
Hardware dependency: a Newton-compatible **linear** flash or SRAM card. Modern
ATA/CF cards do not work without an ATA driver, which is itself a package
(<https://www.reddit.com/r/VintageApple/comments/qti8g2/>). I found no
evidence in this repo that we own such a card.

### c. TCP Dock — `runtime/install-newton-tcp`
Same ROM Dock protocol over TCP; host listens on `10.42.0.1:3679` and the
Newton initiates. The ROM Dock app still needs the separate Dock TCP transport
package after NIE is installed; NIE alone does not create the TCP/IP menu item.
The verified recovery copy is `downloads/recovery/Dock_TCP-1.2-en.pkg`, 72,432
bytes, SHA-256
`44bda0598feddb6329ceec5cbc29d1f079d12b8cca23162769cb8470df89b5fa`.
Documented and coded
(`docs/hardware-bench-runbook.md:144-201`, commit `c5d2852`).
Survives hard reset: **no.** This path is unavailable until both NIE and Dock
TCP are reinstalled by another path. Typing once they are up: the desktop
address `10.42.0.1` = **9 characters**, plus SSID `newton` = 6 during network
setup.
Verdict: an excellent *steady-state* path, useless as a lifeline.

### d. Our own `harness-loader.pkg` (10,552 bytes)
A Newton-side package that fetches a fixed URL over HTTP and installs the
result. Proven working: round 14g passed all three gates, including the exact
72-byte request `GET /harness-client.pkg HTTP/1.0` and a visible
"Harness Client install queued" (`docs/newton-dev-notes.md:573-587`).
Typing: **0** — it is one button, the URL is compiled in.
Survives hard reset: **no** — it is a package, and it needs NIE besides.
Verdict: this is the thing worth *protecting*, not the thing that protects
you. Note it is 28× smaller than Newt's Cape and already does the same job for
the one URL we care about; Newt's Cape's advantage over it is that you can
type an *arbitrary* URL, which matters exactly when the loader is the thing
that broke.

### e. NS Basic demo slot (today's path)
Works, survives soft reset, dies on hard reset or an overwritten demo slot —
which has already happened once.
Typing: the entire bootstrap program, by hand, on a 1997 touchscreen.
**I cannot give you a character count, because the bootstrap source is not in
this repository.** I grepped the whole tree; the only `nsbasic` hits are an
unrelated emulator compose profile (then in `README.md`, now
`docs/dev-harness.md`, "Agent screen and input control"). Whatever you typed
last time exists only on the device and in your memory. Fixing that costs
nothing and is the first action item below.

### f. Things I checked and am ruling out
- **Beaming from a second Newton.** Requires a second Newton we do not have,
  and the copy-protection note above says the NIE packages cannot be beamed
  anyway.
- **NCU / Newton Connection 3.0.** Real and working in 2025
  (<https://tow.com/2025/02/10/getting-the-newton-messagepad-2000-and-2100-to-work-in-2025/>),
  but it is Mac software over the same serial link — strictly more moving
  parts than option (a) for the same result on the same cable.
- **`lpkg`, `newtl`.** Alternative host-side serial uploaders from UNNA
  (`docs/unna-survey.md:26-27`). Same transport as (a); `lpkg`'s own README
  warns its incomplete MNP handling can hang. Worth keeping as spare tyres,
  not as a second path.
- **Restoring an Einstein flash image to the hardware.** Not possible; the
  emulator's 8 MB flash file has no path onto the physical device.

## 3. Typing cost — the decision metric

Characters the human must enter on the Newton screen. Taps are not characters.

| Path | From bare metal after hard reset | In steady state | Survives hard reset |
|---|---:|---:|:--:|
| Serial Dock | **0** | 0 | ✅ ROM |
| PCMCIA card | **0** | 0 | ✅ card is external |
| TCP Dock | n/a (needs NIE) | 9 (`10.42.0.1`) | ❌ |
| `harness-loader.pkg` | n/a (needs NIE + itself) | 0 | ❌ |
| Newt's Cape | n/a (needs NIE + itself) | 15–41 per URL, 0 from a bookmark | ❌ |
| NS Basic bootstrap | whole program, hundreds–thousands (**uncounted, source lost**) | — | ❌ |

Newt's Cape URL lengths: `http://10.42.0.1:18081/harness-client.pkg` is 41
characters. If Mars also listens on port 80 and serves a one-letter path,
`10.42.0.1/l.pkg` is **15** — a two-thirds cut for a few lines of host-side
change. Whether Newt's Cape accepts a URL with no `http://` prefix is
**inferred**, not verified; assume 22 characters (`http://10.42.0.1/l.pkg`) if
it does not. Bookmarks make repeat fetches free but die with the internal
store, so they never help recovery.

The honest reading of this table: **the two zero-typing options are the only
ones that matter for recovery, and everything else is quality-of-life.**

## 4. Recommendation

**Primary lifeline: the serial Dock.** It is the only mechanism that takes a
bare-metal MP2000 back to installing packages with zero typing and zero
prerequisites, because it lives in ROM. The host half is already written and
committed. What it needs is one afternoon of hardware time to prove the cable
chain, and a photograph of the working setup so it is never ambiguous again.

**Independent fallback: a PCMCIA linear-flash card carrying the recovery set.**
It depends on no cable, no adapter, no host machine and no host software — a
completely different failure mode from the serial chain. Load it with
everything the copy protection permits: the WaveLAN driver,
`harness-loader.pkg`, `harness-tools.pkg`, and Newt's Cape 2.1e-2 unexpiring.

**Newt's Cape: install it, but as the third layer.** It is free, unexpiring,
documented to install `.pkg` from a URL, and it directly kills the reason you
were typing into NS Basic — an arbitrary URL you can retype beats a fixed URL
compiled into a package you would have to rebuild. Just do not let it be
mistaken for the safety net.

**Retire the NS Basic demo slot as a lifeline** once serial is proven. Keep it
only as a live-but-degraded third option, and only if its source is in git.

## 5. Where the two paths are not independent — read this before trusting it

If the copy-protection claim in section 2b is true, the NIE quartet cannot
live on the card. In that case:

- Serial can restore **everything**, including NIE.
- The card can restore **everything except NIE**.

So a card-only recovery leaves you with a Newton that runs our packages but
has no network — which is a much better place than today, but is not full
parity. The two paths therefore share one dependency: **restoring networking
requires serial.** I am flagging this rather than papering over it, because it
is the difference between "defence in depth" and "one and a half paths".

If the claim turns out to be false, or applies only to some of the four, the
card becomes a complete standalone lifeline and should be promoted to
co-primary. **This is one hardware test.** See section 6.

## 6. Needs hardware to verify — nothing below was or could be tested today

Ordered by how much the answer changes the plan.

1. **Can `Inetenbl.pkg`, `Enetsup.pkg`, `Newtdev.pkg` and `Inetstup.pkg` be
   installed onto a PCMCIA card?** Decides whether the fallback is complete or
   partial. Test: with a card inserted, set the install destination to the
   card and install each; record which refuse and the exact error. **The
   single biggest unknown in this document.**
2. **Does the InterConnect cable we own actually expose serial?** Decides
   whether the primary lifeline exists at all. Test: the runbook's step 5
   (`docs/hardware-bench-runbook.md:232-243`) — success is byte counts
   reaching `10552 / 10552` and `Finished!!`. Photograph both cable ends
   either way.
3. **Do we own a Newton-compatible linear flash/SRAM card, and how large?**
   The recovery set is roughly 600 KB with Newt's Cape; a 2 MB card is ample,
   an ATA/CF card is useless without a driver.
4. **Does the unexpiring Newt's Cape (296,128 bytes) install and run, and does
   its `.pkg` download actually fire against Mars?** Serve it with the correct
   `application/x-newton-compatible-pkg` MIME type — `runtime/raw_pkg_server.py`
   would need checking, I did not read its content-type handling.
5. **Does Newt's Cape accept a bare `10.42.0.1/l.pkg` with no scheme?** Worth
   26 characters of typing per recovery.
6. **Does `tntk`'s hardcoded package version 1 bite on the real device?**
   `docs/newton-dev-notes.md:647-650` records that Newton rejects same-name
   reinstalls as "already installed" on the emulator. On hardware this turns
   every reinstall into a remove-then-install, which the runbook already warns
   about (line 253).

## 7. Recovery runbook — bare metal to installing packages

### Step 0 — do this now, before any hardware time (costs nothing, offline)

1. **Type the NS Basic bootstrap into a file and commit it.** It is currently
   unrecoverable outside the device. `docs/nsbasic-bootstrap.bas`, verbatim,
   even if ugly. If a hard reset happens before serial is proven, this file is
   the whole difference between an afternoon and a disaster.
2. **Download and check in the recovery set** so it does not depend on a
   30-year-old website staying up:
   - `https://communicrossings.com/html/newton/regnewtscape/pkg/nwcp21e2.pkg`
     (296,128 bytes — the unexpiring one, *not* the `newtscape/` path)
   - the NIE quartet and WaveLAN driver from
     <https://archive.org/details/newton_ethernet_drivers>
   Record SHA-256 for each alongside the existing `SHA256SUMS` in
   `runtime/staging/hardware/`.
3. **Serve short URLs.** Add a port-80 listener on Mars mapping `/l.pkg` to
   the loader. Cuts recovery typing from 41 characters to 15.

### Step 1 — bare metal, first minutes (0 characters typed)

The Newton has just been hard-reset. Cards are out (remove them *before* the
reset — the FAQ warns you can destroy a card otherwise).

1. Work through the ROM setup assistant. Handwriting, taps, no free text
   beyond what it forces.
2. **If the card exists:** insert it. Packages activate on insertion. You now
   have `harness-loader.pkg`, `harness-tools.pkg`, the WaveLAN driver and
   Newt's Cape without touching a keyboard. Skip to step 3.
3. **Otherwise, or to restore NIE:** Dock → Serial → 38400 → Connect. On Mars:

   ```sh
   cd ~/git/newton-harness
   runtime/install-newton-serial runtime/staging/hardware/inetenbl.pkg /dev/ttyUSB0
   ```

   Repeat per package, in this order: `enetsup`, `inetenbl`, `newtdev`,
   `inetstup`, WaveLAN driver, `nwcp21e2` (Newt's Cape), `harness-loader`,
   `harness-tools`. Dock returns to its waiting screen between packages.
   Expect roughly two minutes for the 296 KB Newt's Cape at 38400 baud
   (**inferred** from the line rate, not measured).

Character count so far: **0**.

### Step 2 — network back up (15 characters)

Bring the AP up on Mars (`sudo ap/apply.sh`, per
`docs/hardware-bench-runbook.md:68-87`). On the Newton: WaveLAN settings →
SSID **`newton`** (6 characters), encryption None. Internet Setup → DHCP, no
proxy.

Confirm from the host with `hostapd_cli … all_sta` and the dnsmasq leases,
per runbook step 4.

### Step 3 — installing packages again (0–15 characters)

Three ways, in preference order:

1. **`harness-loader.pkg`** — open it, tap fetch. 0 characters. Only works for
   the URL compiled into it.
2. **Newt's Cape** — open, type `10.42.0.1/l.pkg` (15 characters, or 22 with
   the scheme), confirm the install prompt. Works for *any* URL, which is what
   you want when the loader is the broken thing.
3. **TCP Dock** — Dock → TCP/IP → desktop `10.42.0.1` (9 characters), tap
   Connect, and run `runtime/install-newton-tcp <pkg>` on Mars. Needs port
   3679 open in the nft table (`sudo nft -f ap/newton-ap.nft`).

### Step 4 — re-arm the lifeline before you put the Newton down

This is the step that stops it happening a third time.

1. Rebuild the card if it was consumed or was not there: install the recovery
   set onto the card, verify each package appears in Extras with the card as
   its store, and eject/reinsert to confirm it reactivates.
2. Confirm serial still works with one throwaway package.
3. Note in `docs/newton-dev-notes.md` what the device is carrying and where.

A device is only safe when **both** the card and the serial cable have been
demonstrated on that device since its last reset. Neither is a lifeline until
it has been used once.

## Sources

- Newt's Cape setup and `.pkg` download behaviour — <https://communicrossings.com/html/newton/newtscape/docs/setup.htm>
- Newt's Cape versions and 45-day demo expiry — <https://communicrossings.com/html/newton/newtscape.htm>
- Freeware announcement and unexpiring downloads — <https://communicrossings.com/html/newton/regnewtscape.htm>
- Newt's Cape source mirror — <https://github.com/saweyer/newtscape>
- NIE package requirements, install order, and PCMCIA copy protection — <https://archive.org/details/newton_ethernet_drivers>
- Hard reset scope and card removal warning — <http://old.chuma.org/newton/faq/newton-faq-nos.html>
- Package activation on card insertion — <http://newtonfaq.com/newton-faq-nos.html>
- MP2000/2100 in 2025, Newton Connection 3.0 over serial — <https://tow.com/2025/02/10/getting-the-newton-messagepad-2000-and-2100-to-work-in-2025/>
- ATA/CF cards need a driver — <https://www.reddit.com/r/VintageApple/comments/qti8g2/newton_messagepad_2100_transferring_files/>
- Newton docking protocol reference — <https://40hz.org/Pages/newton/hacking/newton-docking-protocol/>
- UnixNPI and `lpkg` sources — <https://www.unna.org/unna/unix/unixnpi-1.1.3.tar.gz>, <https://www.unna.org/unna/unix/lpkg.tar.gz>

In-repo: `docs/hardware-bench-runbook.md`, `docs/unna-survey.md`,
`docs/newton-dev-notes.md`, `runtime/install-newton-serial`,
`runtime/install-newton-tcp`.
