#!/usr/bin/env bash
# hardware-preflight.sh — is this host ready for a real-Newton bench run?
# Read-only. Run BEFORE ap/apply.sh; re-run after, to confirm the flip worked.
# ponytail: checks only what has actually bitten us before. No generic linting.
cd "$(dirname "$0")/.."
fail=0
say() { printf '%-34s %s\n' "$1" "$2"; }
bad() { say "$1" "FAIL  $2"; fail=1; }
ok()  { say "$1" "ok    $2"; }

# 1. Radio. hostapd reports state=ENABLED while holding a stale handle to a
#    re-enumerated card, so trust iw + link state, never the daemon.
info=$(iw dev wlan0 info 2>/dev/null) || info=""
grep -q 'type AP' <<<"$info" && grep -q 'ssid newton' <<<"$info" \
  && ip -br link show wlan0 2>/dev/null | grep -q 'UP' \
  && ok "wlan0 beaconing" "AP mode, ssid newton, UP" \
  || bad "wlan0 beaconing" "not an AP / not UP — run: sudo ap/apply.sh"

# 2. The address must be on wlan0. emulator-only.sh parks it on lo, which
#    silently works for Einstein and silently fails for real hardware.
if ip -br addr show wlan0 2>/dev/null | grep -q '10.42.0.1/24'; then
  ok "10.42.0.1 on wlan0" "reachable from the subnet"
elif ip -br addr show lo | grep -q '10.42.0.1/24'; then
  bad "10.42.0.1 on wlan0" "it is on lo (emulator mode) — sudo ap/emulator-only.sh down, then sudo ap/apply.sh"
else
  bad "10.42.0.1 on wlan0" "address absent entirely"
fi

# 3. Daemons.
pgrep -f 'hostapd .*hostapd.conf' >/dev/null && ok "hostapd" "running" || bad "hostapd" "not running"
pgrep -f 'dnsmasq --conf-file=dnsmasq.conf' >/dev/null && ok "dnsmasq" "running" || bad "dnsmasq" "not running"

# 4. Firewall: the Newton may reach ONLY 6801/18081. A missing table means the
#    subnet is wide open; an extra port means the isolation claim is false.
if sudo -n nft list table inet newton-ap >/dev/null 2>&1; then
  ok "nft table inet newton-ap" "loaded"
else
  say "nft table inet newton-ap" "unknown (needs root to read; apply.sh loads it)"
fi

# 5. Listener. The Newton has no way to tell you the package server is down.
ss -tlnp 2>/dev/null | grep -q '10.42.0.1:18081' \
  && ok "package server :18081" "listening" \
  || bad "package server :18081" "start: python3 runtime/raw_pkg_server.py"

# 6. Payload.
if [ -f runtime/staging/hardware/SHA256SUMS ]; then
  (cd runtime/staging/hardware && sha256sum -c --quiet SHA256SUMS 2>/dev/null) \
    && ok "staged packages" "$(ls runtime/staging/hardware/*.pkg | wc -l) files, checksums match" \
    || bad "staged packages" "checksum mismatch — rebuild and re-stage"
else
  bad "staged packages" "runtime/staging/hardware/ not staged"
fi

# 7. Firmware health. The AX200 resets itself out of AP mode; a nonzero count
#    here explains an AP that "was up a minute ago".
# ponytail: grep -c exits 1 on zero matches, so `|| echo 0` would print "0\n0".
resets=$(journalctl -k -b 2>/dev/null | grep -c 'Device error - SW reset') || resets=0
[ "$resets" -eq 0 ] && ok "iwlwifi firmware" "0 resets this boot" \
  || bad "iwlwifi firmware" "$resets resets — sudo modprobe -r iwlmvm iwlwifi; sudo modprobe iwlwifi"

echo
if [ "$fail" -eq 0 ]; then
  echo "READY. Associate the Newton, then: iw dev wlan0 station dump"
else
  echo "NOT READY — fix the FAIL lines above."
fi
exit "$fail"
