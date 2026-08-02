# Newton TCP Dock soup-export runbook

This is the no-serial-cable path for a MessagePad 2000 running Newton OS 2.1.
The host listens on `10.42.0.1:3679`; the Newton initiates the connection.

## One-time Newton prerequisite: Dock TCP

NIE does not add TCP/IP to the ROM Dock application by itself. If Dock's
connection menu has no **TCP/IP** choice, install the separate English **Dock
TCP/IP 1.2** package first:

```sh
cp downloads/recovery/Dock_TCP-1.2-en.pkg runtime/staging/hardware/install.pkg
python3 runtime/dual_send.py
```

Use ZC40 with `install.pkg`. The verified package is 72,432 bytes with SHA-256
`44bda0598feddb6329ceec5cbc29d1f079d12b8cca23162769cb8470df89b5fa`;
allow at least about 145 KB free for ZC40's VBO and the installation copy.
Install it to internal memory, then reopen Dock and confirm that **TCP/IP** is
present. `Install not confirmed` remains a ZC40 status defect; the Dock menu is
the functional check.

The package comes unchanged from Newton Research's NCX 2.3 distribution. Its
data fork also matches the copies in NCX 1.4 and 3.0.2. It identifies itself as
**Dock TCP/IP 1.2**, package identity `Dock ZC & TCP/IP:Kallisys`.

## Important scope and safety

`runtime/newton_backup.py` is **read-only on the Newton**. Its default mode lists
stores, soups, and entry counts and creates no backup files. `--dump DIRECTORY`
explicitly enables copying every soup entry to the host. Neither mode adds,
changes, or deletes Newton entries.

The resulting directory is a **selective soup export**, not a byte-for-byte or
NCU-restorable full backup. It preserves each entry's raw Newton Streamed Object
Format (NSOF) packet and writes a best-effort JSON rendering. A true NCU-style
backup also tracks package/system data, last-backup state, deleted IDs, and
changed entries. Do not erase or restore the Newton on the strength of this
export alone.

## First run: safe enumeration

1. On the host, confirm the AP address and that port 3679 is free:

   ```sh
   cd ~/git/newton-harness
   ip -brief addr | grep '10.42.0.1/24'
   ss -ltn | grep ':3679' || true
   ```

   On the current Mars + AirPort Express bench, the address is on `enp2s0`.
   Do **not** apply `ap/newton-ap.nft` there: that checked-in ruleset matches the
   separate self-hosted `wlan0` AP topology. Success is `10.42.0.1/24` on the
   active Newton-facing interface and no existing 3679 listener. If the address
   is absent, stop; do not change Newton data or reset the device.

2. On the Newton, open **Dock** from Extras.

3. In Dock, select **TCP/IP**. Do not select Serial or AppleTalk.

4. If Dock asks for the desktop address, enter **`10.42.0.1`**. This is the only
   Newton-side text required. Leave the Newton at the screen with **Connect**;
   do not tap it yet.

5. On the host, run the read-only default mode:

   ```sh
   cd ~/git/newton-harness
   runtime/newton_backup.py
   ```

   Success begins with:

   ```text
   Listening on 10.42.0.1:3679; now tap Connect in Dock on the Newton
   ```

   Failure: `Cannot assign requested address` means `10.42.0.1` is not active on
   the host. `Address already in use` means another process owns port 3679; find
   it with `ss -ltnp | grep 3679` and stop only that process.

6. Tap **Connect** once on the Newton.

   Success: the host prints `Newton connected from ...`, followed by each store
   and lines such as `Notes: 17 entries`. The tool then sends Dock's normal
   disconnect command. The Newton returns from the Dock session without an
   install or restore prompt.

   Failure: `no Newton connected within 60s` means no TCP session reached the
   host. Confirm Dock still says TCP/IP, the desktop address is exactly
   `10.42.0.1`, and run `ss -tn | grep 3679` while tapping Connect. Do not retry
   more than once without recording the exact host error.

## Copy every soup entry to the host

Only after enumeration succeeds, repeat the same Newton steps and run:

```sh
cd ~/git/newton-harness
runtime/newton_backup.py --dump "runtime/backups/messagepad-$(date +%Y%m%d-%H%M%S)"
```

The command refuses to use a directory that already exists, preventing an earlier attempt from being overwritten. Success ends with `Soup export written to ...`. The directory contains:

- `manifest.json`: stores, soup names, signatures, listed counts, and received counts.
- `NN-store/NN-soup/000001.nsof`: the exact raw NSOF entry payload received from the Newton.
- `NN-store/NN-soup/000001.json`: a readable rendering when the entry uses supported NSOF types.

Verify the copy before doing anything experimental:

```sh
find runtime/backups/messagepad-* -name '*.nsof' | wc -l
sha256sum runtime/backups/messagepad-*/manifest.json
```

A warning such as `listed 17, received 16` means the export is incomplete. Keep
all files, record the warning, and retry once into a **new** timestamped
directory. Never overwrite the first attempt.

## Protocol basis and limits

The script uses the documented old synchronize-session handshake already proven
by `runtime/install-newton-tcp` and vendored UnixNPI:

1. Newton sends `rtdk`; desktop sends `dock` with synchronize session type `2`.
2. Newton sends `name`; desktop sends `stim`; Newton returns `dres`.
3. Desktop sends `gsto`; Newton returns `stor` (store frames).
4. For each store, desktop sends `ssto`, then `gets`; Newton returns `soup`
   (parallel arrays of soup names and signatures).
5. For each soup, desktop sends `ssou`, then `gids`; Newton returns `sids`, whose
   leading 32-bit value is the entry count.
6. With `--dump`, desktop sends `snds`; Newton streams `entr` packets and ends
   with `bsdn`.

### Sources

- The community Dock protocol reference documents the session preamble, store
  and soup commands, `sids` layout, and says `snds` returns every current-soup
  entry followed by `bsdn`:
  <https://40hz.org/Pages/newton/hacking/newton-docking-protocol/>.
- NewtonKit independently defines the same command codes and implements
  `ssgn`/`ssgi`/`snds` backup traversal in
  `Sources/NewtonDock/DockCommand.swift` and `DockBackupLayer.swift`:
  <https://github.com/turbolent/NewtonKit>.
- RDCL implements the old read/export sequence (`gsto`, `ssto`, `gets`, `ssou`,
  `gids`, `snds`) in `link/dock_modules/storage_dock_module.rb`:
  <https://github.com/ekoeppen/RDCL>.
- DCL is a second independent implementation and defines `gsto`, `gets`,
  `gids`, `bksp`, and `bsdn` in
  `DCL/Link/Dock_Commands/TDCLDockCommand.h`:
  <https://github.com/pguyot/DCL>.
- In this repository, `runtime/unixnpi/unixnpi.c` and
  `runtime/install-newton-tcp` verify the `newtdock` framing, 4-byte padding,
  host-listens/Newton-connects direction, and old-session handshake.

### Full backup versus this export

`bksp` is the incremental backup command: it uses the previous backup/sync time
and last unique ID, sends changed `entr` records, compressed `bids` lists for
unchanged IDs (so deletions can be detected), optional `base` offsets, and then
`bsdn`; `ndir` means the soup was unchanged. That metadata only becomes a safe,
restorable backup when combined with package/system backup data and a persistent
backup catalog. This tool deliberately uses `snds` instead: it copies all
currently present entries and does not claim restore compatibility.

## Emulator status

Offline synthetic Dock exchanges cover framing, NSOF store/soup parsing,
read-only enumeration, and raw-entry export in `test_newton_backup.py`. The
running Einstein emulator was healthy, but an end-to-end TCP/IP Dock run was not
completed: its FLTK external Dock transport is configured as a TCP **serial**
client to `127.0.0.1:3679` inside the container, while the required test is the
Newton OS TCP/IP Dock path to the host listener. No emulator network, ROM, or
flash configuration was changed to manufacture a misleading pass. Physical
MP2000 TCP/IP Dock compatibility remains the required final verification.
