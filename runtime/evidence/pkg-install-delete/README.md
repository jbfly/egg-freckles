# Package install/delete emulator proof — 2026-08-08

Instance: isolated `pkgdelproof` (`newton-harness-pkgdelproof_emulator_1`), seeded with
`internal-before-round9-loader-20260725-195622.flash`. No shared emulator, Mars, or
physical Newton was touched.

## Proven: `pkg_install` over the Egg Freckles tools channel

1. `pkg_publisher.py` listened on `0.0.0.0:18081` and served the staged
   `runtime/staging/hardware/pkg-proof.pkg` basename. The client connected and fetched
   it with `GET /pkg-proof.pkg HTTP/1.0` (`22-publisher.log`).
2. The host MCP call returned success:

   `{"request_id":"1","status":"result","result":"installed HarnessHello:jbfly"}`

   (`24-pkg-install-success.log`).
3. Store-specific verification returned `TRUE` for
   `GetPkgRef("HarnessHello:jbfly", GetDefaultStore()) <> nil`
   (`25-pkg-install-present.txt`).

The earlier bounded attempts are retained because they found two real races: expected
HTTP/1.0 peer-close overwrote a successful install (`06-pkg-install-tool.log`), and the
Loader callback did not report the identity for a 1,104-byte package even though it was
installed (`14-pkg-install-fixed.log`, `18-pkg-install-proof.log`). Commits `e330859` and
`092a734` fix those cases; the successful rerun above is after both fixes.

## Proven: `pkg_remove` over the Egg Freckles tools channel

`27-pkg-remove-tools-proof.txt` records the complete sequence: package present (`TRUE`),
the MCP result `removed HarnessHello:jbfly`, then store-specific nil verification
(`GetPkgRef(..., GetDefaultStore()) = nil` returned `TRUE`). The client implementation
closed the dynamic package root, searched every store with two-argument
`GetPkgRef(identity, store)`, called `SafeRemovePackage`, and searched every store again.

## Proven: `emulator_remove`

`11-emulator-remove-proof.txt` records `HarnessHello:jbfly` present before the helper and
nil afterwards. The control API answers `queued`, so the following bounded
`runtime/ns_eval.py` check is the result assertion.

## Hardware pending

The physical MP2000 was not touched. Pending hardware proof is one user-requested active
chat turn that calls `pkg_install` immediately after `build_pkg`, then `pkg_list`; and one
separately confirmed `pkg_remove` of a disposable identity. EF14 keeps `/tools` alive only
while that send/reply is active and closes it about five seconds after idle, so a model/tool
stall can miss the window. There is deliberately no background keepalive.
