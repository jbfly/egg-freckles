#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
dest=$root/downloads/recovery
sums=$dest/SHA256SUMS
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

fetch() {
    url=$1
    name=$2
    echo "Fetching $name"
    curl --fail --location --retry 2 --show-error --output "$tmp/$name" "$url"
}

fetch https://archive.org/download/newton_ethernet_drivers/Enetsup.pkg Enetsup.pkg
fetch https://archive.org/download/newton_ethernet_drivers/Inetenbl.pkg Inetenbl.pkg
fetch https://archive.org/download/newton_ethernet_drivers/Inetstup.pkg Inetstup.pkg
fetch https://archive.org/download/newton_ethernet_drivers/Newtdev.pkg Newtdev.pkg
fetch https://communicrossings.com/html/newton/regnewtscape/pkg/nwcp21e2.pkg nwcp21e2.pkg
fetch http://www.unna.org/unna/drivers/ethernet/WiFi/NewtonWaveLAN_source.zip NewtonWaveLAN_source.zip
unzip -p "$tmp/NewtonWaveLAN_source.zip" WaveLAN_DDK/LucentWaveLAN.pkg > "$tmp/LucentWaveLAN.pkg"

(cd "$tmp" && sha256sum -c "$sums")
mkdir -p "$dest"
rm -f "$dest"/*.pkg
mv "$tmp"/*.pkg "$dest"/
echo "Recovery packages verified in $dest"
