# Real-hardware bench runbook

Step-by-step for benching the harness tool surface on a physical Newton
(MP2000/2100 + WaveLAN card) instead of Einstein. The question this run
answers: **is the per-call latency on real hardware over WiFi usable, or does
it confirm that the emulator's 5.8–11.5 s is a floor?**

Everything here is runtime-only. Nothing installs to `/etc`; a reboot or
`ap/teardown.sh` returns the machine to its previous state.

## Before you start — the one destructive fact

Bringing the AP up **moves `10.42.0.1` from loopback to wlan0**. Einstein
binds that address too, so **the emulator work stops the moment you run
`apply.sh`**. Do not start this while an emulator spike is running. That is
the whole reason this is gated on you rather than automated.

Reverting is one command (`sudo ap/emulator-only.sh` after teardown), so the
cost of a wrong call is a couple of minutes, not a rebuild.

## What is already prepared

| Item | Where | State |
|---|---|---|
| Packages to install on the Newton | `runtime/staging/hardware/` | staged, `SHA256SUMS` verified |
| Preflight checker | `ap/hardware-preflight.sh` | written, runs clean |
| AP bring-up / teardown | `ap/apply.sh`, `ap/teardown.sh` | existing, NOPASSWD via sudoers |
| Package server | `runtime/dual_send.py` | serves bootstrap + named packages on all interfaces, port `18081` |
| Latency bench | `runtime/bench_tools.py` | written, see step 6 |

Staged packages, in install order:

| Package | Purpose |
|---|---|
| `newtdev.pkg`, `enetsup.pkg` | Newton Devices + Ethernet support (NIE prerequisites) |
| `inetenbl.pkg` | Internet Enabler — the NIE stack itself |
| `inetstup.pkg` | Internet Setup — where you configure the WaveLAN + DHCP |
| `harness-tools.pkg` | `HarnessToolsR10I:jbfly`, the non-blocking persistent long-poll tool surface under test |
| `harness-loader.pkg` | over-the-air updater, optional |
| `harness-client.pkg` | chat client, optional |

**The WaveLAN/Noguchi driver is NOT in this repo.** It ships with the card or
comes from UNNA. Install it on the Newton before anything else, or the card
will not appear in Internet Setup. This is the most likely thing to block the
run — check it first.

## Step 1 — Confirm nothing is mid-flight

```sh
cd ~/git/newton-harness
git status --porcelain          # expect clean
ss -tlnp | grep 18081           # expect raw_pkg_server.py only
```

If an emulator spike is running, stop here and wait for it.

## Step 2 — Preflight (read-only, safe any time)

```sh
./ap/hardware-preflight.sh
```

Expect FAILs on `wlan0 beaconing` and `10.42.0.1 on wlan0` — that is normal
before bring-up and is exactly what step 3 fixes. Everything else should be
`ok`.

## Step 3 — Bring the AP up

```sh
sudo ap/emulator-only.sh down     # release 10.42.0.1 from loopback FIRST
sudo ap/apply.sh
./ap/hardware-preflight.sh        # now expect all ok, exit 0
```

`apply.sh` disconnects wlan0 from the house uplink, marks it unmanaged in
NetworkManager (via a conf.d drop-in that survives the AX200 re-enumerating),
sets `10.42.0.1/24`, loads the nftables isolation table, and starts
dnsmasq + hostapd. It self-verifies the radio and exits nonzero if it is not
actually beaconing.

If it fails with a firmware reset:

```sh
sudo modprobe -r iwlmvm iwlwifi; sleep 2; sudo modprobe iwlwifi
sudo ap/apply.sh
```

## Step 4 — Associate the Newton

On the Newton: WaveLAN driver settings → SSID `newton`, encryption
**None/Open**. Internet Setup → obtain IP automatically (DHCP), no proxy.

Confirm from the host:

```sh
sudo hostapd_cli -p /run/newton-ap/hostapd all_sta   # the Newton's MAC
cat /run/newton-ap/dnsmasq.leases                    # its 10.42.0.10–.50 lease
iw dev wlan0 station dump | grep -E 'Station|signal|tx bitrate'
```

**Record the signal strength and tx bitrate.** At 1–2 Mb/s on 802.11b, the
radio itself contributes real latency, and you need that number to interpret
the benchmark honestly.

## Step 4b — Quick network test (STOP HERE on the first session)

Before installing anything, prove the radio path end to end. This is the
decision point for whether the AX200 suffices or you need the vintage AP.

On the Newton, in NetHopper/Newtscape or Nettest, fetch:

```
http://10.42.0.1:18081/harness-client.pkg
```

On the host, watch it arrive:

```sh
ss -tn | grep 10.42.0                       # the Newton's connection
tail -f /run/newton-ap/dnsmasq.leases       # its lease
```

Pass = the download starts and the host sees the connection from a
`10.42.0.10-.50` address. Also record `iw dev wlan0 station dump` signal and
tx bitrate. If association is flaky, drops, or the AX200 logs firmware resets
(`dmesg | grep -c "SW reset"`), that is the signal to switch to the AirPort
base station or another 802.11b router on the same `10.42.0.1/24` plan --
nothing else in this runbook changes, only which box beacons.

## Step 5 — Install any package over WiFi/Ethernet

This is the preferred no-cable path. Pass the unattended Einstein command below
before touching hardware, then treat the physical MP2000 as a separate gate.
Einstein's patched NIE stack can differ from the WaveLAN/NIE stack in link
acquisition, callback timing, buffering, and timeouts.

### Host: stage one arbitrary package under the zero-typing alias

`install.pkg` is only a filename alias; it does not alter the package's internal
identity. Never install a second build with an identity already present on the
Newton.

```sh
cd ~/git/newton-harness
cp -- /absolute/path/to/ANY-PACKAGE.pkg runtime/staging/hardware/install.pkg
sha256sum /absolute/path/to/ANY-PACKAGE.pkg runtime/staging/hardware/install.pkg
python3 runtime/dual_send.py
```

Leave that terminal running. **ZC40 is current** and is hardcoded to the
dedicated Mars AP at **`[10,42,0,1,18081]`**. Keep the checked-in
`harness-loader-zc39.pkg` unchanged as the fallback; do not rebuild either
identity to stage an arbitrary payload.

### Newton: one-time loader upgrade, then two taps per package

1. Open **ZC40 Loader 2.4** from Extras. If ZC40 has been lost but ZC39 remains,
   use **ZC39 Loader 2.3** only to restore the checked-in
   `harness-loader-zc40.pkg`; the identities are distinct.
2. Confirm the filename is **`install.pkg`**, join the dedicated Mars network,
   and tap **Install**.
3. Wait for installation to return, then check Extras. `Install not confirmed`
   is a faulty ZC40 status check, not evidence of failure.
4. Open the new application from Extras and exercise one real action. That is
   the hardware confirmation gate. Current Harness Client A3 appears as **Chat
   A3** and opens with the title **Newton Chat 2.3-a3**. The A1 fallback appears
   only as **Newton Chat** and opens with the title **Newton Chat 2.1-a1**.
   Record the exact status, package identity, byte size, and whether the app
   opened; do not infer hardware success from the emulator result.

The hardware gate passed. ZC40 installed and launched fresh 1,136-byte and
321,920-byte proof packages over WiFi. For the large success Mars saw one GET
and ACKs for all 322,003 HTTP response bytes. A prior attempt reached the
installer but returned `-10617` (card memory full) with 498 KB free; the same
package succeeded after increasing free space on `Ultimate Newton` to 893 KB.
Budget roughly twice the package size for the download VBO and installation
copy. `Install not confirmed` remains a faulty post-install status check and
does not override an app appearing in Extras and launching.

Harness Client A1 also passed the physical WiFi gate on 2026-08-02. Newton Chat
2.1-a1 connected from `10.42.0.114` to the real Mars backend at
`10.42.0.1:6801`, sent `Hi`, and rendered the Codex response. If a persisted
Codex thread can no longer be resumed, tap the client's **New** button before
retrying; this resets host conversation state without Newton-side typing or a
package reinstall. A1 renders a blank `Agent:` line after that host error, so
confirm the cause in the Mars server log rather than treating it as a network
failure; A3 retains the error in the transcript.

Harness Client A3 passed its physical UI gate on 2026-08-02. ZC40 installed the
fresh 19,184-byte `HarnessClientA3:jbfly` package after one HTTP 200; Mars saw
all 19,266 HTTP bytes acknowledged. Its four-line handwriting field and compact
control row worked substantially better on the MP2000, and opening it created a
live connection from `10.42.0.114` to Mars port 6801. Keep A1 installed as the
fallback.

For the 318,276-byte recovery package, use the same alias:

```sh
cp runtime/staging/hardware/inetenbl.pkg runtime/staging/hardware/install.pkg
python3 runtime/dual_send.py
```

Do this only if that NIE identity is not already installed. A duplicate-package
error is not a transfer failure, but it is also not a successful install.

### Preserve and install Newt's Cape

The recovery convenience layer is the pinned **freeware/unexpiring** Newt's
Cape 2.1e-2 build, not the 45-day demo. Its verified file is 296,128 bytes with
SHA-256 `300c00a291e903e72a8b82749d1427b8f622990b505c4eb11c4a540a8670c611`.
Allow at least about 600 KB free for ZC40's VBO plus the installation copy.

```sh
sha256sum runtime/staging/hardware/nwcp21e2.pkg
cp runtime/staging/hardware/nwcp21e2.pkg runtime/staging/hardware/install.pkg
python3 runtime/dual_send.py
```

Use ZC40 as above, then open **Newt's Cape** from Extras. On 2026-08-02 the
same pinned file was absent from an isolated Einstein flash, installed as
`NewtsCape:NewtsCape` at 296,128 bytes, and opened to its About screen. The
physical MP2000 remains the separate confirmation gate.

### Unattended emulator proof

With the emulator healthy and `10.42.0.1/24` assigned to loopback:

```sh
sudo ap/emulator-only.sh
runtime/test_wifi_install.py
```

The script creates a fresh package identity every run, builds a valid package
larger than `inetenbl.pkg`, stages it under a random filename, fetches it through
`dual_send.py`, confirms it with `GetPkgRef`, opens it, and requires its `Proof()`
method to return `wifi-install-ok`. It is intentionally not in the normal pytest
suite because it requires a live emulator, NIE state, host networking, and the
Newton toolchain.

### TCP Dock bootstrap (current no-cable path)

This uses the Newton OS 2.x ROM Dock protocol's old package-loading session,
so it needs no loader or installer package on the Newton. The **host listens on
`10.42.0.1:3679` and the Newton initiates the TCP connection** when you tap
Connect. Do not try to connect from the host to `10.42.0.36`. The sequence is
the documented `rtdk` / `dock(loadPackage)` / `name` / `stim` / `dres` /
`lpkg` / `dres` / `disc` exchange:
<https://40hz.org/Pages/newton/hacking/newton-docking-protocol/>. NewtonKit
independently uses the same direction and port: its host starts a server on
3679, then the Newton Dock app initiates the TCP/IP connection:
<https://github.com/turbolent/NewtonKit#tcp>.

1. **Allow Dock traffic through the already-running AP firewall.** The checked-in
   `ap/newton-ap.nft` adds `3679` to the existing Newton-only TCP allowlist.
   Apply that prepared ruleset; this does not reset the Newton or stop the
   package server:

   ```sh
   cd ~/git/newton-harness
   sudo nft -f ap/newton-ap.nft
   sudo nft list chain inet newton-ap input | grep 3679
   ```

   Expect the second command to show `tcp dport { 3679, 6801, 18081 } accept`.
2. **Prepare Dock, but do not tap Connect yet.** On the Newton, open **Dock**.
   Choose **TCP/IP** (the network transport; not Serial and not AppleTalk). If
   Dock asks for the desktop address, enter **`10.42.0.1`**.
3. **Start the one host command:**

   ```sh
   cd ~/git/newton-harness
   runtime/install-newton-tcp runtime/staging/hardware/harness-loader.pkg
   ```

   It must print `Listening on 10.42.0.1:3679; now tap Connect in Dock on the
   Newton`. Leave it running.
4. **Now tap Connect on the Newton.** Expected host output is:

   ```text
   Newton connected from 10.42.0.36:<ephemeral-port>
   Sending 10552 bytes from runtime/staging/hardware/harness-loader.pkg
   Package installed; Dock session closed
   ```

   The Newton should show its normal package-install progress and then return
   from Dock. To send the larger proof-of-life package instead, use the same
   command with `runtime/staging/hardware/harness-tools.pkg`; expected size is
   `18320` bytes.

Top three TCP Dock failures:

| Symptom | Fix |
|---|---|
| `no Newton connected within 60s` | Confirm the Newton still has `10.42.0.36`, Dock is set to **TCP/IP** with desktop `10.42.0.1`, and the live nft rule includes 3679. Run `ss -tn | grep 3679` while tapping Connect; no row means the connection never reached the host. |
| `Address already in use` or `Cannot assign requested address` | For the first, find the unexpected listener with `ss -ltnp | grep 3679` and stop only that process. For the second, the AP address is missing; `ip addr show wlan0 | grep 10.42.0.1` must succeed before retrying. |
| `Newton rejected package install with Dock error ...` | Keep Dock open and retry once with the staged package. Error `-28019` means the package cannot load: remove an older package with the same identity or free Newton store space, then retry. Other codes should be recorded verbatim rather than resetting the device. |

### Serial bootstrap (works with no Newton-side loader)

Use the ROM's built-in Dock application when HTTP installation is unavailable.
No package needs to be installed on the Newton first.

1. **Cable it without resetting the Newton.** Connect the MP2000 InterConnect
   port to an InterConnect adapter/cable that actually exposes the Newton
   serial pins, then through the DIN-to-DB serial adapter to the USB serial
   adapter and host. If the InterConnect piece is ambiguous, describe or
   photograph both ends before proceeding; a power/dock-only cable will not
   work.
2. **Use the FTDI FT232R, not the currently attached CP2102.** Plug in only the
   FTDI adapter (`0403:6001`) and identify its device:

   ```sh
   for d in /dev/ttyUSB*; do
     echo "$d $(udevadm info -q property -n "$d" | grep -E '^(ID_VENDOR_ID|ID_MODEL_ID)=')"
   done
   ```

   Expect one device with `ID_VENDOR_ID=0403` and `ID_MODEL_ID=6001`, normally
   `/dev/ttyUSB0`. Use the PL2303 (`067b:2303`) only if the FTDI fails.
3. **Check access before using the bench.** `test -r /dev/ttyUSB0 -a -w
   /dev/ttyUSB0 && echo ready` must print `ready`. On this host the serial
   devices are group `uucp`, and the current user is not a member. The human
   may fix that once with `sudo usermod -aG uucp "$USER"`, then must log out
   and back in; do not run the installer with sudo.
4. **Put the Newton in receive mode.** Open **Dock**, choose **Serial** at the
   stock **38400** speed, and tap **Connect**. Leave that waiting screen open.
   Do not select Fast Serial: its Newton-side package is not installed.
5. **Send the smallest proof-of-life package from the host:**

   ```sh
   cd ~/git/newton-harness
   runtime/install-newton-serial \
     runtime/staging/hardware/harness-loader.pkg /dev/ttyUSB0
   ```

   Use `runtime/staging/hardware/harness-tools.pkg` instead if the loader build
   is being replaced. Success is `Connected`, handshake progress, byte counts
   reaching `10552 / 10552` for the staged loader, then `Finished!!`; the
   Newton leaves the waiting screen and shows the normal package install flow.

Top three serial failures:

| Symptom | Fix |
|---|---|
| USB ID is `10c4:ea60`, no FTDI device appears, or the port changes | That is the currently attached CP2102, not the bench adapter. Unplug it, attach only FTDI `0403:6001`, rerun the identification loop, and use the reported `/dev/ttyUSB*`. |
| `cannot access /dev/ttyUSB*` | Add the user to the device's group (`uucp` here) with `sudo usermod -aG uucp "$USER"`, then log out/in and retry without sudo. |
| `No Newton answered within 30 seconds` | Confirm Dock shows **Serial** and was tapped to **Connect**; reseat the full cable chain and verify the InterConnect adapter exposes serial. Stay at 38400. If wiring is sound, swap the FTDI only then try the PL2303. |

**Never reuse a package identity.** If `HarnessToolsR10I:jbfly` is already on
the device: close the app, `SafeRemovePackage(GetPkgRef(...))`, then install
fresh. And remember `tntk` exits 0 even with undefined symbols — a clean build
is not proof.

## Step 6 — Measure

Open Harness Tools on the Newton. R10I opens ONE outbound connection to
`10.42.0.1:18081` and holds it (Newton-initiated async long-poll). Confirm the
link exists before benching:

```sh
ss -tn | grep 18081     # expect exactly one ESTAB from the Newton's address
```

Emulator reference numbers to beat: warm calls ~0.8 s, `front_app` as low as
0.034 s, and ~7-9 s only on the first call after the idle link dies.

```sh
python3 runtime/bench_tools.py --op ping --count 10
python3 runtime/bench_tools.py --op front_app --count 5
```

This POSTs to `/tools` and reports min/median/max per call. Compare against
the Einstein baseline of **5.8–11.5 s**.

Then verify against the device, not against a string in a prompt:

- `front_app` must name the app actually frontmost on the Newton's screen.
- `get_note` must return text you can read on the device.

Photograph the screen for evidence; there is no screenshot API on real
hardware.

## Step 7 — Restore

```sh
sudo ap/teardown.sh          # stops daemons, drops the nft table and address,
                             # hands wlan0 back to NetworkManager
sudo ap/emulator-only.sh     # put 10.42.0.1 back on lo for emulator work
./ap/hardware-preflight.sh   # expect the two "emulator mode" FAILs again
```

Emulator work resumes normally after this.

## What can go wrong

| Symptom | Cause | Fix |
|---|---|---|
| Card absent in Internet Setup | WaveLAN/Noguchi driver not installed | install it on the Newton first |
| AP "up" but Newton sees nothing | AX200 firmware reset out of AP mode | `modprobe -r iwlmvm iwlwifi; modprobe iwlwifi`; re-apply |
| Newton associates, no DHCP lease | NetworkManager grabbed wlan0 back | check the conf.d drop-in; re-run `apply.sh` |
| Connects, then every port fails | working as designed — only 6801/18081 are allowed | use those ports |
| `-48809` from the Newton | NIE link/driver error, or a blocked port | check the nft table; confirm the port is 6801 or 18081 |
| Everything works but is slow | expected — this is the measurement | record it, that is the deliverable |
