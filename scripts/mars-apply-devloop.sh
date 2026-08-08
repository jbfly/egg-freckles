#!/usr/bin/env bash
# Human-gated mars production deploy. PREPARED ONLY; never run unattended.
set -Eeuo pipefail
shopt -s nullglob

readonly TARGET=a49a1b91dd8472085d67f69c990ab9b1a078c228
readonly EF21_SHA=6652fb0b2e28412cf63caf9cd692359ecee0388206d0bb4131fc1cb9a96a8ebb
readonly EF22_SHA=f301fe73cd032cc6300f6f41e64f1283f718fc045c2670c9011ea46abb82a8f1
readonly OLD_PUBLISHER_SHA=538d6fa41b65373c4cb3040ff3e7512078e93e7f4d6914e8a18e7b583f6ec566
readonly NEW_PUBLISHER_SHA=1c7f4a85c027c9a76768890efae6889db492dee6a12fccb78de3cf926a9b1ed8
readonly ZC40_SHA=b43564abf03ec5d8aac275fd5de34b995518097a7438b04849d69e37a0623e49
readonly DEPLOY_ID=mars-devloop-a49a1b9-ef22
readonly STATE_ROOT=/var/tmp/newton-harness-$DEPLOY_ID
readonly BACKUP_BRANCH=backup/mars-before-$DEPLOY_ID
readonly EF21=runtime/staging/hardware/egg-freckles.pkg
readonly EF22=runtime/staging/hardware/egg-freckles-ef22.pkg
readonly BUNDLE_REL=deploy/mars-devloop-a49a1b9-ef22.tar.gz

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(git rev-parse --show-toplevel)
cd "$REPO"
BUNDLE=${MARS_RELEASE_BUNDLE:-$REPO/$BUNDLE_REL}
fail(){ printf '\nFAIL: %s\nState: %s\nRollback: %s/scripts/mars-rollback-devloop.sh\n' "$*" "$STATE_ROOT" "$STATE_ROOT" >&2; exit 1; }
trap 'fail "line $LINENO: $BASH_COMMAND"' ERR
[ "${MARS_DEPLOY_APPROVED:-}" = YES ] || fail 'set MARS_DEPLOY_APPROVED=YES with the human present'
[ "$(hostname -s)" = mars ] || fail 'this script must run on mars'
command -v timeout >/dev/null
command -v systemctl >/dev/null
command -v curl >/dev/null
command -v git >/dev/null
command -v tar >/dev/null

protected_manifest(){
  {
    find runtime/staging/hardware -maxdepth 1 -type f \( -iname '*backup*' -o -iname '*.bak*' -o -name 'harness-loader-zc40.pkg' -o -name 'egg-freckles.pkg' \) -print0
    if [ -d runtime/backups ]; then find runtime/backups -type f -print0; fi
  } | sort -zu | xargs -0 -r sha256sum
}

verify_post(){
  systemctl --user is-active --quiet egg-freckles-chat.service
  systemctl --user is-active --quiet dual-send.service
  [ "$(sha256sum "$EF21" | awk '{print $1}')" = "$EF21_SHA" ]
  [ "$(sha256sum "$EF22" | awk '{print $1}')" = "$EF22_SHA" ]
  [ "$(sha256sum pkg_publisher.py | awk '{print $1}')" = "$NEW_PUBLISHER_SHA" ]
  [ "$(curl --max-time 20 -fsS http://127.0.0.1:18081/egg-freckles.pkg | sha256sum | awk '{print $1}')" = "$EF21_SHA" ]
  [ "$(curl --max-time 20 -fsS http://127.0.0.1:18081/egg-freckles-ef22.pkg | sha256sum | awk '{print $1}')" = "$EF22_SHA" ]
}
if [ -f "$STATE_ROOT/PASS" ]; then
  verify_post || fail 'prior PASS marker exists but post-state no longer verifies'
  printf 'PASS: %s was already applied and still verifies\n' "$DEPLOY_ID"
  exit 0
fi

[ -z "$(git status --porcelain)" ] || fail 'mars git working tree is not clean; nothing changed'
systemctl --user is-active --quiet egg-freckles-chat.service || fail 'chat service not active before deploy'
systemctl --user is-active --quiet dual-send.service || fail 'dual-send not active before deploy'
[ -f "$EF21" ] || fail "missing current served EF21: $EF21"
[ "$(sha256sum "$EF21" | awk '{print $1}')" = "$EF21_SHA" ] || fail 'current served package is not the known EF21 build'
[ "$(sha256sum runtime/staging/hardware/harness-loader-zc40.pkg | awk '{print $1}')" = "$ZC40_SHA" ] || fail 'ZC40 hash mismatch'
[ "$(curl --max-time 20 -fsS http://127.0.0.1:18081/egg-freckles.pkg | sha256sum | awk '{print $1}')" = "$EF21_SHA" ] || fail 'port 18081 is not serving known EF21'

if [ ! -f "$STATE_ROOT/BACKUP-DONE" ]; then
  [ -f "$BUNDLE" ] || fail "missing release bundle: $BUNDLE"
  [ "$(sha256sum pkg_publisher.py | awk '{print $1}')" = "$OLD_PUBLISHER_SHA" ] || fail 'pre-deploy pkg_publisher.py is not the known production version'
  timeout -k 10 40 mkdir -p "$STATE_ROOT/release" "$STATE_ROOT/scripts"
  cp "$BUNDLE" "$STATE_ROOT/release.tar.gz"
  cp "$SCRIPT_DIR/mars-rollback-devloop.sh" "$STATE_ROOT/scripts/mars-rollback-devloop.sh"
  timeout -k 10 60 tar -xzf "$STATE_ROOT/release.tar.gz" -C "$STATE_ROOT/release"
  (cd "$STATE_ROOT/release" && sha256sum -c MANIFEST.sha256)
  [ "$(sha256sum "$STATE_ROOT/release/egg-freckles-ef22.pkg" | awk '{print $1}')" = "$EF22_SHA" ]
  [ "$(sha256sum "$STATE_ROOT/release/pkg_publisher.py" | awk '{print $1}')" = "$NEW_PUBLISHER_SHA" ]
  {
    date -Is
    hostname -f
    git status --short --branch
    git rev-parse HEAD
    systemctl --user status egg-freckles-chat.service dual-send.service --no-pager
    ss -ltnp | grep -E ':6801 |:18081 '
    sha256sum "$EF21" pkg_publisher.py runtime/staging/hardware/harness-loader-zc40.pkg
  } >"$STATE_ROOT/pre-state.txt" 2>&1
  protected_manifest >"$STATE_ROOT/protected.pre.sha256"
  cp "$EF21" "$STATE_ROOT/pre-deploy-egg-freckles.pkg"
  cp pkg_publisher.py "$STATE_ROOT/pre-deploy-pkg_publisher.py"
  [ "$(sha256sum "$STATE_ROOT/pre-deploy-egg-freckles.pkg" | awk '{print $1}')" = "$EF21_SHA" ]
  pre_head=$(git rev-parse HEAD)
  if git show-ref --verify --quiet "refs/heads/$BACKUP_BRANCH"; then
    [ "$(git rev-parse "$BACKUP_BRANCH")" = "$pre_head" ] || fail "$BACKUP_BRANCH exists at another commit"
  else
    git branch "$BACKUP_BRANCH" "$pre_head"
  fi
  printf '%s\n' "$pre_head" >"$STATE_ROOT/pre-head.txt"
  timeout -k 30 600 tar --exclude=.git -C "$REPO" -czf "$STATE_ROOT/working-tree.tar.gz" .
  sha256sum "$STATE_ROOT/working-tree.tar.gz" >"$STATE_ROOT/working-tree.tar.gz.sha256"
  date -Is >"$STATE_ROOT/BACKUP-DONE"
else
  [ -f "$STATE_ROOT/release/MANIFEST.sha256" ] || fail 'resume state is incomplete: release missing'
  (cd "$STATE_ROOT/release" && sha256sum -c MANIFEST.sha256)
  git show-ref --verify --quiet "refs/heads/$BACKUP_BRANCH" || fail 'resume state is incomplete: backup branch missing'
  [ "$(git rev-parse "$BACKUP_BRANCH")" = "$(cat "$STATE_ROOT/pre-head.txt")" ] || fail 'resume backup branch mismatch'
  [ -f "$STATE_ROOT/working-tree.tar.gz" ] || fail 'resume state is incomplete: tarball missing'
fi

rm -f "$STATE_ROOT/dual-send-monitor.FAIL"
# Sample continuously: this script never restarts or stops dual-send.
(while sleep 2; do systemctl --user is-active --quiet dual-send.service && curl --max-time 10 -fsS http://127.0.0.1:18081/egg-freckles.pkg >/dev/null || { date -Is >"$STATE_ROOT/dual-send-monitor.FAIL"; exit; }; done) &
MONITOR_PID=$!
SMOKE_INSTANCE=marsdeployef22
cleanup(){
  kill "$MONITOR_PID" 2>/dev/null || true
  timeout -k 10 90 ./scripts/emulator-instance.sh down "$SMOKE_INSTANCE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Exact requested production code commit; release-only EF22 bytes stay in staging.
timeout -k 30 300 git fetch origin
git cat-file -e "$TARGET^{commit}"
timeout -k 10 60 git checkout --detach "$TARGET"
[ "$(git rev-parse HEAD)" = "$TARGET" ]
grep -Fq 'limit=2**24' server.py || fail '64KB stream-limit fix missing'
grep -Fq 'pkg_install' newton_mcp.py || fail 'host pkg_install missing'
grep -Fq 'pkg_remove' newton_mcp.py || fail 'host pkg_remove missing'
cmp -s pkg_publisher.py "$STATE_ROOT/release/pkg_publisher.py" || fail 'checked-out publisher does not match paired release publisher'
[ "$(sha256sum runtime/staging/hardware/harness-loader-zc40.pkg | awk '{print $1}')" = "$ZC40_SHA" ] || fail 'checkout changed ZC40'

install -m 0644 "$STATE_ROOT/release/egg-freckles-ef22.pkg" "$EF22.tmp"
[ "$(sha256sum "$EF22.tmp" | awk '{print $1}')" = "$EF22_SHA" ]
mv -f "$EF22.tmp" "$EF22"
# EF21 is intentionally neither overwritten nor removed.
[ "$(sha256sum "$EF21" | awk '{print $1}')" = "$EF21_SHA" ]
protected_manifest >"$STATE_ROOT/protected.after-publish.sha256"
cmp "$STATE_ROOT/protected.pre.sha256" "$STATE_ROOT/protected.after-publish.sha256" || fail 'protected ZC40/backup/EF21 files changed'

timeout -k 20 90 systemctl --user restart egg-freckles-chat.service
for _ in $(seq 1 30); do systemctl --user is-active --quiet egg-freckles-chat.service && break; sleep 1; done
systemctl --user is-active --quiet egg-freckles-chat.service

rm -rf runtime/agent-workspace/mars-deploy-smoke
./scripts/emulator-instance.sh down "$SMOKE_INSTANCE" >/dev/null 2>&1 || true
prompt="EMULATOR ONLY. Make a tiny app visibly titled Mars Deploy Smoke. Use isolated instance $SMOKE_INSTANCE, project mars-deploy-smoke, identity MarsDeploySmokeEF22:nwtn. Run create_project, write_source, build_pkg, emulator_boot, emulator_install, emulator_newtonscript, emulator_screen in order. Never use hardware_install."
timeout -k 30 480 python3 "$STATE_ROOT/release/mars-live-smoke.py" --timeout 420 "$prompt" | tee "$STATE_ROOT/live-smoke.txt"
[ -s runtime/agent-workspace/mars-deploy-smoke/mars-deploy-smoke.pkg ]
head -c 8 runtime/agent-workspace/mars-deploy-smoke/mars-deploy-smoke.pkg | grep -aq '^package0$'
python3 -m emulator.client --instance "$SMOKE_INSTANCE" screen "$STATE_ROOT/live-smoke.png"
if command -v tesseract >/dev/null; then
  timeout -k 5 60 tesseract "$STATE_ROOT/live-smoke.png" stdout --psm 11 2>/dev/null | tee "$STATE_ROOT/live-smoke.ocr.txt"
  grep -Eiq 'Mars|Deploy|Smoke' "$STATE_ROOT/live-smoke.ocr.txt" || fail 'smoke screenshot OCR did not show expected title'
fi
cleanup
trap - EXIT
[ ! -f "$STATE_ROOT/dual-send-monitor.FAIL" ] || fail 'dual-send monitor observed an outage'
verify_post
protected_manifest >"$STATE_ROOT/protected.post.sha256"
cmp "$STATE_ROOT/protected.pre.sha256" "$STATE_ROOT/protected.post.sha256" || fail 'protected files changed after smoke'
{
  date -Is
  git rev-parse HEAD
  systemctl --user is-active egg-freckles-chat.service dual-send.service
  sha256sum "$EF21" "$EF22" pkg_publisher.py
  echo 'live smoke: PASS'
  echo 'physical Newton: untouched'
} | tee "$STATE_ROOT/PASS"
printf '\nPASS: mars dev-loop deploy prepared at %s is live. EF21 and EF22 are both downloadable; no physical Newton was touched.\n' "$TARGET"
