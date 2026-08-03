#!/bin/sh
set -eu

fail() {
    echo "newton-round: ERROR: $*" >&2
    exit 1
}

bump_identity() {
    python3 - "$1" "$2" "$3" <<'PY'
import re
import sys
from pathlib import Path

main, project = map(Path, sys.argv[1:3])
tag = sys.argv[3]
text = main.read_text()
proj = project.read_text()

version = re.findall(r'^kVersion := "([^"\n]+)-([a-z][a-z0-9]*)";$', text, re.M)
if len(version) != 1:
    raise SystemExit("newton-round: ERROR: expected one kVersion with a lowercase tag")
base, old = version[0]
if old == tag:
    raise SystemExit(f"newton-round: ERROR: tag {tag} is already used by current source")
old_upper = old.upper()
new_upper = tag.upper()

patterns = [
    (r"^kAppSymbol := '\|([^\n]*?)" + re.escape(old_upper) + r"(:[^|\n]+)\|;$", r"kAppSymbol := '|\g<1>" + new_upper + r"\g<2>|;", 1),
    (r'^kVersion := "' + re.escape(base) + r'-' + re.escape(old) + r'";$', f'kVersion := "{base}-{tag}";', 1),
    (r'^kAppTitle := "([^"\n]*?)' + re.escape(old_upper) + r'([^"\n]*)" & kVersion;$', r'kAppTitle := "\g<1>' + new_upper + r'\g<2>" & kVersion;', 1),
    # The Extras label is optional: only the chat client carries one.
    (r'^kAppLabel := "([^"\n]*?)' + re.escape(old_upper) + r'([^"\n]*)";$', r'kAppLabel := "\g<1>' + new_upper + r'\g<2>";', False),
]
for pattern, replacement, required in patterns:
    text, count = re.subn(pattern, replacement, text, flags=re.M)
    if count > 1 or (required and count != 1):
        raise SystemExit(f"newton-round: ERROR: identity pattern matched {count} times in {main}")

proj, count = re.subn(
    r'^(\s*name: "[^"\n]*?)' + re.escape(old_upper) + r'([^"\n]*",\s*)$',
    r'\g<1>' + new_upper + r'\g<2>',
    proj,
    flags=re.M,
)
if count != 1:
    raise SystemExit(f"newton-round: ERROR: identity pattern matched {count} times in {project}")

main.write_text(text)
project.write_text(proj)
PY
}

self_check() {
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT HUP INT TERM
    cat > "$tmp/Main.newt" <<'EOF'
kAppSymbol := '|-HarnessLoaderZC1:jbfly|;
kVersion := "1.1-zc1";
kAppTitle := "- ZC1 Loader " & kVersion;
kAppLabel := "Load ZC1";
EOF
    cat > "$tmp/test.nprj" <<'EOF'
{
    name: "-HarnessLoaderZC1:jbfly",
}
EOF
    bump_identity "$tmp/Main.newt" "$tmp/test.nprj" r15a
    grep -Fx "kAppSymbol := '|-HarnessLoaderR15A:jbfly|;" "$tmp/Main.newt" >/dev/null
    grep -Fx 'kVersion := "1.1-r15a";' "$tmp/Main.newt" >/dev/null
    grep -Fx 'kAppTitle := "- R15A Loader " & kVersion;' "$tmp/Main.newt" >/dev/null
    grep -Fx 'kAppLabel := "Load R15A";' "$tmp/Main.newt" >/dev/null
    grep -Fx '    name: "-HarnessLoaderR15A:jbfly",' "$tmp/test.nprj" >/dev/null
    if bump_identity "$tmp/Main.newt" "$tmp/test.nprj" r15a 2>/dev/null; then
        fail "self-check accepted an already-used tag"
    fi
    echo "newton-round self-check: PASS"
}

if [ "${1:-}" = "--self-check" ]; then
    self_check
    exit 0
fi

[ "$#" -eq 2 ] || fail "usage: $0 <example-dir> <round-tag>"
example_dir=${1%/}
tag=$2
case "$tag" in
    [a-z]* ) ;;
    * ) fail "round tag must start with a lowercase letter" ;;
esac
case "$tag" in
    *[!a-z0-9]* ) fail "round tag may contain only lowercase letters and digits" ;;
esac
case "$example_dir" in
    examples/* ) ;;
    * ) fail "example directory must be under examples/" ;;
esac

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
[ -d "$example_dir" ] || fail "directory not found: $example_dir"
main=$example_dir/Main.newt
[ -f "$main" ] || fail "missing $main"
set -- "$example_dir"/*.nprj
[ "$#" -eq 1 ] && [ -f "$1" ] || fail "expected exactly one .nprj in $example_dir"
project=$1
pkg=$example_dir/$(basename "$project" .nprj).pkg
container_pkg=/packages/${pkg#examples/}
evidence=runtime/evidence
capture=$evidence/$tag-emulator-capture.log
baseline=$evidence/$tag-baseline.txt
screenshot=$evidence/$tag-ready.png
ocr=$evidence/$tag-ready.txt
pidfile=$evidence/$tag-capture.pid
server_log=runtime/logs/raw-pkg-server.log
container=newton-harness_emulator_1
current_tag=$(sed -n 's/^kVersion := "[^"]*-\([a-z][a-z0-9]*\)";$/\1/p' "$main")
[ "$current_tag" != "$tag" ] || fail "tag $tag is already used by current source"
mkdir -p "$evidence"
for path in "$capture" "$baseline" "$screenshot" "$ocr" "$pidfile"; do
    [ ! -e "$path" ] || fail "refusing to overwrite evidence: $path"
done
[ -f "$server_log" ] || fail "package-server log not found: $server_log"

bump_identity "$main" "$project" "$tag"
symbol=$(sed -n "s/^kAppSymbol := '|\([^|]*\)|;$/\1/p" "$main")
version=$(sed -n 's/^kVersion := "\([^"]*\)";$/\1/p' "$main")
[ -n "$symbol" ] || fail "could not read kAppSymbol after identity bump"
[ -n "$version" ] || fail "could not read kVersion after identity bump"

echo "Building $example_dir as $symbol ($version)"
make -B -C "$example_dir"
[ -s "$pkg" ] || fail "build did not produce $pkg"
LC_ALL=C grep -aF "$symbol" "$pkg" >/dev/null || fail "built package does not contain symbol $symbol"
sha=$(sha256sum "$pkg" | awk '{print $1}')
echo "Verified package identity: $symbol"
echo "SHA-256: $sha"

: > "$capture"
[ ! -s "$capture" ] || fail "capture file did not start at zero bytes: $capture"
server_bytes=$(wc -c < "$server_log" | tr -d ' ')
{
    echo "capture_command=podman logs --since 0s -f $container"
    echo "capture_initial_bytes=0"
    echo "server_log=$server_log"
    echo "server_baseline_bytes=$server_bytes"
} > "$baseline"
podman logs --since 0s -f "$container" > "$capture" 2>&1 &
capture_pid=$!
echo "$capture_pid" > "$pidfile"
ready=0
cleanup() {
    if [ "$ready" -eq 0 ]; then
        kill "$capture_pid" 2>/dev/null || true
        wait "$capture_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT HUP INT TERM
sleep 1
kill -0 "$capture_pid" 2>/dev/null || fail "capture process exited; see $capture"

echo "Installing and launching $symbol"
scripts/install-and-launch.sh "$container_pkg" "$symbol"

if command -v tesseract >/dev/null 2>&1; then
    found=0
    attempt=1
    while [ "$attempt" -le 5 ]; do
        sleep 1
        python3 -m emulator.client screen "$screenshot" >/dev/null
        tesseract "$screenshot" "$evidence/$tag-ready" 2>/dev/null
        if grep -F "$version" "$ocr" >/dev/null; then
            found=1
            break
        fi
        attempt=$((attempt + 1))
    done
    [ "$found" -eq 1 ] || fail "OCR did not find $version on the Newton screen; inspect $screenshot and $ocr"
    echo "Running version confirmed by OCR: $version"
else
    sleep 2
    python3 -m emulator.client screen "$screenshot" >/dev/null
    ready=1
    trap - EXIT HUP INT TERM
    echo "newton-round: MANUAL CHECK REQUIRED: OCR is unavailable; inspect $screenshot for $version" >&2
    echo "Capture remains running as PID $capture_pid; stop it with: kill $capture_pid" >&2
    exit 2
fi

ready=1
trap - EXIT HUP INT TERM
cat <<EOF

Round ready (fetch button not tapped)
  package:    $pkg
  sha256:     $sha
  symbol:     $symbol
  capture:    $capture
  baseline:   $baseline
  screenshot: $screenshot
  capture PID: $capture_pid (stop with: kill $capture_pid)
EOF
