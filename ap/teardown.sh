#!/usr/bin/env bash
# teardown.sh — undo apply.sh completely and hand wlan0 back to NetworkManager.
# Idempotent: every step tolerates the state already being gone.
# Usage: sudo ./teardown.sh
set -uo pipefail   # deliberately no -e: plow through partial states
cd "$(dirname "$0")"
RUN=/run/newton-ap

[ "$(id -u)" -eq 0 ] || { echo "error: run with sudo" >&2; exit 1; }

# 1. Stop daemons started by apply.sh.
[ ! -f "$RUN/hostapd.pid" ] || kill "$(cat "$RUN/hostapd.pid")" 2>/dev/null
[ ! -f "$RUN/dnsmasq.pid" ] || kill "$(cat "$RUN/dnsmasq.pid")" 2>/dev/null

# 2. Drop the firewall table (only ours; everything else untouched).
nft destroy table inet newton-ap 2>/dev/null

# 3. Remove the subnet address and raze runtime state.
ip addr del 10.42.0.1/24 dev wlan0 2>/dev/null
ip link set wlan0 down
rm -rf "$RUN"

# 4. Hand wlan0 back; NM auto-reconnects the saved fallback uplink.
nmcli device set wlan0 managed yes
nmcli device connect wlan0 2>/dev/null

echo "wlan0 back under NetworkManager (fallback uplink restored)"
