#!/bin/sh
set -eu
timeout -k 5 90 scripts/emulator-instance.sh down wifiproof
echo DOWN
