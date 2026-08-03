#!/bin/sh
# Fetch the Newton reference material this repo greps constantly.
#
# None of it is redistributable: the manuals and the Q&A notes are Apple
# copyright, so only this script and SHA256SUMS are tracked. Everything the
# script writes into refs/ is gitignored.
#
# Sources (all verified 2026-08-03, every file byte-identical to the copy this
# repo was developed against):
#
#   NewtonProgrammerGuide20.pdf  UNNA /unna/development/documentation/
#   NewtonProgrammerRef20.pdf    UNNA /unna/development/documentation/
#   qa/endpoint.htm              UNNA /unna/apple/documentation/developer/QAs-2.x/html/
#   qa/inptspec.htm              UNNA  same directory
#   nie11/nie11api.pdf           inside UNNA /unna/apple/development/NIE1.x/NIEDVLPR.EXE
#   nie11/incldfls/*.txt         inside the same archive
#
# NIEDVLPR.EXE is a DOS self-extracting zip whose `DATA` member is itself a
# zip; python3's stdlib zipfile reads both layers, so no p7zip is needed.
#
# The `.txt` files are NOT downloaded. They are pdftotext extractions, and
# dozens of docs cite them by line number (e.g.
# `refs/NewtonProgrammerGuide20.txt:50167-50178`). This script regenerates them
# with poppler's pdftotext at its default settings, which is exactly how the
# originals were made; the SHA256SUMS check below is what proves your poppler
# produces the same line numbering. Verified reproducing byte-identical output
# with poppler 26.07.0.
#
# UNNA's HTTPS certificate chain does not validate on a normal Linux trust
# store, so these are plain-HTTP URLs and SHA256SUMS is the integrity check —
# same choice scripts/fetch-recovery-packages.sh already makes.
#
# Requires: curl, sha256sum, python3, pdftotext (poppler-utils).

set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sums=$root/SHA256SUMS
base=http://www.unna.org/unna
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

command -v pdftotext >/dev/null 2>&1 || {
    echo "pdftotext not found; install poppler-utils." >&2
    echo "Without it the .txt extractions cannot be regenerated, and every" >&2
    echo "doc citation of the form refs/<name>.txt:<line> is unusable." >&2
    exit 1
}

fetch() {
    echo "Fetching $2"
    curl --fail --location --retry 2 --show-error --output "$tmp/$2" "$base/$1"
}

fetch development/documentation/NewtonProgrammerGuide20.pdf NewtonProgrammerGuide20.pdf
fetch development/documentation/NewtonProgrammerRef20.pdf NewtonProgrammerRef20.pdf

mkdir -p "$tmp/qa"
fetch apple/documentation/developer/QAs-2.x/html/endpoint.htm qa/endpoint.htm
fetch apple/documentation/developer/QAs-2.x/html/inptspec.htm qa/inptspec.htm

fetch apple/development/NIE1.x/NIEDVLPR.EXE NIEDVLPR.EXE
echo "Extracting nie11 material from NIEDVLPR.EXE"
mkdir -p "$tmp/nie11/incldfls"
python3 - "$tmp" <<'PY'
import io, os, sys, zipfile

tmp = sys.argv[1]
wanted = [
    "nie11api.pdf",
    "incldfls/inetrrrs.txt",
    "incldfls/intcnstn.txt",
    "incldfls/namemap.txt",
]
with zipfile.ZipFile(os.path.join(tmp, "NIEDVLPR.EXE")) as outer:
    inner_bytes = outer.read("DATA")
with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
    by_lower = {n.lower(): n for n in inner.namelist()}
    for want in wanted:
        name = by_lower.get(want)
        if name is None:
            raise SystemExit("missing from NIEDVLPR.EXE: " + want)
        dest = os.path.join(tmp, "nie11", want)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(inner.read(name))
PY

echo "Extracting text (pdftotext $(pdftotext -v 2>&1 | head -1 | cut -d' ' -f3))"
pdftotext "$tmp/NewtonProgrammerGuide20.pdf" "$tmp/NewtonProgrammerGuide20.txt"
pdftotext "$tmp/NewtonProgrammerRef20.pdf" "$tmp/NewtonProgrammerRef20.txt"
pdftotext "$tmp/nie11/nie11api.pdf" "$tmp/nie11/nie11api.txt"

if ! (cd "$tmp" && sha256sum -c "$sums"); then
    echo >&2
    echo "Checksum mismatch. If only the .txt lines differ, your pdftotext" >&2
    echo "version formats differently and doc line citations will be off by" >&2
    echo "some amount; the PDFs themselves are still authoritative." >&2
    exit 1
fi

rm -f "$root"/*.pdf "$root"/*.txt
rm -rf "$root/nie11" "$root/qa"
mkdir -p "$root"
mv "$tmp"/*.pdf "$tmp"/*.txt "$root"/
mv "$tmp/nie11" "$tmp/qa" "$root"/
echo "Reference material verified in $root"
