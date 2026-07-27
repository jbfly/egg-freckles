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
| Package server | `runtime/raw_pkg_server.py` | running on `10.42.0.1:18081` |
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

## Step 5 — Install the packages

The Newton pulls them over HTTP from the already-running package server. From
the Newton's browser or the loader, fetch from `10.42.0.1:18081`. To serve a
specific package:

```sh
NEWTON_PUBLISHER_PACKAGE=runtime/staging/hardware/harness-tools.pkg \
  python3 runtime/raw_pkg_server.py
```

then fetch `http://10.42.0.1:18081/harness-client.pkg` (the route name is
fixed; the file it serves is whatever `NEWTON_PUBLISHER_PACKAGE` points at).

Serial/dock install via `newton-pkg`/NCX is the fallback if the network path
is not up yet — that is the chicken-and-egg case, since NIE itself has to be
installed before the network works.

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
