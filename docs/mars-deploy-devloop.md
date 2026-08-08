# Mars dev-loop reliability deploy — prepared, not applied

Prepared 2026-08-08 from `task/dev-loop-reliability` base
`a49a1b91dd8472085d67f69c990ab9b1a078c228`. This page is a human gate, not a
claim that mars or the physical Newton has been changed.

## Release contents

| Item | Path | SHA-256 |
|---|---|---|
| EF22 client | `runtime/staging/hardware/egg-freckles-ef22.pkg` | `f301fe73cd032cc6300f6f41e64f1283f718fc045c2670c9011ea46abb82a8f1` |
| Paired publisher | `pkg_publisher.py` | `1c7f4a85c027c9a76768890efae6889db492dee6a12fccb78de3cf926a9b1ed8` |
| Release bundle | `deploy/mars-devloop-a49a1b9-ef22.tar.gz` | `898a1c95c384b6fe0c31fa0abcd9b0f199c47d0ab0577ebfa8a303e36391fbb9` |
| Apply script | `scripts/mars-apply-devloop.sh` | human-gated; run on mars only |
| Rollback script | `scripts/mars-rollback-devloop.sh` | human-gated; run on mars only |

EF22 follows the package identity rule exactly: app and project identity
`EggFrecklesEF22:jbfly`, visible version `1.0-ef22`, and Newton package version
34 (`examples/harness-client/Main.newt:10-11` and
`examples/harness-client/egg-freckles.nprj:8-9`). It is distinct from EF21, so
Newton can install it without the same-identity `-10402` collision. The native
scroll callbacks remain in `Main.newt:755-764`; the new package operations are
at `Main.newt:3205-3219`.

## Human-gated apply on mars

Have the human present. Copy the three files to mars; do not pipe a script over
SSH and do not set a model override:

```sh
scp deploy/mars-devloop-a49a1b9-ef22.tar.gz \
    scripts/mars-apply-devloop.sh scripts/mars-rollback-devloop.sh mars:/tmp/
```

Then the orchestrator runs these commands in an interactive mars shell:

```sh
cd ~/git/newton-harness
sha256sum /tmp/mars-devloop-a49a1b9-ef22.tar.gz
# Must print 898a1c95c384b6fe0c31fa0abcd9b0f199c47d0ab0577ebfa8a303e36391fbb9

MARS_RELEASE_BUNDLE=/tmp/mars-devloop-a49a1b9-ef22.tar.gz \
MARS_DEPLOY_APPROVED=YES \
timeout -k 60 1200 /tmp/mars-apply-devloop.sh
```

The script is fail-closed and resumable. Before mutation it requires the known
EF21, ZC40, current publisher, both user services, port 18081, and a clean git
working tree. It records `/var/tmp/newton-harness-mars-devloop-a49a1b9-ef22/`,
creates backup branch `backup/mars-before-mars-devloop-a49a1b9-ef22`, and makes
a tarball of the complete working tree. It then fetches and checks out exactly
`a49a1b9`, verifies the stream-limit and package-tool code, stages EF22 beside
rather than over EF21, restarts only `egg-freckles-chat.service`, and drives one
bounded native-protocol “make a tiny app” turn on port 6801 in isolated emulator
`marsdeployef22`. A background monitor checks that `dual-send.service` and the
EF21 download remain available throughout. The isolated emulator is torn down
on success or failure; no physical Newton endpoint is called.

A successful run ends with `PASS` and writes the complete pre-state, package
hashes, service status, live-smoke transcript/screenshot, and continuous-server
monitor result under that state directory. Stop on any `FAIL`; do not continue
by hand around an assertion.

## Rollback

With the human present:

```sh
cd ~/git/newton-harness
MARS_ROLLBACK_APPROVED=YES \
timeout -k 60 900 /tmp/mars-rollback-devloop.sh
```

Rollback checks the saved hashes, checks out the recorded backup branch,
restores the working-tree tarball, publisher, and pre-deploy EF21 bytes, and
restarts only the chat service. EF22 is moved into the state directory for
diagnosis rather than deleted. `dual-send.service` is not stopped or restarted.
The final gate requires the old EF21 URL to have its pre-deploy hash and the
EF22 basename no longer to be downloadable.

## Physical Newton step after mars passes

1. On the Newton, close any open Egg Freckles window.
2. Open Loader ZC40 and enter `egg-freckles-ef22.pkg` once. Install it, then open
   **Egg Freckles 1.0-ef22** from Extras and verify a long reply with both native
   scroll arrows.
3. Ask it to make a tiny disposable app. After `build_pkg`, EF22 can call
   `pkg_install` over its tools channel, so future generated apps install
   without Dock. Keep the human confirmation gate for every real-device install
   or removal.
4. Keep EF21 installed and downloadable until EF22 is validated. Old Egg
   Freckles identities do linger and can compete for the Notes hook and the one
   tools poll. Do not leave both windows active. After EF22 is accepted, remove
   EF21 with a human-controlled package manager; `pkg_remove` deliberately
   refuses Egg Freckles identities.

EF14’s radio policy still applies: the tools channel exists only during an
active send/reply and closes about five seconds after idle
(`runtime/evidence/pkg-install-delete/README.md:44-47`). A no-Dock install must
happen immediately after `build_pkg`; a stalled model/tool call can miss that
window and should be retried in a new explicit send, not “fixed” with a
background keepalive.
