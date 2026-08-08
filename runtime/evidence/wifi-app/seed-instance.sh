#!/bin/sh
set -eu
instance=wifiproof
container=newton-harness-${instance}_emulator_1
seed="$HOME/newton-archive/newton-harness/flash-backups/internal-before-round9-loader-20260725-195622.flash"
health_wait() {
    deadline=$(( $(date +%s) + 90 ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        status=$(timeout -k 2 5 podman inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || true)
        echo "health=$status"
        [ "$status" = healthy ] && return 0
        sleep 3
    done
    echo "health timeout" >&2
    return 1
}
timeout -k 5 60 scripts/emulator-instance.sh down "$instance" >/dev/null 2>&1 || true
timeout -k 5 60 scripts/emulator-instance.sh up "$instance"
health_wait
timeout -k 5 30 podman stop -t 20 "$container"
timeout -k 5 30 podman cp "$seed" "$container:/state/internal.flash"
timeout -k 5 30 podman start "$container"
health_wait
timeout -k 5 10 podman port "$container" 8080
echo READY
