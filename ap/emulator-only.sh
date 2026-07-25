#!/bin/sh
# Put 10.42.0.1 on loopback so the emulator + harness servers can bind it,
# with no radio involved. Einstein needs the ADDRESS, not a Wi-Fi association.
# Use this for all emulator work; use apply.sh only for real-hardware benching.
# ponytail: two lines beats the AX200. `down` to revert.
set -e
case "$1" in
  down) ip addr del 10.42.0.1/24 dev lo 2>/dev/null || true; echo "10.42.0.1 removed" ;;
  *)    ip addr add 10.42.0.1/24 dev lo 2>/dev/null || true; echo "10.42.0.1 up on lo" ;;
esac
