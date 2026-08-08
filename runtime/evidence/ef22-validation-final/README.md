# EF22 isolated emulator acceptance — 2026-08-08

Exact validated package: `examples/harness-client/egg-freckles.pkg`, 99,096 bytes,
SHA-256 `f301fe73cd032cc6300f6f41e64f1283f718fc045c2670c9011ea46abb82a8f1`.
`clean-build.log` is the forced top-level reproducible rebuild; the package is
Newton package version 34 and identity `EggFrecklesEF22:jbfly`.

- Isolated seeded instance `ef22final`: install-present `TRUE`, launch `"opened"`,
  30 rows at `scrollRow=0`, native up arrow moved to 10, native down returned to
  0. `scroll-pixels.txt` records 265 changed pixels on page-up and zero pixels
  different after page-down. `pkg-install-result.txt` returned
  `installed HarnessHello:jbfly`; `postinstall-present.txt` is `TRUE`.
- Installing a package intentionally dropped the EF14 tools connection. The
  attempted in-place tools restart poisoned that disposable instance's eval
  channel, so it was torn down rather than reused.
- Fresh isolated seeded instance `ef22remove`: the exact same EF22 package and a
  disposable `HarnessHello:jbfly` were installed by emulator control, then
  `pkg_remove` over EF22's tools broker returned `removed HarnessHello:jbfly`;
  `postremove-nil.txt` is `TRUE`.
- Both isolated instances were torn down. No shared emulator, mars, or physical
  Newton was touched.

The full repository suite is `132 passed` in `full-tests.txt`.
