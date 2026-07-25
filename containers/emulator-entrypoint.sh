#!/bin/sh
set -eu

ROM=/rom/717006
EXPECTED_ROM_SIZE=8388608
CONTROL_PID=
EMULATOR_PID=
OPENBOX_PID=
PULSE_PID=
VNC_PID=
WEBSOCKIFY_PID=
XVFB_PID=

cleanup() {
    for pid in \
        "$EMULATOR_PID" \
        "$CONTROL_PID" \
        "$WEBSOCKIFY_PID" \
        "$VNC_PID" \
        "$OPENBOX_PID" \
        "$PULSE_PID" \
        "$XVFB_PID"
    do
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    for pid in \
        "$EMULATOR_PID" \
        "$CONTROL_PID" \
        "$WEBSOCKIFY_PID" \
        "$VNC_PID" \
        "$OPENBOX_PID" \
        "$PULSE_PID" \
        "$XVFB_PID"
    do
        if [ -n "$pid" ]; then
            wait "$pid" 2>/dev/null || true
        fi
    done
}

trap cleanup EXIT INT TERM

if [ ! -f "$ROM" ]; then
    echo "Missing Newton ROM: mount your 717006 dump at $ROM" >&2
    exit 64
fi

rom_size=$(stat -c %s "$ROM")
if [ "$rom_size" -ne "$EXPECTED_ROM_SIZE" ]; then
    echo "Newton ROM must be exactly $EXPECTED_ROM_SIZE bytes; got $rom_size" >&2
    exit 65
fi

mkdir -p \
    "$HOME/.config/robowerk.com" \
    "$HOME/.config/pulse" \
    "$XDG_RUNTIME_DIR"
chmod 0700 "$XDG_RUNTIME_DIR"
cp /opt/newton/config/einstein.prefs \
    "$HOME/.config/robowerk.com/einstein.prefs"

Xvfb "$DISPLAY" -screen 0 1024x768x24 -nolisten tcp -noreset &
XVFB_PID=$!

i=0
while ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 50 ]; then
        echo "Xvfb did not become ready" >&2
        exit 70
    fi
    sleep 0.1
done

openbox --display "$DISPLAY" >/tmp/openbox.log 2>&1 &
OPENBOX_PID=$!

pulseaudio --daemonize=no --exit-idle-time=-1 >/tmp/pulseaudio.log 2>&1 &
PULSE_PID=$!

if [ "${NEWTON_ENABLE_VNC:-1}" = "1" ]; then
    x11vnc \
        -display "$DISPLAY" \
        -localhost \
        -forever \
        -shared \
        -nopw \
        -quiet \
        -rfbport 5900 &
    VNC_PID=$!
    websockify --web=/usr/share/novnc 6080 localhost:5900 &
    WEBSOCKIFY_PID=$!
fi

python3 /opt/newton/bin/emulator-control --host 0.0.0.0 --port 8080 &
CONTROL_PID=$!

einstein &
EMULATOR_PID=$!

status=0
wait "$EMULATOR_PID" || status=$?
exit "$status"
