#!/usr/bin/env bash
# apply.sh — bring up the Newton AP on wlan0. Idempotent; safe to re-run.
# Usage: sudo ./apply.sh      (undo with: sudo ./teardown.sh)
set -euo pipefail
cd "$(dirname "$0")"
RUN=/run/newton-ap

[ "$(id -u)" -eq 0 ] || { echo "error: run with sudo" >&2; exit 1; }
command -v hostapd >/dev/null || { echo "error: hostapd not installed — sudo pacman -S hostapd" >&2; exit 1; }

# 1. Take wlan0 away from NetworkManager (it is the fallback uplink,
#    normally on THIS_HOUSE_6G). Runtime-only change; teardown restores it.
nmcli device disconnect wlan0 2>/dev/null || true
nmcli device set wlan0 managed no

# 2. Static address for the isolated subnet.
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

echo "AP up: SSID 'newton' (open, 802.11b ch6) on wlan0, host at 10.42.0.1, harness tcp/6801, packages tcp/18081"
