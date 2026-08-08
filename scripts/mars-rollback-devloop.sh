#!/usr/bin/env bash
# Human-gated rollback for mars-devloop-a49a1b9-ef22.
set -Eeuo pipefail
readonly DEPLOY_ID=mars-devloop-a49a1b9-ef22
readonly STATE_ROOT=/var/tmp/newton-harness-$DEPLOY_ID
readonly BACKUP_BRANCH=backup/mars-before-$DEPLOY_ID
readonly EF21=runtime/staging/hardware/egg-freckles.pkg
readonly EF22=runtime/staging/hardware/egg-freckles-ef22.pkg
fail(){ printf '\nROLLBACK FAIL: %s\nState preserved at %s\n' "$*" "$STATE_ROOT" >&2; exit 1; }
trap 'fail "line $LINENO: $BASH_COMMAND"' ERR
protected_manifest(){
  {
    find runtime/staging/hardware -maxdepth 1 -type f \( -iname '*backup*' -o -iname '*.bak*' -o -name 'harness-loader-zc40.pkg' -o -name 'egg-freckles.pkg' \) -print0
    if [ -d runtime/backups ]; then find runtime/backups -type f -print0; fi
  } | sort -zu | xargs -0 -r sha256sum
}
[ "${MARS_ROLLBACK_APPROVED:-}" = YES ] || fail 'set MARS_ROLLBACK_APPROVED=YES with the human present'
[ "$(hostname -s)" = mars ] || fail 'this script must run on mars'
REPO=$(git rev-parse --show-toplevel)
cd "$REPO"
[ -d "$STATE_ROOT" ] || fail 'deploy state directory is missing'
[ -f "$STATE_ROOT/pre-head.txt" ] || fail 'pre-deploy commit record is missing'
[ -f "$STATE_ROOT/pre-deploy-egg-freckles.pkg" ] || fail 'pre-deploy EF21 backup is missing'
[ -f "$STATE_ROOT/pre-deploy-pkg_publisher.py" ] || fail 'pre-deploy publisher backup is missing'
[ -f "$STATE_ROOT/working-tree.tar.gz" ] || fail 'working-tree backup is missing'
(cd "$STATE_ROOT" && sha256sum -c working-tree.tar.gz.sha256)
systemctl --user is-active --quiet dual-send.service || fail 'dual-send is not active before rollback'
git show-ref --verify --quiet "refs/heads/$BACKUP_BRANCH" || fail 'backup branch is missing'
[ "$(git rev-parse "$BACKUP_BRANCH")" = "$(cat "$STATE_ROOT/pre-head.txt")" ] || fail 'backup branch does not match recorded pre-deploy HEAD'

# Keep failed EF22 bytes for diagnosis, but stop advertising that basename.
if [ -f "$EF22" ]; then
  mv -f "$EF22" "$STATE_ROOT/rolled-back-egg-freckles-ef22.pkg"
fi
timeout -k 10 60 git checkout "$BACKUP_BRANCH"
timeout -k 30 600 tar -xzf "$STATE_ROOT/working-tree.tar.gz" -C "$REPO"
install -m 0644 "$STATE_ROOT/pre-deploy-egg-freckles.pkg" "$EF21.tmp"
mv -f "$EF21.tmp" "$EF21"
install -m 0644 "$STATE_ROOT/pre-deploy-pkg_publisher.py" pkg_publisher.py.tmp
mv -f pkg_publisher.py.tmp pkg_publisher.py

# dual-send is deliberately never stopped or restarted.
timeout -k 20 90 systemctl --user restart egg-freckles-chat.service
for _ in $(seq 1 30); do systemctl --user is-active --quiet egg-freckles-chat.service && break; sleep 1; done
systemctl --user is-active --quiet egg-freckles-chat.service
systemctl --user is-active --quiet dual-send.service
[ "$(sha256sum "$EF21" | awk '{print $1}')" = "$(sha256sum "$STATE_ROOT/pre-deploy-egg-freckles.pkg" | awk '{print $1}')" ]
[ "$(sha256sum pkg_publisher.py | awk '{print $1}')" = "$(sha256sum "$STATE_ROOT/pre-deploy-pkg_publisher.py" | awk '{print $1}')" ]
protected_manifest >"$STATE_ROOT/protected.rollback.sha256"
cmp "$STATE_ROOT/protected.pre.sha256" "$STATE_ROOT/protected.rollback.sha256" || fail 'rollback did not restore protected ZC40/backup/EF21 files'
[ "$(curl --max-time 20 -fsS http://127.0.0.1:18081/egg-freckles.pkg | sha256sum | awk '{print $1}')" = "$(sha256sum "$STATE_ROOT/pre-deploy-egg-freckles.pkg" | awk '{print $1}')" ]
if curl --max-time 10 -fsS http://127.0.0.1:18081/egg-freckles-ef22.pkg >/dev/null 2>&1; then
  fail 'EF22 basename is still downloadable after rollback'
fi
{
  date -Is
  git rev-parse HEAD
  systemctl --user is-active egg-freckles-chat.service dual-send.service
  sha256sum "$EF21" pkg_publisher.py
  echo 'serving restored pre-deploy package: PASS'
} | tee "$STATE_ROOT/ROLLBACK-PASS"
printf '\nPASS: restored %s and the pre-deploy served Egg Freckles package. dual-send stayed active.\n' "$BACKUP_BRANCH"
