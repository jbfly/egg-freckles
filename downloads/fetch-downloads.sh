#!/bin/sh
# Fetch the Newton Internet Enabler distributions and the one third-party NIE
# TCP source this project studied while reverse-engineering the transport.
#
# The eight NIE archives are Apple copyright and are not redistributed here;
# only this script and SHA256SUMS are tracked. Everything it writes is
# gitignored.
#
# All nine files come from UNNA and were verified 2026-08-03: HTTP 200, and
# each downloaded file hashed identically to the copy this repo was developed
# against.
#
#   NIE10.ZIP, NIE11.EXE, NIEDVLPR.EXE, NIEGOODS.ZIP,
#   NIE_1.1_Developer.sea.hqx, NIE_1.1_Packages.sea.hqx,
#   NIE_Developer_Goodies.sea.hqx, Newton_Internet_Enabler.sea.hqx
#                                  UNNA /unna/apple/development/NIE1.x/
#   NIM-source.zip (NewtonIM)      UNNA /unna/internet/NewtonIM/
#
# NOT fetched, because it stays tracked: `unixnpi-1.1.3.tar.gz` is GPL C source
# (Richard C. Li's UnixNPI, UNNA /unna/unix/), so redistributing it here is both
# allowed and useful — it is 21 KB and it is the reference implementation of the
# Newton package-upload protocol that `runtime/newton_backup.py` had to match.
#
# `recovery/` has its own fetcher, `scripts/fetch-recovery-packages.sh`.
#
# UNNA's HTTPS certificate chain does not validate on a normal Linux trust
# store, so these are plain-HTTP URLs and SHA256SUMS is the integrity check.
#
# Requires: curl, sha256sum.

set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sums=$root/SHA256SUMS
base=http://www.unna.org/unna
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

fetch() {
    echo "Fetching $2"
    curl --fail --location --retry 2 --show-error --output "$tmp/$2" "$base/$1"
}

for name in NIE10.ZIP NIE11.EXE NIEDVLPR.EXE NIEGOODS.ZIP \
            NIE_1.1_Developer.sea.hqx NIE_1.1_Packages.sea.hqx \
            NIE_Developer_Goodies.sea.hqx Newton_Internet_Enabler.sea.hqx; do
    fetch "apple/development/NIE1.x/$name" "$name"
done
fetch internet/NewtonIM/NIM-source.zip NIM-source.zip

(cd "$tmp" && sha256sum -c "$sums")

for name in NIE10.ZIP NIE11.EXE NIEDVLPR.EXE NIEGOODS.ZIP \
            NIE_1.1_Developer.sea.hqx NIE_1.1_Packages.sea.hqx \
            NIE_Developer_Goodies.sea.hqx Newton_Internet_Enabler.sea.hqx \
            NIM-source.zip; do
    mv "$tmp/$name" "$root/$name"
done
echo "NIE archives verified in $root"
