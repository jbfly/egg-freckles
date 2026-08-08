# `tntk` recursive-source crash — 2026-08-09

## Result

The source remaining in Mars' `tic-tac-toe-a8` workspace was already the
corrected 3,910-byte revision: the dev-box compiler built it successfully and
created a 7,720-byte package (`runtime/evidence/repro-default-stack.log:1-41`,
`runtime/evidence/repro-default-stack.exit:1`). The copied read-only source and
project are preserved at `runtime/evidence/tntk-crash-src/Main.newt:1-41` and
`runtime/evidence/tntk-crash-src/tic-tac-toe-a8.nprj:1-10`.

A reconstructed 1,078-byte fixture containing 500 nested array literals
reproduces the same parser-recursion crash
(`runtime/evidence/tntk-crash-fixture/Main.newt:1-2`). `tntk` exits 139 and
creates no package with the normal 8 MiB stack, a 64 MiB stack, or an unlimited
stack (`runtime/evidence/tntk-crash-stack-limits.txt:1-3`). The local core is
SIGSEGV/`SEGV_MAPERR`; its stack starts `NPSGenNode2`, `yyparse`, `NPSParse`,
and `NPSParseStr` (`runtime/evidence/tntk-crash-coredump.txt:1-35`). Raising the
stack limit therefore does not hold for this source shape.

## Fix

`build_pkg` already rejects every nonzero `make` exit and does not stage the
artifact. It now recognizes `Segmentation fault`/`dumped core` output and
returns a specific repair instruction: do not retry byte-identical `Main.newt`;
reduce nesting or change the source shape (`newton_mcp.py:535-540`). The agent
prompt repeats that rule (`agent_prompt.txt:55-59`). This is the smallest rung-2
change: no retry state or source-history framework was added.

The real sandboxed build path rejected the fixture, reported make exit 2 and
the core dump, and returned `isError: true` without publishing
(`runtime/evidence/tntk-crash-build-path.txt:1-9`). The regression test also
places the crash fixture in a project, simulates the compiler's exact crash
output plus a stale package, and proves the result tells the agent to change
source and stages nothing (`test_newton_mcp.py:282-308`). The complete suite passes 135 tests
(`runtime/evidence/tntk-crash-pytest.txt:1-3`).

## Limits

The Mars journal's systemd-coredump entries were not readable through the
unprivileged SSH account, so the supplied Mars `NBCGenBC_sub` trace could not be
copied independently. The dev box did reproduce and preserve the supplied
`NPSGenNode2 -> yyparse -> NPSParse` trace. No service, emulator, port 18081, or
physical Newton was touched.
