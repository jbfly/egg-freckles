# EF20 note teardown and ink transport

Date: 2026-08-07. Emulator validation is required before this round is complete;
physical hardware remains human-gated.

## Part 1 — Notes completion owns teardown

EF19's Notes agent filed a terminal `INK` reply but returned without calling
`InkDone`; it depended on a later NIE peer-drop callback to finish the transfer.
If that callback did not arrive, neither delayed disposal of `inkEndpoint` nor
the five-second radio-idle timer was scheduled, leaving the `/tools` endpoint on
the shared link established. EF20 makes the terminal Notes reply clear
`inkBusy` and call `InkDone` directly
(`examples/harness-client/Main.newt:333-347`). `InkDone` still delays disposal
out of the NIE input callback by one second, preserving the Stage 3 callback
armor, and arms the existing ticketed five-second idle path
(`examples/harness-client/Main.newt:2398-2424`). That path stops `/tools`, stops
chat/ink, and only then allows the endpoint-presence guard to release the link
(`examples/harness-client/Main.newt:811-881`).

Regression coverage pins the terminal Notes transition, idle arming, and the
all-endpoint `RadioExpired` shutdown in
`test_newton_client_source.py:185-196`. The focused source and publisher suites
pass (56 tests), and `tntk` compiled package identity
`EggFrecklesEF20:jbfly`, version 32, cleanly.

Part 2 instrumentation, emulator proof, reproducible package builds, and final
suite counts follow in the next commit(s).
