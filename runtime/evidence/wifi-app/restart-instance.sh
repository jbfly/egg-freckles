#!/bin/sh
set -eu
container=newton-harness-wifiproof_emulator_1
timeout -k 5 30 podman restart -t 20 "$container"
deadline=$(( $(date +%s) + 90 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
    status=$(timeout -k 2 5 podman inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || true)
    echo "health=$status"
    [ "$status" = healthy ] && { echo READY; exit 0; }
    sleep 3
done
echo timeout >&2
exit 1
