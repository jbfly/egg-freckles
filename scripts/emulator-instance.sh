#!/bin/sh
# Bring up / tear down / list isolated Einstein emulator instances.
#
# Each instance is one podman-compose project, so podman-compose already gives
# it a private container name and a private `emulator-state` volume. The only
# thing left to separate is the two host ports, and those are taken from the
# kernel rather than assigned by hand.
set -eu

COMPOSE=${COMPOSE:-podman-compose}
command=${1:-}
instance=${2:-}
# External git worktrees do not inherit the main checkout's ignored .env.
# Reuse it explicitly so the ROM mount cannot silently fall back to secrets/.
main_env=
if [ ! -f .env ]; then
	common=$(git rev-parse --git-common-dir 2>/dev/null || true)
	case "$common" in /*) :;; *) common=$PWD/$common;; esac
	main_env=$(dirname "$common")/.env
	[ -f "$main_env" ] || main_env=
fi

if [ -n "$main_env" ]; then
	compose() { "$COMPOSE" --env-file "$main_env" "$@"; }
else
	compose() { "$COMPOSE" "$@"; }
fi

project() {
	test -n "$instance" || { echo "INSTANCE is required" >&2; exit 1; }
	case "$instance" in
		*[!a-z0-9-]*) echo "INSTANCE must be lowercase letters, digits and dashes" >&2; exit 1;;
	esac
	echo "newton-harness-$instance"
}

# ponytail: bind port 0, read it back, release it. There is a small race between
# release and podman binding it; retry the `up` if that ever loses.
free_port() {
	python3 -c 'import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()'
}

case "$command" in
up)
	name=$(project)
	NEWTON_CONTROL_PORT=$(free_port) \
	NEWTON_NOVNC_PORT=$(free_port) \
	compose -p "$name" --profile emulator up -d emulator >&2
	container=$(podman ps -a --filter "label=com.docker.compose.project=$name" \
		--filter label=com.docker.compose.service=emulator --format '{{.Names}}' | head -1)
	test -n "$container" || { echo "compose did not create the emulator container" >&2; exit 1; }
	printf 'instance   %s\n' "$instance"
	printf 'container  %s\n' "$container"
	printf 'control    http://127.0.0.1:%s\n' "$(podman port "$container" 8080 | cut -d: -f2)"
	printf 'novnc      http://127.0.0.1:%s/vnc.html?autoconnect=1\n' \
		"$(podman port "$container" 6080 | cut -d: -f2)"
	;;
down)
	name=$(project)
	compose -p "$name" --profile emulator down -v
	;;
list)
	printf '%-24s %-10s %s\n' INSTANCE STATUS PORTS
	podman ps --filter name=_emulator_1 \
		--format '{{.Names}}\t{{.Status}}\t{{.Ports}}' |
	while IFS="$(printf '\t')" read -r container status ports; do
		case "$container" in
			newton-harness-*) label=${container#newton-harness-}; label=${label%_emulator_1};;
			newton-harness_emulator_1) label="(default)";;
			*) label=$container;;
		esac
		printf '%-24s %-10s %s\n' "$label" "${status%% *}" "$ports"
	done
	;;
*)
	echo "usage: $0 up|down INSTANCE | $0 list" >&2
	exit 1
	;;
esac
