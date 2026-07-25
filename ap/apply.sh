#!/usr/bin/env bash
# apply.sh — bring up the Newton AP on wlan0. Idempotent; safe to re-run.
# Usage: sudo ./apply.sh      (undo with: sudo ./teardown.sh)
set -euo pipefail
cd "$(dirname "$0")"
RUN=/run/newton-ap

[ "$(id -u)" -eq 0 ] || { echo "error: run with sudo" >&2; exit 1; }
command -v hostapd >/dev/null || { echo "error: hostapd not installed — sudo pacman -S hostapd" >&2; exit 1; }

# 1. Take wlan0 away from NetworkManager (it is the fallback uplink,
#    normally on THIS_HOUSE_6G).
#
# The persistent conf.d drop-in is what actually holds. `nmcli device set
# managed no` binds to ONE device instance, and the AX200's firmware resets
# RE-ENUMERATE the card (phy3 -> phy4). NM then sees a brand-new device, has
# no memory it was unmanaged, grabs it, randomizes the MAC and kills the
# beacon -- mid-DHCP if the Newton is connecting. Keyed on interface NAME,
# this survives that. (2026-07-25; teardown.sh removes it.)
NMCONF=/etc/NetworkManager/conf.d/99-newton-ap.conf
if [ ! -f "$NMCONF" ]; then
	printf '[keyfile]\nunmanaged-devices=interface-name:wlan0\n' > "$NMCONF"
	nmcli general reload 2>/dev/null || true
	sleep 1
fi
nmcli device disconnect wlan0 2>/dev/null || true
nmcli device set wlan0 managed no 2>/dev/null || true

# 2. Static address for the isolated subnet.
# ponytail: power save off before the radio comes up -- the AX200 firmware
# resets itself out of AP mode with PS enabled (7 resets in one boot).
iw dev wlan0 set power_save off || true
ip link set wlan0 down
ip addr flush dev wlan0
ip addr add 10.42.0.1/24 dev wlan0
ip link set wlan0 up

# 3. Firewall: subnet may reach only this host's TCP 6801/18081 + DHCP/DNS.
nft -f newton-ap.nft

# 4. (Re)start the two daemons, cleanly replacing any previous run.
mkdir -p "$RUN"
[ ! -f "$RUN/dnsmasq.pid" ] || kill "$(cat "$RUN/dnsmasq.pid")" 2>/dev/null || true
[ ! -f "$RUN/hostapd.pid" ] || kill "$(cat "$RUN/hostapd.pid")" 2>/dev/null || true
dnsmasq --conf-file=dnsmasq.conf
hostapd -B -P "$RUN/hostapd.pid" hostapd.conf

# 5. Verify we are ACTUALLY beaconing. hostapd prints state=ENABLED even when
#    holding a stale handle to a card that re-enumerated under it, so trust the
#    radio, not the daemon. This is the check whose absence cost an evening.
sleep 2
info=$(iw dev wlan0 info)
ok=1
grep -q 'type AP'     <<<"$info" || { echo "FAIL: wlan0 is not in AP mode" >&2; ok=0; }
grep -q 'ssid newton' <<<"$info" || { echo "FAIL: not beaconing SSID 'newton'" >&2; ok=0; }
ip -br link show wlan0 | grep -q 'UP' || { echo "FAIL: wlan0 is not UP" >&2; ok=0; }

if [ "$ok" -ne 1 ]; then
	echo >&2
	echo "AP did NOT come up. Most likely an iwlwifi firmware reset; count them with:" >&2
	echo "  journalctl -k -b | grep -c 'Device error - SW reset'" >&2
	echo "Recover: sudo modprobe -r iwlmvm iwlwifi; sleep 2; sudo modprobe iwlwifi" >&2
	echo "then re-run this script." >&2
	exit 1
fi

echo "AP up: SSID 'newton' (open, 802.11g ch6) on wlan0, host at 10.42.0.1, harness tcp/6801, packages tcp/18081"
echo "verified: $(grep -E 'ssid|type|channel' <<<"$info" | tr -d '\t' | tr '\n' ' ')"
