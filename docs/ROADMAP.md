# ROADMAP — from a working chat app to "Claude Code for the Newton"

Written 2026-08-03 after a full-repo audit. This is the successor to `PLAN.md`
(phases 0–3 there are shipped; this doc picks up at its phase 4). Point new
sessions here; each track below is sized so a single session of a cheaper
agent can complete one task and verify it.

## Status log (update this section as tracks complete)

- **2026-08-04 — EF6: ink is decimated instead of truncated, the tools poll is
  package-wide, and every NIE callback is armored.** Ships as
  `EggFrecklesEF6:jbfly` (v1.0-ef6), sha256 `7cce547b…`, still one package and
  still named "Egg Freckles". Answers findings (1), (2) and (4) of the fifth
  hardware test and the fourth test's `-48803`. Proven on isolated instance
  `ef6round` (seeded flash) against `NEWTON_FAKE_BACKEND=1 server.py:6801` and
  `runtime/raw_pkg_server.py:18081`, with **real** codex for the vision call.
  Round record `docs/newton-dev-notes.md` "EF6 round"; evidence
  [`ef6round-ink-decimation.txt`](../runtime/evidence/ef6round-ink-decimation.txt),
  [`ef6round-tools-window-closed.txt`](../runtime/evidence/ef6round-tools-window-closed.txt),
  screenshots `runtime/evidence/ef6round-*.png`. 98 tests (94 + 4).
  - **The headline: `/tools` answers with the app never opened.** After a
    `podman restart`, with Egg Freckles not launched once,
    `{"op":"ping"}` → `pong` and `{"op":"front_app"}` → `Notepad (paperroll)`.
    The poll now belongs to the same package-level install-hook agent as "Send
    to AI" — created by `InstallScript`, started by a delayed call on a *frame*
    receiver (no view to be closed under it, so no `-48809`), and stopped only
    by `RemoveScript`. `Boot` no longer starts it and `ViewQuitScript` no longer
    stops it. Because `InstallScript` runs on every reset, the poll restarts
    itself after a crash or a battery pull with nobody touching the device.
    Window opened → chatted → **closed** → `ping`/`front_app`/`note_list`/
    `battery` all still answered; reopened and `Ask Note` worked.
  - **Ink: 37 strokes drawn, 37 sent, 37 rendered.** A dense Sketches page
    (37 drags, **2569 points** read straight back out of the soup) went through
    "Send to AI" and arrived as `INK BODY bytes=5585 strokes=37 points=1308
    bytes_per_point=4.27`. Not one stroke dropped; the points were thinned
    evenly *within* each stroke at an integer stride of 2. **EF5 would have sent
    5 of those 37** — `kMaxPoints := 400` was spent by the first five strokes
    and `:AddStroke` refused every stroke after it, silently, while reporting
    the survivor count as the drawing. That is the handwritten sentence that
    came back as its first three words.
  - **The new budget, and its arithmetic.** `kMaxPoints := 1600`,
    `kMaxItems := 256`, plus a `kMaxRaw := 12000` pre-thinning ceiling past
    which a stroke is kept as its two endpoints rather than dropped. 16384-byte
    host body cap, minus 20 for the header, 204 for the `H` line and 2048 for
    the per-stroke `S` lines, leaves 14112; at a pessimistic 8 bytes/point that
    is 1764 points, so 1600 fits with margin. **Measured on the wire: 4.27
    bytes/point**, so the real margin is about 1.8x. The count reported to the
    human is the true drawn count, and thinning is stated out loud — the reply
    note read `re: 37 strokes (ink thinned to fit)` / *"Diagonal lines
    resembling falling rain."*
  - **A reconnect storm, found because of the move and fixed.** Making the poll
    permanent exposed that `:ToolConnected` started a fresh self-rescheduling
    `:ToolWatch` chain on *every* connect and never stopped the old ones, so
    `toolMisses` climbed once per chain per 4 s and the channel tore itself
    down continuously: **15 reconnects in 60 s**, every one of them the Newton
    hanging up (`persistent Newton connection closed mid-response`). One
    `toolWatching` guard → **0 reconnects in 60 s**, one connection held across
    a 12-minute session. Twenty-sixth finding in `docs/newtonscript-eval.md`;
    this is very probably the fifth test's "stale-poll 504s".
  - **NIE armor, by construction and unverifiable here.** Every
    `CompletionScript`, `InputScript` and `ExceptionHandler` body, and
    `Grabbed`/`InkGrabbed`/`ToolGrabbed`, now open with `try … onexception
    |evt.ex|` and never rethrow; the `InetReleaseLink` call itself is guarded,
    which is the one that drives `RemoveLinkClient`. A bind failure buys exactly
    one 5-second retry before it reaches the status line. **Einstein cannot
    reproduce the fourth test's fault** — its synthetic link never exercises the
    real `InetManagerFSM` — so this remains hardware-unverified. What is proven
    here is only that the armored client still works: chat, ink, tools, filing.
  - **Regressions all pass**: "Send to AI" on a text note filed the reply to
    `AI` (`7:AI`) and left the source unfiled (`6:-`), so the third hardware
    test's filing fix has not regressed; `Save Note` → "Saved note id=5";
    `/help` → the full command list. One new host line logs the parsed ink
    geometry (`INK BODY …`) so a future round can check a budget against the
    wire instead of against arithmetic.
  - **Also measured**: one `'ink2` item can hold many strokes — 37 strokes
    arrived in 6 items — which corrects the seventeenth finding's "one item per
    pen stroke" (twenty-seventh finding). An item cap is not a stroke cap.
  - **Still open: hardware.** EF6 has not been installed on the MP2000, and the
    `-48803` armor is the part that most needs to go there. Item (3) of the
    fifth test, the loader UX, is answered separately by Track L4 below.

- **2026-08-04 — Track L4 DONE: the loader is called "Loader", you can write in
  its field, and you can type into it.** Answers item 3 of the fifth hardware
  test below. New identity **`-Loader1:jbfly`**, Extras label plain **"Loader"**,
  window title "Loader 1.0". Package 15,624 bytes.
  - **Naming.** The convention is now `-Loader<n>:jbfly` with `n` incrementing
    and never reused (`docs/phase3-chat-round.md`, "Package identity"); the
    leading `-` carries over from the `-HarnessLoaderZC*` series. The version
    restarts at **1.0** because the 2.x numbering belonged to the ZC dev series
    — the same call Egg Freckles made going from "Chat A9 v2.4-a9" to
    "Egg Freckles 1.0-ef5". Extras shows the label only; the version lives in
    the window title so a screenshot still identifies the build.
  - **Input field.** Full window width bar the keyboard button, and **42px tall
    instead of 26**, font 14 instead of 10. The slot that actually buys writing
    room is `viewLineSpacing` — "the height of the input line in pixels"
    (`refs/NewtonProgrammerRef20.txt:23311-23314`) — now 38; `viewFont` only
    styles the recognised text (`:23301-23303`). 14 not 18 so a ~24-character
    `.pkg` name still fits the one line `protoInputLine` allows.
  - **On-screen keyboard.** The stock affordance is **`protoKeyboardButton`**:
    "the same keyboard button shown on the status bar in the notepad. Tapping
    the button causes the on-screen keyboard to appear"
    (`refs/NewtonProgrammerGuide20.txt:20405-20407`). It needs a
    `defaultKeyboard` symbol which it "is not actually in the button view frame,
    but is found by inheritance" (`refs/NewtonProgrammerRef20.txt:24477-24480`),
    so `defaultKeyboard: 'alphaKeyboard` sits on the parent window. Keys go to
    the one current **key receiver** view (Guide `:20308-20312`), so the app
    points that at its own field with `SetKeyView`, which is "only guaranteed to
    work with a clParagraphView" (`Ref:24698-24724`) — `protoInputLine` is one
    ("a simple paragraph view", `:23269-23270`). Never override the button's
    `ViewClickScript`/`ButtonClickScript`/`PickActionScript`: `protoPictureButton`
    uses them internally (`Ref:24481-24486`).
  - **Proven on instance `loaderround`**, seeded per `docs/parallel-emulators.md`.
    Tapped the button → the ROM alphaKeyboard opened over the window; tapped its
    `del` key 11 times → `filenameView.text` read `""`; tapped `h e l l o . p k g`
    → it read `"hello.pkg"`; tapped Install → the package server logged
    `GET /hello.pkg HTTP/1.0` and `GetPkgRef("HarnessHello:jbfly", GetDefaultStore())`
    returned the installed package. Evidence `runtime/evidence/loaderround-*.png`
    and [`loaderround-proof.txt`](../runtime/evidence/loaderround-proof.txt).
    Note for future rounds: **host key injection does not reach Einstein** —
    `emulator.client text` and `key` both left the field byte-identical, so an
    on-screen keyboard has to be driven by tapping its keys.
  - **Two things found and deliberately left alone**, both pre-existing and both
    inside the install machinery this round was not to touch: (a)
    `SuckPackageFromBinary`'s `callbackFrequency: 8192` never fires for a package
    smaller than 8 KiB, so the status says "Install not confirmed" on a
    successful small install — every real payload is larger; (b) a NewtonOS
    paragraph breaks on CR, so `"\n"` inside a status string draws as an
    empty-box glyph. The window header had the same box and *is* fixed here, by
    using two `protoStaticText` children instead of one `"\n"`-joined string.
  - **Hardware upgrade path** (nothing done on the device this round): install
    the new Loader **using ZC40**, verify one real install with it, then delete
    ZC40. **Keep ZC39 as the deep fallback until Loader is hardware-proven.**
  - **94 tests collected, 91 passed, 3 failed.** No test pins the loader
    identity; the standalone `scripts/test-loader-install-guard.py` did and was
    updated to `-Loader1:jbfly`. All three failures are in
    `test_newton_client_source.py`, which reads only
    `examples/harness-client/Main.newt` and `egg-freckles.nprj` (`:6-7`) — the
    parallel EF6 client work that was uncommitted in the tree at commit time.
    None of them touch `examples/harness-loader`.

- **2026-08-04 — Fifth hardware test (EF5 on the MP2000): the dev loop worked
  end to end — codex wrote a dice program, the human installed it via ZC40,
  and it ran on real hardware.** Remaining findings, triaged:
  1. **Handwritten (ink) notes get truncated.** A handwritten "Send a list of
     ice hotels in Iceland" transcribed as just "Send a list", client
     reported 17 strokes (fewer than drawn). This is the A9 round's flagged
     unmeasured risk landing: `kMaxPoints := 400` was calibrated on straight
     `/drag` test strokes (17–89 points each); real handwriting is far
     denser, so whole strokes get dropped. An earlier long handwritten note
     returned nothing at all, then the fourth-test NIE error appeared.
     Fix (EF6): **decimate, don't truncate** — thin points per stroke to fit
     the budget (host body cap is 16 KiB, room for thousands of points),
     keep every stroke, report the real stroke count, and say loudly in the
     transcript when thinning happened.
  2. **Agent-driven install to hardware failed with "Newton not responding
     to pings"** — because the tools long-poll only runs while the Egg
     Freckles *window* is open (ToolStart in Boot, ToolStop in
     ViewQuitScript). The agent correctly fell back to asking the human to
     use ZC40. Fix (EF6): make the tools poll **package-wide** — owned by
     the same install-hook agent as Send to AI, started at boot, surviving
     window close. This also covers the observed stale-poll 504s after
     window-close cycles.
  3. **Loader UX**: ZC40 rename to plain "Loader" finally due; its text
     entry field is too small to write in, and it needs an on-screen
     keyboard option (typing package names in ink is painful).
  4. Armor from the fourth test carries into EF6: every NIE callback wrapped
     in `try … onexception` so nothing of ours can throw into the
     InetManagerFSM (`-48803`), plus one retry-after-delay on bind failure
     (`-60047`).

- **2026-08-04 — Fourth hardware test (photo evidence): NIE link-lifecycle
  fault on EF5 launch.** The human photographed the MP2000 running
  `Egg Freckles 1.0-ef5` showing two errors at once: a modal NIE alert —
  *"Newton Internet Enabler: The following exception occurred in event
  (RemoveLinkClient) of state (connected) of finite state machine
  (InetManagerFSM): {<1> name: 'evt.ex.fr.intrp, error: -48803}"* — and the
  status line `Bind error -60047`. Reading of the evidence:
  `-48803`-on-release is the repo's documented signature for
  **`InetReleaseLink` called while an endpoint is still live**
  (`docs/newton-networking-lessons.md` §1.5), and `evt.ex.fr.intrp` inside
  the FSM means one of *our* NewtonScript callbacks threw an unguarded
  interpreter exception inside an NIE FSM event. The subsequent
  `Bind error -60047` is the next connection failing to bind against the
  half-torn-down link. **Leading suspect, not yet confirmed:** the
  known two-package fight — installing EF5 leaves EF4 active until manually
  deleted (`docs/newton-dev-notes.md`, effix round operational traps), and
  two Egg Freckles both running install hooks / holding NIE state is exactly
  the shape that releases a link out from under a live endpoint. Awaiting the
  human's report of what Extras contained at the time. If it reproduces with
  only EF5 installed after a clean restart, this becomes a real EF6 bug:
  wrap every link/endpoint callback (`Released`, completion scripts) in
  `try … onexception` so nothing of ours can throw into the FSM, and add a
  single retry-after-delay on bind failure. Einstein cannot reproduce this —
  its synthetic link never exercises the real InetManagerFSM.
- **2026-08-04 — Third hardware test: "Send to AI" filed the wrong note, fixed
  in `EggFrecklesEF5:jbfly` (v1.0-ef5); Egg Freckles now has an icon.** The
  human ran EF4 on the physical MP2000 and reported: *"Send to AI works, but
  when it sends the reply it comes back as Unfiled instead of the AI folder. And
  then it seems to file the ORIGINAL note that was sent into AI."* Round record
  [`runtime/evidence/effix-filing-bug.txt`](../runtime/evidence/effix-filing-bug.txt)
  and [`effix-icons.txt`](../runtime/evidence/effix-icons.txt); the current-state
  write-up is the last section of
  [`docs/notes-integration-design.md`](notes-integration-design.md), "Third
  hardware test". Isolated instance `effix`, real codex for the vision calls.
  - **Root cause: one line, `local entry := :FindNewest();` in `:FileReply`.**
    EF4 wrote the reply note and then went looking for it again by highest
    `_uniqueID` in the Notes union soup, and filed whatever came back. That is a
    guess at identity. `_uniqueID` is allocated **per member soup** — measured on
    the ROM, two soups on one store both start at 0 — so on a union soup
    spanning more than one store the maximum is not the newest entry. The
    MP2000 has three stores; Einstein has one, which is why l2build passed and
    why re-running EF4 here under hardware-shaped conditions passed again. Not
    reproducible in the emulator; the twenty-fourth finding in
    `docs/newtonscript-eval.md`.
  - **Fix: stop searching.** `NewNote` turns the frame `MakeTextNote` returned
    into the soup entry (`"before=n after=y uid=3 lab=set"`), and a `labels` slot
    set before the add rides into the store with it — so the reply is filed as
    part of being created and the source note is never written to. `:SaveNote`
    had the same defect cosmetically and was fixed with it; `:FindNewest` stays
    for **Ask Note**, where naming the newest note is the job.
  - **Proved on all three note kinds plus a repeat send**, `uid:folder` over the
    whole soup each time: text `3:- 4:AI`, second send of the same note
    `3:- 4:AI 5:AI`, sketch `7:- 8:AI`, mixed `9:- 10:AI`. Every source note kept
    its folder; only replies carry `'AI`.
  - **Icons, both of them, from one 20x14 drawing.** A ROM icon could have been
    borrowed — Duplicate's and Delete's are reachable from the hook — but
    neither means "send this to an AI", so the egg is drawn; what is borrowed is
    the *format*, the 16-byte `bits` header copied verbatim off the ROM's own
    Duplicate icon, which is why none of the binary layout is guessed
    (twenty-fifth finding). `tntk` evaluates the source at build time, so
    `MakeBinaryFromHex` ships the binary in the part frame's `icon` slot
    (Extras) and the route entry's (the picker); both survive a cold restart
    with the app never opened.
  - **Regression on `effix`**: chat turn, `Ask Note`, `Save Note`
    ("Saved note id=11", matching an independent soup read), and the tools
    channel over curl (`front_app` → `Notepad (paperroll)`, `note_list` →
    `count=12`). 94 tests pass.
  - **Still open: hardware.** EF5 has not been installed on the MP2000. Worth
    capturing there: `{"op":"store_info"}`, which would say what the device's
    stores actually are and settle the trigger for the record.

- **2026-08-04 — Track L2 built: "Send to AI" is in the stock Notes envelope
  menu, and it works with the app closed.** Ships inside Egg Freckles as
  `EggFrecklesEF4:jbfly` (v1.0-ef4) — still one package, still one Extras icon.
  Design + settled `[verify]` table:
  [`docs/notes-integration-design.md`](notes-integration-design.md) "Build
  result"; round transcript `runtime/evidence/l2build-round.txt`; screenshots
  `runtime/evidence/l2build-*.png`. Proven on isolated instance `l2build`
  against `NEWTON_FAKE_BACKEND=1 server.py:6801` and
  `runtime/raw_pkg_server.py:18081`, with **real** codex for the vision calls.
  - **`InstallScript` works under `tntk`** — the first and riskiest `[verify]`,
    and the answer is yes on both counts. tntk emits the slot and the ROM runs
    it on activation *and on reset*: after `podman restart`, with Egg Freckles
    never opened, the picker item was back and the entry's own `aiVia` slot read
    `install`. `GetRoot().paperroll` already exists at that point, so the
    deferred-retry path shipped but never fired. The `ViewSetupFormScript`
    fallback ships as insurance and never overwrites an InstallScript entry.
  - **The wrong-note bug is gone by construction on this path.** The route
    script is handed the live soup entry of the page whose envelope was tapped,
    so there is no newest-note heuristic to poison. Three routes proven: a
    text-only note (zero-stroke `NSI1` + `H` line, answered from the text — a
    new host branch in `pkg_publisher.py`), a six-stroke house sketch (real
    vision: *"A simple outline of a house with a pitched roof."*), and a mixed
    page as **one** POST carrying both. The answer comes back as a native note
    filed in an "AI" folder.
  - **One defect found and fixed, older than this track.** The 150 s ink
    watchdog was not per-send, so an earlier send's timer could land inside a
    later one and tear its endpoint down — the first mixed-note attempt filed
    "(not sent) The host did not answer" while the host had answered. `inkSeq`
    now tickets each send. On the Ask button this only ever showed a wrong
    status line, which is why it survived A9 and L1.
  - **New toolchain rule, and it explains an old one.** `tntk` **segfaults** on
    any nested `func` that reads an enclosing function's local — i.e. on a
    closure — and since it compiles the whole `.newt` file as one function body,
    that is also the real reason "a top-level constant inside a function body"
    has always crashed it. One rule, not two
    (`docs/newtonscript-eval.md`, twenty-second finding). The route script is
    therefore a plain method value that uses neither a closure nor `self`.
  - **Uninstall is clean but not for the documented reason.** Removing the
    package re-instantiates the Notepad base view and takes the whole RAM
    `routeScripts` slot with it — a probe marker and a simulated third-party
    entry vanished too (twenty-third finding). `RemoveScript` ships regardless,
    removes only our marked entry, and never calls `RemoveSlot`. It deliberately
    does **not** `RemoveFolder("AI")`: RemoveScript runs on every deactivation,
    package replacement included, and that would unfile the user's answers on
    every upgrade.
  - **The Ask button stays for now.** The design says this path eventually
    retires it. It should not be retired until the human has used "Send to AI"
    on the physical MP2000 — otherwise the only proven path is deleted in favour
    of an unproven one. 93 tests (88 + 5). **Hardware: untouched.**

- **2026-08-04 — Track L1 done: one package, and it has a name.** Ships as
  **Egg Freckles** (`EggFrecklesEF1:jbfly`, v1.0-ef1, package version 18),
  answering points (1) through (4) of the hardware feedback below. Round record
  `docs/newton-dev-notes.md` "Track L1 round"; evidence
  `runtime/evidence/efround-*`; proven on isolated instance `efround` with the
  **committed** bytes (sha256 `2831f813…`) against `NEWTON_FAKE_BACKEND=1
  server.py:6801` and `raw_pkg_server.py:18081`.
  - **The tools client is inside the chat app now** — shape (a), not a two-form
    package. `examples/harness-tools/` is deleted. The chat window already ran a
    second endpoint on its NIE link for the ink POST, so the `/tools` long poll
    is simply a third connection on the same link; every timing rule is
    unchanged (3 s heartbeat, 4 s watchdog, `async: true`, `form: 'string`,
    `ViewQuitScript` teardown). All eight ops answered over `POST /tools`
    **with only Egg Freckles installed** — `battery` →
    `count=0 cap=100% charge=discharging ac=no type=nimh`, `note_list` →
    `count=28` — and the device's package list contains no `HarnessTools`
    (`runtime/evidence/efround-tools.txt`).
  - **Ask is no longer clock-dependent, which is what actually fixes the cat.**
    "Newest" now means the highest `EntryUniqueID` — a per-soup counter that
    never reads the clock — instead of the newest `EntryModTime`. A9's rule was
    poisoned twice over by the 2008 clock: a note written while the date was
    wrong sorts to the *front* of the `timeStamp` index, outside a scan that
    starts at the back, *and* loses every date comparison. Both rules run over
    the same rigged 25-note soup: A9 answers `id=23 "EF dnd session 18"`, EF1
    answers `id=24 "EF cat drawing page"`. On the shipped bytes the button
    itself answered `Note: EF cat drawing page two`. Rule in
    `docs/notes-bridge.md`, mechanism in `docs/newtonscript-eval.md` "Twentieth
    finding". **The trade is real and deliberate**: a drawing added to an
    *older* page no longer wins. Only one of the two behaviours survives a wrong
    clock, and the hardware has a wrong clock; Track F3 / L2 (read the note the
    user is actually on) is the fix that needs neither.
  - **`vApplication` experiment: answered, and the answer is no.** The
    eighteenth finding's open question is now closed. The flag really was set
    (live `viewFlags` 581), the root view's chain qualifies, the handlers worked
    when called directly — and tapping the ROM's up arrow changed *nothing*,
    while the same tap scrolls the Notepad with the window closed. Scroll
    routing excludes floating views by definition
    (`refs/NewtonProgrammerRef20.txt:4510-4512`). Reverted; **Up**/**Dn** stay
    and still page the transcript (27 rows, `scrollRow` 10 → 0).
  - **Two sources of the modal alert noise found and killed** — worth more than
    the feature work, and they apply to every app in this repo. An endpoint with
    no `ExceptionHandler` shows every unsolicited disconnect to the user as
    `Communications — Sorry, a problem has occurred` (`refs:57321-57323`), and
    an `AddDelayedCall` that lands on a closed view raises `-48809`. Both
    reproduced on screen, both fixed; closing the window with the poll live is
    now silent (`efround-18-closed-silent.png`). New "Twenty-first finding".
  - Naming: Extras reads **Egg Freckles**, title "Egg Freckles 1.0-ef1", buttons
    **Send** / **Ask Note** / **Save Note** / New / Up / Dn. The round tag lives
    only in the identity, the version string and the `.nprj` name;
    `scripts/newton-round.sh` was taught that (its title rewrite is now
    optional) and its `--self-check` covers the EF1 → EF2 bump.
  - Window `viewBounds` is computed from the live root box instead of hardcoded
    (`8,26,312,454` on a 320x480 screen). Honest: A9's constant was already
    near-centred *here*, so this is two pixels in the emulator — the point is
    that it is derived, not asserted.
  - 88 tests (85 + 3). **Still open, deliberately**: the loader package keeps
    its `-HarnessLoaderZC40` name (a separate cheap round — *done 2026-08-04,
    Track L4: it is `-Loader1:jbfly` / "Loader" now*), and **the physical
    MP2000 still runs A7 + R10P** — this whole lineage remains emulator-proven
    only until the human installs it. When they do, it is now **one** install
    that replaces both.

- **2026-08-04 — Track L2 designed: "Send to AI" really does go in the stock
  Notes menu, and it kills the wrong-note bug outright.** Research and design
  only, no client code. Design:
  [`docs/notes-integration-design.md`](notes-integration-design.md); probe
  transcript `runtime/evidence/l2probe-routescripts.txt`; new
  `docs/newtonscript-eval.md` "Twentieth finding". Measured on isolated
  instance `l2probe`, which was torn down after.
  - **Runtime menu injection works on the ROM.** `GetRoot().paperroll` has a
    2-entry `routeScripts` (Duplicate, Delete, both via `GetTitle`); assigning
    an extended array to that slot shadows the ROM proto, `GetRouteScripts` —
    the method the picker itself calls
    (`refs/NewtonProgrammerRef20.txt:52547-52561`) — returns `len=3 |<GetTitle>
    |<GetTitle> |Send to AI`, and the real envelope menu draws it
    (`runtime/evidence/l2probe-action-picker.png`). There is **no**
    `RegNotesRouteScript`: the only documented per-app registry is Names-only
    (`kRegNamesRouteScriptFunc`, `Ref:43732-43746`), and the bare
    `RegRouteScript`/`extraRouteScripts` symbols in the 2.1 platform file are
    documented in neither 2.0 book.
  - **The target is the note you are looking at.** `RouteScript(target,
    targetView)` receives the **live soup entry** (`IsSoupEntry`=1,
    `TargetIsCursor`=0, `EntrySoup(target):GetName()`="Notes"). Firing from the
    first note's envelope gave `uid=2`; firing from the second note's envelope
    gave `uid=3`. **Ask's newest-note heuristic is not needed on this path at
    all** — the cat/D&D class of bug cannot occur, and A9's `ExpandInk`
    extraction runs on the entry unchanged.
  - **The reply lands in a folder.** `AddFolder("AI", 'paperroll)` → `'AI`
    (`Ref:38952-38966`), `entry.labels := tag` + `EntryChangeXmit` files it,
    and the whole loop ran on the ROM: `replied uid=6 from=3 chars=46
    folder=AI`, visible under the Notes "AI" tab
    (`runtime/evidence/l2probe-ai-folder.png`). Folders do not fight back; the
    popup is demoted to an optional progress panel.
  - **It is RAM-only and must be re-applied at every boot.** Injected,
    `podman restart`, re-read: back to `len=2`. `InstallScript` "is executed
    when an application or auto part is activated on the Newton or whenever the
    Newton is reset" (`refs/NewtonProgrammerGuide20.txt:5209-5210`), with the
    mandatory `RemoveScript` reversal (`:5223-5234`). `RemoveSlot` restores the
    ROM array exactly — which is why uninstall must instead rebuild the array
    without our frame, so a competing package's entry survives.
  - **Recommended packaging: fold into Track L1's Egg Freckles package, not a
    third package** — the route script needs `InetGrabLink`, the shared
    `linkID` and A9's extractor, all of which already live there, and a second
    NIE link owner is the `-16009` failure the ink round already paid for.
    Transport: reuse the existing `POST /ink` verbatim (`NSI1` + `H` line,
    reply as one `INK …` line), fully async like `SendInk`, no long poll.
  - **Biggest open `[verify]`: nothing in this repo has ever used
    `InstallScript`**, so `tntk`'s handling of it is unproven and is step 1 of
    the build plan; the fallback is hooking from `ViewSetupFormScript`.

- **2026-08-04 — Track L3 done: mars builds Newton packages, and there is a
  public from-zero host-setup guide.** `docs/host-setup.md` is the new
  doc — clone cDCL and `tntk`, apply `tools/tntk-project-version.patch` plus
  a **second, previously undocumented** patch this round found and vendored,
  `tools/tntk-gcc16-cstring.patch` (`tntk.cpp` needs `#include <cstring>`;
  recent GCC no longer pulls `memset`'s declaration in transitively, and
  `tntk.cpp:195` fails with `'memset' was not declared in this scope`
  without it — alpha's live `~/newton-dev/tntk` checkout already carried this
  fix, uncommitted and unexplained anywhere, since the original 2026-07-23
  bring-up; it is now evidence-backed and reproducible instead of tribal
  knowledge). Fetch the NTK platform file directly from UNNA
  (`http://www.unna.org/unna/apple/development/NTK/platformfiles/21PTF.ZIP`,
  the same URL `tntk`'s own upstream README points at) rather than copying it
  host-to-host — confirmed byte-identical (sha256
  `6b68a58a354e59e0454797895dae8969da97d1ff56c8515f23b18d6d4c5e4be0` for the
  renamed `Newton 2.1` file) to the copy alpha has had since first bring-up,
  so the URL is a stable, real source, not a private mirror. NEWT/0 is
  **not** a build-time dependency of the example Makefiles — only `tntk` is
  invoked — and turns out not to be a manual dependency of `tntk` either:
  current `tntk` (`f9f3f5d`) fetches its own private copy of NEWT/0's parser
  via CMake `FetchContent`. A standalone NEWT/0 build is optional and was
  done anyway for parity with alpha's environment (cheap: clean build, no
  patches needed).
  **Reproduced on mars, verified stronger than the size-only gate the track
  asked for**: mars had zero prior `~/newton-dev` and needed zero `sudo`
  package installs — `gcc` 16.1.1, `cmake`, `ninja`, `git`, `curl`, `unzip`,
  `flex`, `bison` were all already present. cDCL (`46aef57`) and `tntk`
  (`f9f3f5d`, both patches applied) were cloned and built with the exact cmake
  invocations now in `docs/host-setup.md`; `tntk` came out 309,584 bytes and
  `libDCL.so` 752,976 bytes, identical to alpha's binaries. Omitting the new
  patch reproduced the predicted compile error verbatim, confirming it is
  load-bearing and not a leftover from something unrelated. `make -C
  examples/hello` built a 1,104-byte `hello.pkg`. `make newton-packages` then
  produced `harness-loader.pkg` and `harness-client.pkg` whose SHA256 matched
  a fresh `make newton-packages` run on alpha **exactly** — not just matching
  size (the documented gate, since `tntk` stamps a build timestamp byte that
  a naive compare would defeat), but byte-for-byte identical after the
  existing `NEWTON_SOURCE_DATE_EPOCH` normalization, on independently built
  toolchains on two different hosts. No system package installs were needed
  on mars, so there is nothing pending for the human on this track.
  `docs/START-HERE.md` and `docs/dev-harness.md` now point to
  `docs/host-setup.md`. 85 tests pass (docs-only change; no test-count
  effect), `uv run --with pytest pytest -q` run from alpha before commit.

- **2026-08-04 — second hardware test feedback (MP2000, mars) → Track L.**
  The human's verdict after real use, verbatim in spirit: (1) **two packages
  is annoying** — Harness Tools should load with Chat, one install; (2)
  **naming is dev-cruft** — "Chat A9 2.4"/"ZC40" mean nothing; user-visible
  names should be the product name (Egg Freckles) and plain words (Loader);
  internal identity-bump convention stays; (3) **Ask still sends the wrong
  note** — the cat drawing loses to months-old D&D notes; the device clock
  had been set to 2008 and was corrected, so `EntryModTime` ordering is
  poisoned by bad wall-clock history (y2k-fix territory) — ordering must be
  robust to a wrong clock (candidate: `EntryUniqueID` is monotonic per store
  regardless of clock); (4) window loads off-center; Up/Dn paging beats
  nothing but native scroll arrows (eighteenth finding's untried
  `vApplication` experiment) would be better; Ask/Send/Note button labels
  confuse; (5) **the real dream is Notes-app integration**: an entry in the
  Notes Action (envelope) menu — "Send to AI" — with the reply arriving as a
  new note (maybe into a dedicated folder) or a small popup panel; Avi's
  Backdrop proves third parties can extend that menu; a floating panel beats
  a full-screen app because Newton multitasking is painful; (6) **mars must
  be self-sufficient** — toolchain on mars, one machine runs everything,
  because future users will have one machine.

- **2026-08-04 — Track A9 done: one "Ask" button, and the cat/D&D bug is
  dead.** Ships as `Chat A9` (`HarnessClientA9:jbfly`, v2.4-a9, package version
  17), building the design the probe entry below wrote. **Ask** means *send the
  newest note, whatever kind it is* — there is deliberately no second button to
  choose between and no silent skip. Round record
  `runtime/evidence/a9ask-round.txt`; results appended to
  `docs/ink-client-design.md` as "A9 result".
  - **All three routes measured on isolated instance `a9ask`**, with **real
    `codex` 0.146.0** answering every vision call. A text-only note takes the
    chat path (`MSG`, zero `/ink` POSTs). A three-stroke sketch note takes
    `/ink` and came back `Ink: The letter N is written.` A mixed note went out
    as **one** `/ink` POST carrying the strokes as `S` lines and the page's text
    as one new optional `H` line — a bare triangle plus the words "the cat" read
    back as *"A simple outline of a cat's head."* That is the whole argument for
    sending both, measured.
  - **Coordinates landed exactly.** Strokes read back with the same uniform
    `0,-36` note-origin offset the probe measured; the minimum `viewBounds`
    across the drawn items comes off in `EncodeInk`, and the host PNG renders
    the drawing where it was drawn.
  - **The modification-order fix is proven against a rigged case.** A D&D text
    note was created *after* a cat note, then the older cat page was drawn on:
    `id6 ts=64477415 mod=64477415` against `id5 ts=64477411 mod=64477418`. A7
    would answer from `id6`; A9's bounded 16-entry `EntryModTime` scan picked
    `id5` and sent its strokes. The render shows two crossing strokes kept
    separate — the property the deleted canvas never had.
  - **New ROM finding**, `docs/newtonscript-eval.md` "Nineteenth finding":
    `EntryModTime` has **one-minute granularity** (two notes touched in the same
    minute tie, and the later-*created* one still wins) and is **stale until you
    leave the note** (`Length(data)` grew while the stamp had not; it settled
    only after scrolling away). The Chat A9 flow dodges the second by
    construction — opening the chat window is leaving the page — but a `/tools`
    op would not.
  - **The InkPad-derived capture canvas is deleted, multi-stroke defect and
    all**, along with `ReadNote`/`AskNote` and the `Ink` button. The `/ink` POST
    transport it sat on is untouched and Ask reuses it; the pinned
    `async: true` count is unchanged from A8, which is what proves that.
  - 85 tests (78 + 7). **Hardware still runs A7** — the A7/A8/A9 lineage is
    emulator-only past A7, and **A9 supersedes A8**, so the human should install
    **A9 directly and skip A8**: A9 contains A8's transcript scrolling plus this.

- **2026-08-04 — sketch-note probe: the ink pivot is GO.** Research and design
  only; no client code shipped. Track I3's long-standing `[verify]` ("nobody
  has looked yet") is answered on isolated instance `sketchprobe`, and it
  answers Track E3 as well. Full finding with quoted probe output and refs
  citations: `docs/newtonscript-eval.md` "Seventeenth finding"; transcript
  `runtime/evidence/sketchprobe-probe.txt`; design
  `docs/ink-client-design.md` "Sketch-note pivot (design)".
  - **There is no sketch stationery** — the `+New` picker offers only
    Note/Checklist/Outline/Recording. The drawing tools are the **recognition
    mode**, reached from the `A` button in the Notes bottom bar at `(30, 425)`
    → **Sketches** at `(88, 402)`.
  - **A sketch note stores one item per pen stroke**, and nothing is merged or
    lost: five strokes including two that physically cross gave five items,
    271 points in 89 bytes of compressed ink. That is exactly what the client's
    own canvas could not do (finding 5 below).
  - **Extraction is proven exact.** `ExpandInk(item, 0)` takes the raw soup
    frame — no live view needed, and it works with Notes not even frontmost —
    then `CountStrokes`/`GetStroke`/`GetStrokePointsArray`. Points read back at
    the drag coordinates with a single uniform note-origin offset (`0,-36`) for
    every stroke. All three ink representations crack: `'ink2` (Sketches),
    `'poly` (Shapes), `'inkWord` (Ink Text, via `InkConvert`).
  - **The inverse works too**, which de-risks I3's write half:
    `MakeStrokeBundle` → `CompressStrokes` → `InkConvert(…, 'ink2)` round-trips
    host points into native sketching ink.
  - **Two hardware defects in shipped `Ask Note` diagnosed**, extending finding
    5 of the hardware test below. The human drew a cat, tapped Ask Note, and
    got an answer about an older D&D *text* note. (a) `ReadNote`
    (`examples/harness-client/Main.newt:675-691`) collects `'para` items only,
    so a drawing is skipped outright; (b) it orders by `timeStamp`, which is
    **creation** time — the probe note read `ts=64477370 mod=64477379`, nine
    minutes apart, because drawing moves `EntryModTime` and never `timeStamp`.
    A drawing added to an existing page therefore never becomes "newest". There
    is no `_modTime` index to order by instead
    (`Query({indexPath: '_modTime})` → `evt.ex.fr.store`), so the fix is a
    bounded 16-entry `EntryModTime` scan. A third, smaller one: an Ink Text
    paragraph leaves placeholder character **63233** in `text`, which
    `ReadNote` currently puts straight into the prompt.
  - **The design is one button, not two.** "Ask" means *send the newest note,
    whatever kind it is* — text via chat, drawings via `/ink`, and a mixed note
    in **one** `/ink` request carrying both (strokes as `NSI1` `S` lines, the
    text as one new optional `H` line). Recommended to ship in the **chat
    client (Chat A9)** rather than as a tools op, because the answer belongs in
    the user's transcript and the client already owns the transport. The
    InkPad-derived canvas is deleted when it lands, multi-stroke bug and all.
    The multi-part `/ink` POST stays unbuilt — 279 points is ~1.1 KB against a
    16 KiB cap.

- **2026-08-04 — Track A8 done: the transcript scrolls.** Ships as `Chat A8`
  (`HarnessClientA8:jbfly`, v2.4-a8, package version 16), fixing the blocker
  finding from the hardware test below. **The root cause was a unit mismatch,
  not a missing widget**: A7 handed the pane the last 640 *characters*, but the
  pane can only draw twelve *rows*, so a short-line reply (`/help`, `/status`)
  overflowed the bottom — including its newest text — with no way to reach it.
  A8 wraps the whole transcript onto the row grid itself (`WrapRows`, word-aware
  at `kRowChars := 38`), pins the paragraph to `viewLineSpacing: 14` so twelve
  rows is a measured 168 px inside the 174 px pane, and shows one window of that
  array. Two stock `protoTextButton`s, **Up** and **Dn**, page the window by ten
  rows (a window less two rows of overlap); any new line snaps it back to the
  live bottom. The `protoDivider` gives up its right half to hold them, so the
  transcript loses no height.
  **The native scroller protos were checked first and all bought nothing**:
  `SetOrigin` needs a `vClipping` parent and a child taller than it, in pixels
  the paragraph will not report (`refs/NewtonProgrammerRef20.txt:6010-6131`);
  `protoUpDownScroller` inherits `protoHorizontal2DScroller`, whose arrows work
  only "provided you specify `scrollRect`, `dataRect`, and `viewRect`
  correctly" (`:19301`, `:19417-19428`); `protoTextList` does scroll itself, but
  each item is one non-wrapping line, so the row conversion is still mine
  (`:13934-14066`). Since every design needs the row array, the row array **is**
  the fix and the windowing is three lines.
  **New ROM finding, measured**: the Newton's own scroll arrows can never reach
  this app. They go to "the frontmost view that has [`vApplication`] set"
  (`refs:3193-3199`, `vApplication` = 4), and the live float window's
  `viewFlags` read **576** = `vFloating` + `vClickable` through `ns_eval` —
  bit 4 clear. Tapping the arrows changed nothing, so the two
  `ViewScroll*Script` slots were deleted rather than shipped dead.
  Proven on isolated instance `a8scroll` (seeded flash) with the **committed**
  bytes (sha256 `123050ac…`) and `NEWTON_FAKE_BACKEND=1 server.py:6801`:
  `/help` and `/status` render whole; a 256-character prompt split into
  `MSGP part 1/2` + `2/2` and its long reply ended visibly at
  `dog 0123456789.`; **Up** then revealed the prompt block that had run off the
  top, and **Dn** returned to the exact bottom. The live conversation measured
  35 rows in a 12-row window — 23 rows that A7 could not show. The on-device
  assert grew a scroll clause and reads
  `Cap test PASS: size=6120 rows=272 first=265 0123456789…` (read back through
  `ns_eval` from `statusView.text`), which proves the 6 KiB cap *and* that the
  visible text after a page up differs from the visible text at the bottom.
  Regressions clean: short prompt, `MSGP` long prompt, New button.
  78 tests (76 + 2). Screens `runtime/evidence/a8scroll-0*.png`.
  **The physical MP2000 still runs A7** until the human installs A8 — nothing
  about this fix reaches hardware before that install.

- **2026-08-03 — first full-stack hardware test (MP2000, mars).** A7 + R10P
  installed over ZC40; chat, slash commands, agent tool calls, Ask/Save Note
  all worked on real hardware. Findings, triaged: (1) **transcript does not
  scroll** — `/status` ran off the viewport; blocker, **fixed 2026-08-04 in
  Chat A8**, see the entry above.
  (2) **Agent refused a battery question until told to use tools** — the
  system prompt never mentioned they exist; fixed `2459a48`. (3) Cosmetic
  `Communications` slip during tool calls — the known two-NIE-client noise
  (D3 finding), expected. (4) `POST /ink` 502 `Errno 2` — ops error, codex
  was not on the tools server's PATH; not a code bug; runbook lesson: both
  host services need `~/.local/bin` on PATH. (5) **InkPad canvas drops all
  but the first stroke when drawing freely** — real client defect, but per
  the human's direction it will NOT be fixed: the pivot is to send **native
  Notes sketches** instead (real drawing tools, no reinvented canvas); the
  sketch-note soup probe **passed 2026-08-04** (entry above) and is the design
  basis for "Ask Sketch", which deletes this canvas rather than fixing it.
  (5b) **`Ask Note` answered from an older text note when the human sent a
  drawing** — found on the same hardware day, root-caused by that probe to two
  causes in `ReadNote`: `'para`-only extraction, and ordering by `timeStamp`
  (creation time) when drawing only moves `EntryModTime`. Fixed by the same
  Track E3 work. (6) **Dice-from-chat failed on mars**
  — correct behavior: mars has no podman/tntk, the dev-loop tools live on
  alpha. Split-host support (MCP proxying to the dev box, or a mars
  toolchain install) is a new backlog item under Track H.

- **2026-08-03 — Track F4 done: the Newton drives its own agent.** Seven slash
  commands — `/help`, `/status`, `/model`, `/effort`, `/sessions`,
  `/new [name]`, `/resume <n|name>` — are intercepted in `server.py` before the
  backend is called and answered as ordinary `TEXT` frames. **Nothing on the
  Newton changed**: no client rebuild, no new wire op, so this is live on
  hardware **Chat A3** as it stands, and the PT100 terminal path gets it for
  free from the same code. Model and effort are **per session**, persisted in a
  new `sessions.json` registry that adopts the old single `session.json` as
  session 1, and they reach codex as `-m <model>` / `-c
  model_reasoning_effort=<level>`. Numbers beat names on a touchscreen, so
  `/model 2` and `/resume 1` work everywhere a name does.
  Proven on isolated instance `f4round` (seeded flash) with the **committed**
  Chat A7 bytes and `NEWTON_FAKE_BACKEND=1 server.py:6801`, then with the real
  backend: `/model 5` typed on the Newton, then a prompt, produced
  `codex argv: codex exec … -m gpt-5.4-mini -c model_reasoning_effort=low
  resume --json … 019fc923-c03a-7fd3-b7c7-4fe1670ebd77` — the **Track D3
  thread** — and that thread's codex rollout now records turn 1 as
  `gpt-5.6-sol/high` (D3) and turn 2 as `gpt-5.4-mini/low`. A 1997 MessagePad
  changed the model of a live codex thread. Clean screenshot of the whole
  feature with a real reply: `runtime/evidence/f4round-21-real-clean.png`.
  **Four empirical findings about this host's codex**, all in
  `docs/chat-commands.md`: valid model names come from
  `~/.codex/models_cache.json` and an invalid one is *not* a CLI error but an
  HTTP 400 mid-turn; `minimal` effort parses but the API refuses it while
  `web_search` is enabled, so the list is `low/medium/high/xhigh`; **`resume`
  does honour `-m` and `-c`** (so a model change needs no `/new`); and both
  flags must precede the `resume` subcommand or the CLI rejects `--sandbox`.
  One real defect found in **shipped** client code: `Main.newt:432` takes the
  **first** `*` in a frame as the checksum delimiter, so a `TEXT` payload
  containing one is silently truncated on screen — `/sessions` first rendered
  as a bare `3.`. The wire format allows `*` and the host parses it correctly,
  so the fix is a host-side rule: no reply may contain `*` (marker is now `>`,
  session names are stripped). A3 has the same code, so this matters for
  hardware. 76 tests (60 at baseline + 16). Round record
  `runtime/evidence/f4round-round.txt`, screens `runtime/evidence/f4round-*.png`.
  Still open: `/model` cannot list what codex would default to (it reports
  `codex default` rather than reading `config.toml`), and the A7 transcript
  clips long replies with no scroll — a client-side matter for a future round
  (**done 2026-08-04 in Chat A8**; see the top of this log).

- **2026-08-03 — publishing prep: the repo is ready to go public as "Egg
  Freckles".** Three things changed, none of them functional. (1) `README.md`
  is now a public front door — what works, an architecture diagram, an honest
  emulator-first "Try it", credits — and its old operational content moved
  verbatim to **`docs/dev-harness.md`** (ports, security boundary, emulator
  control API, package builds). The three docs that cited `README.md` by line
  number were repointed: `docs/install-lifeline-plan.md` and the two in this
  file. (2) **Apple-copyrighted material is no longer tracked.** All 11 files
  under `refs/` and the 9 NIE/NewtonIM archives under `downloads/` were
  `git rm --cached`'d (kept on disk) and are now fetched by
  **`refs/fetch-refs.sh`** and **`downloads/fetch-downloads.sh`**, in the style
  of `scripts/fetch-recovery-packages.sh`. Every URL was verified the same day:
  all 14 fetched files returned HTTP 200 from `unna.org` and hashed
  **byte-identical** to the copies this repo was developed against. Two derived
  layers also reproduce exactly — `refs/nie11/` is extracted from
  `NIEDVLPR.EXE`'s nested `DATA` zip with stdlib `python3` (no p7zip), and the
  `.txt` files are **regenerated with `pdftotext`, not downloaded**, because
  dozens of docs cite them by line number; poppler 26.07.0 reproduces all three
  byte-for-byte, and `refs/SHA256SUMS` is the check that a different poppler
  would fail loudly. `downloads/unixnpi-1.1.3.tar.gz` stays tracked: it is GPL
  C source, redistributable, 21 KB. New `refs/README.md`, `downloads/README.md`,
  and a `.gitignore` block keep the untracked binaries out of `git status`.
  `docs/START-HERE.md`'s dev loop now opens with the fetch step, because agents
  grep `refs/` constantly and a fresh clone has an empty one. (3) `LICENSE` —
  MIT, © 2026 jbfly, with a clause naming what it does *not* cover. A privacy
  sweep found nothing needing removal; the only private-infrastructure detail
  is `docs/next-hardware-session.md:74`'s `ssh jbfly@10.13.13.12` /
  `192.168.1.242`, RFC1918 addresses with no credentials, in an
  already-SUPERSEDED doc. 76 tests pass (the count includes another session's
  in-flight Track F4 work in `server.py`/`test_server.py`; nothing here touches
  either). Internal names are unchanged — Egg Freckles is the public name, the
  package identities and directory names stay as they are.

- **2026-08-03 — Track F2 done: the harness panel is one app.**
  `HarnessClientA7:jbfly` ("Chat A7", v2.4-a7) is Chat A4 plus a second control
  row — **`Ask Note`**, **`Save Note`**, **`Ink`** — and a hideable ink overlay.
  Two plain buttons rather than a toggle: `Ask Note` sends the newest stock note
  as the prompt **through the normal chat path**, so a long note splits into
  `MSGP` parts and the `No answer: LENGTH` failure is dead; `Save Note` writes
  the last reply (chat *or* ink) back as a native note with the proven
  `MakeTextNote` + `NewNote` two-step. `examples/note-export` and
  `examples/ink-capture` are deleted — their code lives in the client now.
  Proven live on isolated instance `f2round` against `NEWTON_FAKE_BACKEND=1
  server.py:6801` + `pkg_publisher.py:18081`: a 266-character note →
  `MSGP part 1/2 220B` + `2/2 46B` → `assembled 2 parts into 266B prompt` →
  reply in the transcript; `Save Note` → status `Saved note id=8` matching an
  independent `ns_eval` read of the soup; a short typed prompt right after
  logged **no** `MSGP` at all. **The E2/E3 encoder blocker is fixed**: `Encode`
  no longer adds the canvas origin to points `GetPointsArray` already hands back
  global, and the host render of an "L" drawn at screen `60,110→60,280→220,280`
  measures **x 60..221, y 110..281** instead of the old +16,+54 shift; the real
  vision call answered *"An L-shaped right angle."* and that line lands in the
  chat transcript. 60 tests. Full record `runtime/evidence/f2round-round.txt`,
  screens `runtime/evidence/f2round-*.png`.
  Three defects found in code three docs called proven, each costing one
  rebuild: (1) **`cursor:ResetToEnd()` lands *on* the last entry and returns
  it**, so note-export's `ResetToEnd(); Prev()` read the **second** newest note
  (measured: `reset=3 entry=3`, `Prev()` → 2) — a real bug in shipped
  `NoteExportN13`; (2) dropping the chat's NIE link to re-grab one for the ink
  POST fails `connect` with **-16009**, so the ink endpoint now rides the link
  the chat already holds; (3) a slot named `inkOpen` shadowed the method
  `InkOpen` (**-48200**), the `transcriptTail` trap again. Also: `vfFrameBlack`
  draws no frame without a pen width, and `scripts/newton-round.sh` now honours
  `NEWTON_INSTANCE` so a round can run off the shared emulator.
  Still open: hardware is **still on A3**, and F3 (a true Notes panel that grabs
  the *currently open* note) is untouched.

- **2026-08-03 — Track G done: an agent built a Newton app end to end, first
  build.** G1 is `docs/agent-dev-loop.md` — ten numbered steps from
  `cp -r examples/hello` to teardown, with the identity rule, the `tntk` patch
  caveat, the raw `/packages/` install path and a footgun table. G2 proved it:
  one `codex exec` run (host, MCP `newton`, `approve` mode) was told to build
  **NewtonDice** (`Dice1:jbfly`, a floating window whose **Roll** button shows a
  random 1–6) into a new `examples/dice` on isolated instance `gloop`. It read
  the runbook, then ran the loop in **six MCP calls with no failures and no
  intervention**: `build_pkg` (compiled first try) → `emulator_install
  /packages/dice/dice.pkg` → `emulator_newtonscript
  GetRoot().|Dice1:jbfly|:Open()` → `emulator_screen` (window + `Roll` button)
  → `emulator_tap(220,218)` → `emulator_screen` (`-` had become `1`). This is
  also the first time any `emulator_*` tool has been driven by an agent rather
  than by tests, which closes one of the two gaps the previous "Next up" named.
  Independently re-verified with six more `curl` taps: `1 3 2 3 3 1`. Evidence
  `runtime/evidence/gloop-codex-transcript.txt`, `gloop-02-codex-launched.png`,
  `gloop-03-codex-after-tap.png`, `gloop-verify-rolls.txt`,
  `gloop-verify-roll1..6.png`; the app is committed as `examples/dice`. One new
  finding: **a `protoFloatNGo` does not render at its declared `viewBounds` x**
  (declared `left: 60`, rendered `x=112`, right edge 8 px inside the screen)
  while its y matched exactly — so tap coordinates come off a screenshot, never
  off the source (`docs/newton-dev-notes.md` Track G round). G2's optional
  hardware half (install `Dice1` on the MP2000 via ZC40 after a `store_info`
  check) was **not** done — it needs the human, and it is the same gate as E2.
  55 tests, measured in a detached worktree holding HEAD plus exactly this
  track's files: the shared working tree showed 53 passed / 2 failed at the
  time, both from another session's in-flight Chat **A5** edit to
  `examples/harness-client` (Track F2), not from Track G.

- **2026-08-03 — Track F1 done (proven on the emulator).** The 240-byte
  single-frame prompt cap is lifted. New client → host op
  `:SS MSGP KK NN <chunk>*HH` (two-digit part/total, 220-character chunks,
  8 KiB assembled cap) documented as an extension in `docs/phase3-protocol.md`;
  `MSG` and every other op are byte-for-byte unchanged and an old client keeps
  working. `Chat A4` (`HarnessClientA4:jbfly`, v2.4-a4) splits anything over
  227 characters and sends the parts stop-and-wait on the existing ACK
  machinery. Live on isolated instance `f1round`: a 378-character typed prompt
  → `MSGP part 1/2 220B` + `part 2/2 158B` → `assembled 2 parts into 378B
  prompt` → 453-character reply rendered on the Newton
  (`runtime/evidence/f1round-round.txt`, `f1round-12-reply.png`); a short
  prompt straight after it logged no `MSGP` at all. 55 tests.
  The round also found a **pre-existing A3 bug**: `StrPos(text, Chr(13), 0)`
  raises `-48802` on this ROM, so the transcript froze the moment it passed 640
  characters. Fixed with a hand-rolled `FindBreak`; see
  `docs/newton-dev-notes.md` Track F1 round and the footgun table in
  `docs/newton-networking-lessons.md` §2. The note bridge still sends a single
  `MSG` — moving it onto `MSGP` is part of F2.

- **2026-08-03 — Track A done.** A3/A5 `3ca0b94` (spikes deleted, old staged
  loaders untracked; true test count was 40 not the documented 30 — now 37);
  A4/A6 `923ae43` (untracked debris archived to
  `~/newton-archive/newton-harness/` — 9 flash snapshots + 100 logs; patch
  audit found **all 9 patches applied**, nothing to archive); A1/A2/A7
  `46565a1` (superseded banner, ink claims fixed, `examples/README.md`);
  A8 `65caa6f` (`drag`/`install`/`newtonscript` CLI subcommands, README
  endpoint table).
- **2026-08-03 — Track B done.** `2786479`: `docs/install-paths.md` (the one
  blessed install story) + `make stage-hw PKG=<dir>` (dry-run verified with
  `examples/hello`).
- **Open decisions resolved 2026-08-03:** superseded sources deleted (git
  history retains); archive location is `~/newton-archive/newton-harness/`;
  Track D stays codex + MCP.
- **2026-08-03 — Track C1–C3 done (proven over the wire).** The `POST /tools`
  acceptance round ran on isolated instance `c2round` against
  `runtime/raw_pkg_server.py` on `10.42.0.1:18081`; the broker logged
  `Newton tools connected` and all three ops answered. Wire replies:
  `battery` → `count=0 cap=100% charge=discharging ac=no type=nimh`;
  `store_info` → `Internal total=7638048 used=883236 free=6754812 ro=n`;
  `pkg_list` → `count=39`, id 1 → `1/39 ScreenBuffer|428|?`, id 39 →
  `39/39 PT100:Scrawl|174416|Internal`, id 99 → HTTP 422
  `package ordinal must be 1..39`. **~0.8 s per device-touching op** on the warm
  link (`ping` 0.05 s). Full `curl -i` transcripts in
  `runtime/evidence/toolsround-r10m-wire-*.txt`, Extras drawer in
  `runtime/evidence/toolsround-r10m-wire-screen.png`.
  The round found one real defect that `ns_eval` could not have found:
  **`StringToNumber` returns a `Real` on this ROM**, and indexing an array with
  a `Real` throws `evt.ex.fr.type;type.ref.frame`, so `R10M`'s `pkg_list` failed
  on *every* valid ordinal over the wire
  (`runtime/evidence/toolsround-r10m-wire-pkg-list-1-r10m-bug.txt`). Fixed by a
  one-line `Floor` at the dispatch site and shipped as
  **`HarnessToolsR10N:jbfly`**; details in `docs/newtonscript-eval.md`
  fourteenth finding. Also learned: seeding a fresh instance's
  `/state/internal.flash` from a saved NIE-configured flash replaces the whole
  tour + `newtdev`/`NE2K` + Internet Setup dance and takes ~90 s
  (`docs/parallel-emulators.md`, "Seed an instance from a saved flash"); and
  `GetPackages()` ordering is not stable across a reboot.
- **2026-08-03 — Track C1–C3 code round (`af6be49`, `1dd099a`) — the transport
  claim in it is superseded by the entry above.** `examples/harness-tools`
  bumped `R10L`→`R10M` and gained `battery`, `store_info`, `pkg_list` on the
  existing `StrEqual` dispatch; no host-side change was needed (generic
  `POST /tools` pass-through, C6 note below). API choices verified against
  `refs/` before coding — `BatteryLevel` is documented-obsolete,
  `BatteryStatus`/`GetStores` sizes/`GetPackages` are the real calls; details
  and citations in `docs/newtonscript-eval.md` thirteenth finding. Each op's
  expression was evaluated on isolated instance `c1round` via
  `runtime/ns_eval.py` (`runtime/evidence/toolsround-r10m-nseval.txt`), which
  proved the *system calls* but, as the wire round later showed, not the
  dispatch path. Two mechanics learned and documented: `POST /install` takes a
  raw `/packages/…` path, not a `curl -F` upload (`docs/install-paths.md`
  row 1), and a fresh `make emulator-instance-up` Newton is *not* network-ready
  — since fixed by flash seeding rather than by hand.
- **2026-08-03 — Track D1 code done** (its live demo ran the same day, see the
  D3 entry below). `newton_mcp.py` —
  one stdlib-only file, MCP over stdio (JSON-RPC 2.0, hand-rolled
  `initialize`/`ping`/`tools/list`/`tools/call`) exposing `newton_tool`,
  `emulator_screen/tap/text/key/newtonscript/install`, `build_pkg`, `stage_hw`.
  D2's rails are folded in **as code**: mutating emulator ops refuse the shared
  instance unless `NEWTON_ALLOW_SHARED=1` (screen always allowed), `newton_tool`
  refuses device-mutating op names with the human's `curl`, and there is no
  physical-install tool at all. Registered with `make server-mcp`
  (`codex mcp add newton -- python3 /app/newton_mcp.py`, writes
  `[mcp_servers.newton]` into the `codex-home` volume, same pattern as
  `make server-login`); `containers/server.Dockerfile` copies the file in;
  `server.py` unchanged. `test_newton_mcp.py` adds 8 tests (45 total).
  **Measured networking finding** (`docs/agent-tools.md`): from the server
  container `10.42.0.1:<port>` on the host **is** reachable — so `newton_tool`
  works in-container — but host `127.0.0.1` is refused, so every `emulator_*`
  tool (control ports are published on `127.0.0.1` only, and `instance_url`
  needs `podman`) plus `build_pkg`/`stage_hw` require running `server.py` on
  the host. Also observed this session: `10.42.0.1/24` **is** now on `lo`
  (`ip -4 addr show lo`), so the C1–C3 acceptance blocker is gone — that round
  has since run, see the C1–C3 entry above.
  The two unverified items in this entry were **settled by D3 below**: no, and
  no.
- **2026-08-03 — Track E1 done (visible ink).** `examples/ink-capture` is now
  `InkPad2:jbfly` v2: one `MakePolygon` retained per stroke, painted in a
  `ViewDrawScript` on the capture view, with `Dirty()` + `RefreshViews()` at
  capture / `Undo` / `Clear` and a new `Undo` button. The Stage 4 `[verify]`
  is settled in both directions — `MakePolygon` *does* take the flat array
  (`ClassOf(...)` → `'polygon`), but as **x,y** pairs while `GetPointsArray`
  returns **y,x** global coordinates, proved by
  `ShapeBounds(MakePolygon([0,0,100,10,0,20]))` → `0/0/101/21` and by a drag
  from screen `60,100` retaining `y0=100 x0=60`. No `MakeLine` loop, no manual
  binary, and the figure is not auto-closed (a hand-injected bent stroke drew
  as an open "L"). Proven on isolated instance `e1ink` (flash-seeded, no
  network, no `/ink` POST): three `/drag` strokes stayed visible after pen-up,
  `Undo` removed only the last, `Clear` wiped all — `runtime/evidence/e1ink-*`
  and `docs/ink-client-design.md` "Stage 5 result". The round also found a
  defect it did not fix: `Encode()` adds the ink view's origin to points that
  are already global, so the host's render is shifted +16,+54 — folded into
  **E2**, which stays open along with hardware install.
- **2026-08-03 — Track D3 done: the keystone demo is live.** From Chat on an
  emulated Newton (isolated instance `d3demo`, seeded flash), the typed prompt
  *"use your newton tools. what app is in front, how much free space, and how
  many packages are installed."* came back on the Newton's own screen 19
  seconds later as **"Front app: Notepad (paperroll) / Free space: 6,758,976
  bytes (6.45 MiB) / Installed packages: 39"**. Three `newton_tool` calls ran
  inside that one turn — `front_app` 0.127 s, `store_info` 0.805 s, `pkg_list`
  0.796 s — so the model, not the Newton, is the latency. The numbers are
  device-derived: a pre-flight `curl` before `HarnessClientA3` was installed
  read `free=6778912`/`count=38`, one package fewer. Evidence:
  `runtime/evidence/d3demo-screen.png`, `…-chat-turn.txt`, `…-mcp-verify.txt`,
  `…-prompt-typed.png`; page is `docs/agent-tools.md`, now flipped to
  live-proven. **Both `[verify]` items are settled and one was a real
  blocker:** (1) `codex exec` does **not** auto-approve MCP tool calls — the
  call fails with `user cancelled MCP tool call` until the server entry carries
  `default_tools_approval_mode = "approve"` (valid values `auto`/`prompt`/
  `writes`/`approve`; `codex mcp add` has no flag for it, so `make server-mcp`
  now writes it and the host registration has it by hand); (2) the MCP
  subprocess is **not** inside `--sandbox read-only` — `build_pkg` wrote a real
  `.pkg` under that flag, so no `--add-dir` is needed *and* the sandbox is not
  a rail for this surface, only `newton_mcp.py`'s own D2 rails are.
  `server.py` ran on the **host** per the container-networking finding, and
  `HarnessClientA3` needed no rebuild — its hardcoded `10.42.0.1:6801` reaches
  a host process on the `lo` alias just like the tools long-poll. Two
  operational notes: the tools client and the chat client coexist on one Newton
  but the tools client's reconnect throws a cosmetic modal `Communications`
  slip over the chat window mid-turn; and `xdotool` typing drops the first
  characters and mangles shifted keys, so tap, wait, then type in chunks.
- **2026-08-03 — Track C4 done (proven over the wire).** `HarnessToolsR10P:jbfly`
  adds `note_list` and hardens `get_note`; the acceptance round ran on isolated
  instance `c4round` (seeded flash) against `runtime/raw_pkg_server.py` on
  `10.42.0.1:18081`, broker logged `Newton tools connected 10.42.0.1:57652`.
  Wire replies: `note_list` → `count=6`, id 1 → `1/6 (untitled)|64461125`,
  id 4 → `4/6 C4 alpha note about batteries|64477198`, id 6 →
  `6/6 C4 charlie note that is delibera...|64477198`, id 7 and id 99 → HTTP 422
  `note ordinal must be 1..6`; `get_note` id 6 → the whole 89-character note,
  id 1 → `""`; `ping` and `battery` unchanged. ~0.8 s per device-touching op
  (`ping` 0.127 s). Evidence `runtime/evidence/c4round-*.txt` (summary in
  `c4round-wire-summary.txt`, ROM probes in `c4round-nseval.txt`, the three
  notes rendered in stock Notepad in `c4round-screen.png`). Three things
  learned, all in `docs/newtonscript-eval.md` fifteenth finding:
  **`cursor:CountEntries()` works on this ROM** and walks the index rather than
  the entries, so counting does not reintroduce the twelfth finding's
  starvation; **a nil `title` is the normal case** for a Notepad entry, so the
  listing label falls back to the note's first 32 characters; and **`ns_eval`
  cannot see NTK platform constants** such as `ROM_paperRollSoupName` — they are
  compile-time symbols, so probing with one throws
  `evt.ex.fr.intrp;type.ref.frame` and you must use the literal (`"Notes"`).
  Also confirmed: the three Notepad entries inside the seed flash are the
  `data=nil` failed writes `docs/notes-bridge.md` diagnosed in N2/N3.
- **Next up (2026-08-03, after G):** the remaining work splits cleanly.
  **Needs the human and the bench:** E2 (the ink client on hardware — its
  doubled `Encode()` origin is **fixed and wire-proven** as of F2, so only the
  hardware half is left), and every other hardware deploy — Chat A7, the tools
  client, `Dice1` — since the whole tools channel has still never run on the
  **physical** MessagePad and there is no tool that installs there by design.
  **Agent-sized and unblocked:** C5 (`pkg_install`/`pkg_remove` ops, still
  human-gated at the device), E3 (multi-part `/ink` POST), F3 (true Notes
  integration, genuinely unexplored), then the Track H backlog. `stage_hw` is the one MCP tool no
  agent has driven yet; G exercised all six `emulator_*` calls it needed.

**The vision, in one paragraph.** The Newton runs a small harness panel that
can send the current note — text *or* ink — to an agent and get replies back
as notes. The agent has tools to manage the device: see status and battery,
list/read/write notes, check free space, install and remove packages. The
same agent can design a new Newton app, build it with the host toolchain,
test it in an isolated Einstein instance (screenshots, taps, ns_eval), and —
behind a human gate — install it on the physical MP2000, then iterate:
delete the old version, install the new one. Modern LLMs paper over the
Newton's weak handwriting recognition by reading ink directly. Long term:
lower-level development (games, richer UIs) on the same rails.

## Where we are (2026-08-03, all claims audited against source)

Hardware-proven and current:

- **Chat**: `examples/harness-client` (`HarnessClientA8:jbfly`, "Chat A8"; the
  physical MP2000 runs A7) ↔ `server.py:6801`, framed ASCII protocol,
  codex backend via `codex exec` subprocess. One turn in flight; since Track F1
  a prompt over 227 characters goes as `MSGP` parts and the host reassembles up
  to 8 KiB. Since Track F2 it is the **harness panel**: `Ask Note` sends the
  newest note down that same path, `Save Note` writes a reply back as a native
  note, and `Ink` opens the capture canvas whose reading joins the transcript
  (`POST /ink` on 18081). Emulator-proven.
- **Install path**: `examples/harness-loader` (`-Loader1:jbfly`, Extras label
  "Loader"; the device still runs `-HarnessLoaderZC40:jbfly` until it is
  upgraded) pulls any staged `.pkg` over WiFi from `runtime/dual_send.py` on
  18081. ZC39 is the installed deep fallback. NS Basic bootstrap (`bootstrap/`) is the bare-metal
  lifeline; Newt's Cape and Dock TCP are preserved in `downloads/recovery/`.
- **Backup/inventory**: `runtime/newton_backup.py` speaks real Dock protocol
  (DES auth, NSOF); produced `docs/installed-package-inventory.md`.

Emulator-proven, **not yet on hardware**:

- **Tools channel**: `examples/harness-tools` (`HarnessToolsR10P`) long-polls
  `pkg_publisher.py`'s `ToolBroker` on 18081; emulator-proven ops are `ping`,
  `front_app`, `get_note`, `note_list`, `note_probe`, `battery`, `store_info`,
  `pkg_list` — the last three travelled the real link on 2026-08-03
  (`runtime/evidence/toolsround-r10m-wire-*.txt`, `docs/newtonscript-eval.md`
  thirteenth finding) and `note_list` + `get_note` v2 the same day
  (`runtime/evidence/c4round-*.txt`, fifteenth finding). Host API:
  `POST /tools` (`pkg_publisher.py:354-385`).
  Median 0.3–0.8 s per call on the warm link.
- **Ink**: built end to end and now **inside the chat client** (Track F2; the
  separate `examples/ink-capture` is deleted). The canvas captures strokes with
  `GetPointsArray`, retains one `MakePolygon` per stroke in a `ViewDrawScript`
  (Stage 5), encodes NSI1 and POSTs `/ink`; the host renders a PNG (stdlib
  Bresenham, `pkg_publisher.py:241-278`) and calls a vision model whose one
  sentence lands in the chat transcript. Six staged results in
  `docs/ink-client-design.md`; the `Encode()` doubled-origin defect is **fixed
  and measured on the wire** ("Track F2 result").
- **Notes**: also inside the chat client (`examples/note-export` deleted).
  `Ask Note` reads the newest note and sends it as an ordinary prompt — no
  `/note` request — and `Save Note` creates a native note via the proven
  two-step `MakeTextNote(answer, nil)` + `NewNote` path.

The critical architectural gap was: **the agent has no tools.** `/tools`,
`/ink`, the emulator control API, and the build toolchain all existed as
separate host surfaces that a *human* curled, and nothing let the agent behind
the chat session call them. **Closed 2026-08-03** by Track D: `newton_mcp.py`
exposes them as MCP tools (`docs/agent-tools.md`), and on 2026-08-03 a prompt
typed into Chat on an emulated Newton drove three of them and answered with the
device's own numbers (D3 entry above). Track G then closed the other half: on
the same day an agent drove `build_pkg`, `emulator_install`,
`emulator_newtonscript`, `emulator_screen` and `emulator_tap` to build a new
app and show it running (G2 entry above). What is left is breadth, not shape —
`stage_hw` has still only been run by tests, and none of it has run against the
physical MessagePad.

## Track A — repo cleanup and doc truth (first; one cheap-agent session)

Goal: an agent landing in this repo finds only current things, and no doc
tells it to do something destructive.

- **A1. Neutralize the dangerous doc.** `docs/next-hardware-session.md` is a
  complete pre-ZC40 session plan; its Step 5 (`:359-377`) instructs deleting
  every loader except `ZC34 Loader 2.0` — six generations behind current.
  The 2026-08-02 hardware session it plans for already happened. Add a
  `> **SUPERSEDED 2026-08-02**` banner at the top pointing to
  `docs/installed-package-inventory.md` and `docs/hardware-bench-runbook.md`.
  Do not delete the doc; its NIE/AP appendices are still cited.
- **A2. Fix the stale ink claim.** `docs/START-HERE.md:44` says ink is
  "Entirely unbuilt". Reality: stages 1–4 verified, results appended to
  `docs/ink-client-design.md`. Update the table row and the doc's own header.
  Per `CLAUDE.md`, grep for other copies of the claim.
- **A3. Delete superseded spike code** (git history keeps everything):
  `examples/harness-tools-persistent/` + `runtime/persistent_tools_server.py`
  + `test_persistent_tools_server.py` (self-described "Disposable" spike,
  wrong port, blocking I/O — `runtime/persistent_tools_server.py:2`), and
  `examples/network-probe/` (early diagnostic; deleting source does not
  affect the copy still installed on the device). Update
  `docs/START-HERE.md:83`'s note about silently-skipped tests.
- **A4. Sweep untracked round debris** (all gitignored, zero git risk):
  seven throwaway listeners in `runtime/` (`round5/6/7_*listener*.py`,
  `sniff18081.py` — keep `raw_pkg_server.py`, it's cited by six docs), stale
  `*.pid` files, `runtime/ns-eval-image-build.log`, `runtime/logs/` round
  debris. Move `runtime/backups/internal-before-round*.flash` (15 × 8 MB,
  rounds 3–9, superseded by `runtime/emulators/mp2000-core-20260803/`) to
  `~/newton-archive/` rather than deleting — they are backups.
- **A5. Untrack superseded staged builds**: `runtime/staging/hardware/`
  ZC37/ZC38 loaders and `harness-client-a1.pkg`. ZC39 stays (documented live
  fallback), ZC40 and A3 stay.
- **A6. Audit `containers/patches/`**: the five `einstein-tcp-*`/
  `einstein-nie-rom-trace` diagnostic patches date from the closed rounds 3–8
  TCP investigation. Check `containers/emulator.Dockerfile` for which patches
  are actually applied; move unapplied ones to `containers/patches/archive/`
  with a README line each.
  **Audited 2026-08-03: all 9 patches, including all five suspected-unapplied
  diagnostic ones, are applied by `containers/emulator.Dockerfile`'s single
  `RUN` block (`git apply` calls at lines 37–44); `git blame` shows they were
  added during the TCP investigation (`8b471e0`, `2ddc8cc`, `6680ef1`) and
  never removed. Nothing archived; `containers/patches/` is unchanged.**
- **A7. Add `examples/README.md`** — a 10-line table: package, identity,
  status (current / smoke-test / seed-for-Track-X), where it runs. This is
  the cheap alternative to renaming `examples/` (renaming would break dozens
  of doc references and the `compose.yaml:41` mount for no functional gain).
- **A8. Fix README drift**: endpoint table (then in `README.md`, now
  `docs/dev-harness.md`, "Agent screen and input control") omits
  `/drag`, `/install`, `/newtonscript`; add the missing `emulator.client`
  subcommands note or (5 lines) add `drag`/`install`/`newtonscript`
  subcommands to `emulator/client.py`.

Acceptance: `uv run --with pytest pytest -q` still passes (count drops by the
3 deleted spike tests); `grep -ri "ZC34 Loader"` finds only the banner-ed doc
and history; `make newton-packages` unaffected.

## Track B — one blessed install story (one cheap-agent session)

Today three host listeners can serve packages (`pkg_publisher.py`,
`runtime/raw_pkg_server.py`, `runtime/dual_send.py`) and the knowledge of
which to use lives in five docs. Streamline by documentation and one target,
not by rewriting servers:

- **B1.** Write `docs/install-paths.md` — one page, one table:
  | Situation | Path | Command |
  with exactly three rows: (1) emulator → `scripts/newton-round.sh` /
  `POST /install`; (2) physical, normal → `dual_send.py` on 18081 + ZC40
  loader taps; (3) physical, bare-metal recovery → NS Basic bootstrap →
  Newt's Cape / Dock TCP (pointers into `docs/install-lifeline-plan.md`).
  State plainly: `dual_send.py` is *the* 18081 listener
  (`docs/newton-networking-lessons.md` §4.9); `raw_pkg_server.py` is
  historical; `pkg_publisher.py`'s pkg-serving is for the tools/ink/note
  channel, not the loader.
- **B2.** Add `make stage-hw PKG=<dir>`: build + copy to
  `runtime/staging/hardware/` + refresh SHA256SUMS + print the exact
  filename to type into ZC40. (The typing cost on the device is the human
  interface; keep filenames short — `docs/install-lifeline-plan.md:170-180`.)
- **B3.** Fold the `dual-send` systemd user unit instructions
  (`runtime/dual-send.service`, currently documented only inside the
  superseded `next-hardware-session.md:96-106`) into `install-paths.md`.

## Track C — tools channel v2: device management ops (2–3 sessions)

Grow `examples/harness-tools` (R10P lineage) into the device-management
surface the agent needs. Fixed-op dispatch stays (arbitrary eval is a proven
dead end — `docs/newtonscript-eval.md`; four investigations reverted). New
ops, each one session-sized with its emulator acceptance test:

- **C1. `battery` — done 2026-08-03**, proven over the wire in `R10N`.
- **C2. `store_info` — done 2026-08-03**, proven over the wire in `R10N`.
- **C3. `pkg_list` — done 2026-08-03**, proven over the wire in `R10N`. Note
  its `size` is uncompressed bytes, so it does *not* match the Dock counts in
  `docs/installed-package-inventory.md`.
- **C4. `note_list` / `get_note` v2 — done 2026-08-03**, proven over the wire
  in `R10P`. `note_list` is paged exactly like `pkg_list` (`count=N`, then one
  `i/N <label>|<timeStamp>` line per request, ordinals capped at 64) and counts
  with `cursor:CountEntries()`, which walks the index rather than the entries.
  `get_note` keeps its reply shape and gains the nil-guard + `Floor` at its
  dispatch site. Details in `docs/newtonscript-eval.md` fifteenth finding.
- **C5. `pkg_install <name>` / `pkg_remove <name>`** — reuse ZC40's proven
  VBO receive + `SuckPackageFromBinary` code inside the tools client;
  removal API `[verify]`. **Human gate on physical hardware, always**
  (`docs/notes-bridge.md:16`).
- **C6. Rehost ToolBroker — deferred, no longer a prerequisite.** Two facts
  found 2026-08-03: (1) the host `POST /tools` route is a **generic
  pass-through** — any op name matching `TOOL_OP` is forwarded and the
  Newton client answers `unknown_op` for names it lacks
  (`pkg_publisher.py:354-386`), so C1–C5 need *only* Newton-side changes
  (plus host arg validation if a new op takes args beyond `id`); (2) the
  tools long-poll and package serving **share port 18081 by design** (the
  `POLL` hijack, `pkg_publisher.py:284-292`), so splitting them means either
  a new port (client rebuild + identity bump) or a pointless rename. Revisit
  only if the file becomes genuinely hard to work in.

Constraint carried from the wire: keep every op's reply ASCII and small;
the 3 s host heartbeat and >3 s client watchdog relationship is load-bearing
(`docs/newton-networking-lessons.md` §2 footgun table).

## Track D — give the agent the tools (the keystone; 2–3 sessions)

Make the agent behind chat able to *act*. Recommended shape: a small **MCP
server** (stdlib-thin, one file) exposing:

- `newton_tool(op, args)` → `POST /tools` on 18081 (physical or emulator);
- `emulator_*` → the `emulator/control.py` HTTP API (screen, tap, drag,
  text, key, install, newtonscript) against a *named instance*, never the
  shared `newton-harness_emulator_1` without explicit opt-in;
- `build_pkg(dir)` → `make`/`tntk` build returning the staged path;
- `stage_hw(pkg)` → Track B's staging (install itself stays human-gated).

`codex exec` supports MCP servers via its config, so `server.py`'s backend
gains these without changing the chat wire protocol. If the backend ever
switches to Claude, the same MCP server plugs in. Steps:

- **D1. Done 2026-08-03.** `newton_mcp.py` written and registered
  (`make server-mcp`, or `codex mcp add newton` on the host);
  `docs/agent-tools.md` is the page. Its acceptance — a chat turn from the
  Newton client whose answer comes from `front_app` — passed as part of D3.
- **D2. Done 2026-08-03, in code.** Rails live in `newton_mcp.py`, not in a
  prompt: device-mutating `newton_tool` ops return "needs human confirmation"
  with the exact command; the shared emulator refuses mutating ops without
  `NEWTON_ALLOW_SHARED=1` while `emulator_screen` stays open; no
  physical-install tool exists in the surface at all. Tested in
  `test_newton_mcp.py`.
- **D3. Done 2026-08-03 — gate passed.** From Chat on the emulated Newton, one
  prompt drove `front_app`, `store_info` (C2) and `pkg_list` (C3) and answered
  `Free space: 6,758,976 bytes (6.45 MiB)` / `Installed packages: 39` on the
  device's own screen. Status log entry above; `docs/agent-tools.md` "The live
  demo (D3)"; `runtime/evidence/d3demo-*`.

## Track E — finish ink and the HWR-assist loop (2 sessions)

- **E1. Visible ink — DONE 2026-08-03.** `InkPad2:jbfly` retains one
  `MakePolygon` per stroke and paints them in a `ViewDrawScript`, and gained
  the `Undo` button. `MakePolygon` takes the flat array but as **x,y** pairs,
  so `GetPointsArray`'s y,x order is swapped and the ink view's origin
  subtracted; no per-segment `MakeLine`. See `docs/ink-client-design.md`
  "Stage 5 result" and `runtime/evidence/e1ink-*`.
- **E2. Install the ink client on hardware** via the Track B path; first real
  stylus drawing → vision model round trip. **Half done 2026-08-03**: the
  `Encode()` doubled origin is fixed and proven over the wire in Track F2 (host
  render of an "L" drawn at `60,110→60,280→220,280` measures x 60..221,
  y 110..281), and the ink client is now the chat client, so the hardware step
  is one ZC40 install of `HarnessClientA7` — which is the same human gate as
  every other hardware deploy.
- **E3. "Ask Sketch" — the capture canvas is replaced by native Notes.**
  Designed 2026-08-04 and evidence-backed; **not built**. The old E3 ("send a
  note's ink to the agent, get clean text back") is subsumed: the probe proved
  every stroke of a stock sketch note comes out with exact geometry
  (`docs/newtonscript-eval.md`, "Seventeenth finding"), so the flow is one
  content-aware button rather than a second feature.
  - **`Ask Note` becomes `Ask`**: read the newest note, classify its `data`,
    and route — `'para` only → the chat path unchanged; any `'poly`/`'ink2`
    → the `/ink` vision path; **both → one `/ink` request carrying both**, the
    strokes as `NSI1` `S` lines and the text as one new optional `H` line.
    Never silently skip either half.
  - **Two hardware defects it must fix**, both diagnosed on the probe:
    `ReadNote` extracts `'para` only and refuses a drawing outright, and it
    orders by `timeStamp`, which is *creation* time — a drawing added to an
    existing page never becomes "newest", and there is no `_modTime` index to
    order by instead (`Query({indexPath: '_modTime})` throws `evt.ex.fr.store`).
    Fix is a bounded 16-entry `EntryModTime` scan.
  - **Ships in the chat client (Chat A9), not a tools op** — the reply belongs
    in the user's transcript and the client already owns the NIE link, the
    async `/ink` POST and the `INK ` reply parsing. Reasoning and the rejected
    alternative are in `docs/ink-client-design.md`, "Sketch-note pivot
    (design)".
  - **The InkPad-derived canvas is deleted** when this ships, and its
    multi-stroke bug with it, unfixed.
  - **The multi-part `/ink` POST is NOT needed** and stays unbuilt. The probe
    note's 9 items and 279 points encode to roughly 1.1 KB against the 16 KiB
    cap (`pkg_publisher.py:313`); `?part=k&of=n` remains specified-but-unwritten
    in `docs/ink-client-design.md` until a real drawing exceeds it.

## Track F — the harness panel (Chat A4/A7; 2–3 sessions)

Evolve the chat client toward the panel-over-Notes dream, incrementally:

- **F1. Multi-frame prompts — DONE 2026-08-03.** `MSGP KK NN <chunk>` shipped
  in `Chat A4`; grammar and host state machine in `docs/phase3-protocol.md`,
  "Extension: `MSGP`"; status log entry above. The note bridge was folded onto
  it by F2, so `No answer: LENGTH` is gone. Everything since A3 is
  emulator-proven only — the physical MP2000 still runs A3.
- **F2. The harness panel — DONE 2026-08-03**, shipped as `Chat A7`
  (`HarnessClientA7:jbfly`, v2.4-a7) rather than A5: three identity bumps were
  spent inside the round, one per defect found (see the status log). `Ask Note`
  + `Save Note` + an `Ink` overlay, all in one app; the note path rides the
  normal chat `MSG`/`MSGP` transport instead of `POST /note`; the ink encoder's
  doubled origin is fixed. `examples/note-export` and `examples/ink-capture` are
  deleted, per the Track A rationale. Status log entry above; round record
  `runtime/evidence/f2round-round.txt`.
- **F3. True Notes integration** (later): a floating `protoFloatNGo` panel
  or a Notes auxButton that grabs the *currently open* note rather than the
  newest. API surface `[verify]` — this is genuinely unexplored.
- **F4. Claude-Code-style session and model control — DONE 2026-08-03.**
  `/help`, `/status`, `/model`, `/effort`, `/sessions`, `/new [name]`,
  `/resume <n|name>`, answered in `server.py` **before** the backend runs, as
  ordinary `TEXT` frames. No client change, no wire change — so it works from
  hardware **Chat A3 unchanged**, from emulator Chat A7, and from the PT100
  terminal path. Model and effort are per session and reach codex as `-m` /
  `-c model_reasoning_effort=`, placed before the `resume` subcommand; state
  lives in a `sessions.json` registry that absorbs the old single
  `session.json` as session 1. Bare `/new` keeps its exact pre-F4 reply
  because A7's New button sends it. Page: `docs/chat-commands.md`; status log
  entry above; round record `runtime/evidence/f4round-round.txt`.

## Track G — agent-driven app development loop (after D; 2 sessions)

The "ask for an app, watch it appear" loop. All the parts exist; this track
is glue + a runbook:

- **G1. Done 2026-08-03.** `docs/agent-dev-loop.md` — ten numbered steps:
  scaffold from `examples/hello`, fresh identity (`-10402` rule), build with
  `build_pkg` (`tntk` + vendored patch — without it every rebuild silently
  regresses to version 1), isolated + flash-seeded emulator, install with the
  raw `/packages/` path, launch, screenshot, tap, iterate, tear down. It also
  records that `scripts/newton-round.sh` does **not** fit a new app on an
  isolated instance (it drives the shared container and needs a `kVersion` tag
  the scaffold lacks), so a new app bumps its identity by hand.
- **G2. Done 2026-08-03 — gate passed.** codex built `Dice1:jbfly`
  ("NewtonDice") into `examples/dice` on isolated instance `gloop` in six MCP
  calls with no intervention and no failed build, and the screenshots show the
  app working. Status log entry above; `docs/agent-dev-loop.md`
  "Proven 2026-08-03"; `runtime/evidence/gloop-*`.
  **Still open:** the hardware half — the human installing it on the MP2000 via
  ZC40 after a `store_info` free-space check. `stage_hw` makes that one command
  away, but the install itself is gated (`docs/agent-tools.md` rail 3).

## Track H — backlog (not scheduled)

- Lower-level development: NCT/C++ toolchain research for games and custom
  drawing — a survey session against `refs/` and UNNA before committing.
- Serial Dock lifeline proof (one bench afternoon —
  `docs/install-lifeline-plan.md` §4).
- Portable networking (PLAN.md phase 5).
- Backend abstraction (Claude alongside codex) — only if/when wanted; the
  MCP design in Track D already keeps this cheap.
- Reboot-persistent host services (`dual-send` unit exists; server/emulator
  units don't — `docs/dev-harness.md`, "Verification status").

## Track I — image generation on the Newton (designed 2026-08-03, not started)

Requested by the human 2026-08-03; also the original `PLAN.md` phase 4 item
("image gen, Newton-optimized dithered grayscale, 320x480 portrait"). Ask for
an image in chat, get a Newton-friendly version back — as a bitmap on screen,
or ideally as a native note.

- **I1. Host pipeline.** Prompt → image API (the codex CLI does vision *in*,
  not generation *out* — pick and wire an image-generation backend; the
  OpenAI images API off the same account is the obvious candidate, decision
  open) → downscale to 320×480 portrait → grayscale → dither. Use Atkinson
  dithering (the period-correct Apple algorithm) to the MP2000's 4-bit
  (16-level) panel; 1-bit fallback. Pure-stdlib PNG handling already exists
  (`pkg_publisher.py` writes PNGs with zlib/struct); reading/dithering can
  stay stdlib the same way.
- **I2. Bitmap delivery.** Do NOT push 76 KB through the 240-byte chat
  frames (~350 frames). Reuse the proven bulk path: the client fetches bytes
  over HTTP from 18081 into a VBO, exactly like the ZC40 loader pulls
  packages (proven to 512 KB). Chat flow: `/image <prompt>` (server-side
  command like F4's) → reply `TEXT image ready: <name>` → client (A8+) adds
  a viewer that GETs the payload and draws it. `[verify]` the NewtonScript
  bitmap APIs against `refs/` before coding: candidate path is a raw
  bitmap frame for `DrawShape` (`MakeBitmap`/`SetPixel` family — names
  unverified; grep the Ref before believing any of them).
- **I3. Vector-into-a-note (the ideal). The `[verify]` is DONE — 2026-08-04.**
  Host converts the generated image to polylines (edge-trace, or ask the model
  for SVG and flatten paths), ships them over `/tools` or the bulk HTTP path,
  and the client writes a **sketch note** the Newton renders natively and the
  human can edit with the stylus. The probe round is complete and the write
  path is de-risked; only the *building* is left.
  - **There is no sketch stationery.** The `+New` picker offers only
    Note/Checklist/Outline/Recording. A sketch note is an ordinary
    `class 'paperroll` note; what you switch is the *recognition mode*, from
    the `A` button in the Notes bottom bar → **Sketches**.
  - **The soup shape:** `data` is an array with **one item per pen stroke**.
    Freehand items are `{ink: <'ink2 binary>, viewBounds, _proto}` with **no**
    `viewStationery`; shape-recognised items are `{viewStationery: 'poly,
    viewBounds, points: <polygonshape>}`; Ink Text hides `'inkWord` binaries in
    a `'para`'s `styles`.
  - **The write path is proven**, not assumed:
    `MakeStrokeBundle(pointArrays, 0)` → `CompressStrokes` → a
    `{ink, viewBounds}` frame — but as `'inkWord`, so **`InkConvert(ink, 'ink2)`
    is a required step**, and the geometry survives the round trip
    (`(10,10)…(40,40)` in, same endpoints out).
  - Cap points per note — the twelfth-finding event-loop lessons apply to soup
    writes too.
  - Evidence: `docs/newtonscript-eval.md` "Seventeenth finding",
    `runtime/evidence/sketchprobe-*`.
- Sizing: I1 one session (host-only, testable without a Newton); I2 one
  session (client round); **I3 is now one session** — the probe round is spent,
  only the write round remains.

## Track J — web interface for the modern side (designed 2026-08-03, not started)

Requested by the human 2026-08-03: see all Newton notes in a modern browser
(phone or desktop), browse device data, installed packages, battery — the
Newton's data made useful in the modern age.

- **J1. Sync layer first, UI second.** The web view must not depend on the
  Newton being awake. A host sync job walks `note_list`/`get_note` (and
  `pkg_list`/`store_info`/`battery`) over the proven `/tools` channel and
  writes a local store — plain JSON files or sqlite under a new
  `state/sync/` (decision open; JSON matches the repo's stdlib habit). Each
  sync is incremental and respects the wire lessons (paged ordinals, ~0.8 s
  per call — a 40-note sync is ~35 s, fine for a background job). The Dock
  backup path (`runtime/newton_backup.py`) stays the deep-backup tool; this
  is the light continuous one.
- **J2. Web server.** One stdlib `http.server` file (the repo pattern),
  serving: notes list + note view (rendered text; later sketch-note strokes
  as inline SVG — the same geometry knowledge from Track E/I3), package
  inventory, store/battery status, and a "sync now" button that fires the
  tools calls live when the Newton is connected. Bind LAN, not localhost,
  so a phone can reach it; NO auth beyond the isolated-subnet assumption at
  first — say so on the page — revisit if it ever leaves the bench network.
  New port (e.g. 8090); do not overload 18081 (the POLL hijack makes that
  server special — C6 note).
- **J3. Later**: write-back (edit a note in the browser → new note on the
  Newton via the sanctioned two-step create), and serving the ink PNGs the
  `/ink` path already renders.
- Sizing: J1 one session (host + live emulator round), J2 one session, J3
  later. J1's store is also what a future mobile/RSS/export anything would
  read — keep it dumb and documented.

## Track K — crash telemetry (requested 2026-08-03, designed, research in flight)

The human reports frequent crashes on the physical MP2000, usually right
after package installs (classic NS-heap exhaustion), and most go unreported.
Goal: the agent learns about crashes and memory pressure without the human
retyping error slips.

- **K1. Reboot detection, host-side (nearly free).** The tools client
  reconnects after every restart; the broker already logs
  `Newton tools connected`. Timestamp these in a durable host log
  (`state/device-events.jsonl`), classify reconnect-after-silence as a
  probable reboot, and expose the recent event list to the agent (an MCP
  tool or a `newton_tool` alias reading the host file). Correlate with
  install events (dual_send/loader log) so the agent can say "3 reboots
  tonight, each after an install".
- **K2. `mem` tools op.** Heap free / largest free block / frames-heap
  stats + store free (store part exists via `store_info`). API names
  `[verify]` — research agent checking refs for the real NewtonScript
  memory-introspection surface (Gestalt selectors, `Stats`-family,
  `SystemRAMSize`-family — do not trust these names until quoted from the
  Ref). Agent-facing use: warn BEFORE installs when heap is tight.
- **K3. Structured error reporting from our packages.** Our clients catch
  their own exceptions and show them on-screen; also POST them to the host
  (tools channel or the 18081 HTTP surface) into the same
  `device-events.jsonl`. No OS-level crash capture — NewtonScript cannot
  catch a system crash — but our own failures stop depending on the human's
  memory.
- **K4 [verify].** Does NewtonOS 2.1 record ANY durable last-error/restart
  reason readable from NewtonScript (reboot-reason Gestalt, last error
  global)? Research in flight; if yes it joins `mem`; expected answer is no.
- Also practical, not code: retire superseded packages from the physical
  device (A3 once A7 is trusted, old proof payloads) — installed packages
  consume RAM even idle; C5 (`pkg_remove`) makes this agent-assisted later.

## Track L — product-shape fixes from real use (2026-08-04, in flight)

Direct answers to the second hardware test (status log entry above).

- **L1. One package, real name: "Egg Freckles" client — DONE 2026-08-04**
  (`EggFrecklesEF1:jbfly`, v1.0-ef1; status-log entry at the top of this
  file). The fixed-op client now lives inside the chat app on the same NIE
  link and `examples/harness-tools/` is deleted, so one install delivers
  both and the second NIE client is gone. Window centred from the live root
  box, buttons relabelled Send / Ask Note / Save Note, Ask ordered by
  `EntryUniqueID` instead of any clock-derived stamp. The `vApplication`
  experiment was run and **failed** — floating views are excluded from
  scroll routing by definition — so Up/Dn stay and the eighteenth finding
  is closed. Two modal-alert sources (missing `ExceptionHandler`, delayed
  calls landing on a closed view) were found and fixed on the way.
  **Closed 2026-08-04 by Track L4**: the loader is `-Loader1:jbfly` with the
  plain **Loader** label, a much larger input field and a `protoKeyboardButton`
  beside it. See the status-log entry at the top of this file.
- **L2. Notes Action-menu integration — DESIGNED 2026-08-04, not built.**
  `docs/notes-integration-design.md` is the design, with a four-session build
  plan and every unproven step tagged `[verify]`; the mechanism was measured
  on the ROM (status log entry above, evidence
  `runtime/evidence/l2probe-routescripts.txt`). Short version: append a
  `{title, RouteScript}` frame to `GetRoot().paperroll.routeScripts` from the
  package's `InstallScript` (re-runs on every reset), the script receives the
  **live soup entry of the note whose envelope was tapped** — so no
  newest-note heuristic — POST it over the existing `/ink` transport, and
  write the answer back as a note filed into an "AI" folder via `AddFolder` +
  `labels`. Ship it **inside** L1's Egg Freckles package, not as a third
  package. This eventually supersedes the Ask button; the chat app remains as
  the conversation surface.
- **L3. Mars self-sufficiency — DONE 2026-08-04.** Built cDCL, patched
  `tntk`, and NEWT/0 on mars, all user-space under `~/newton-dev`, zero
  `sudo` (mars already had every prerequisite package: `gcc` 16.1.1, `cmake`,
  `ninja`, `flex`, `bison`). `docs/host-setup.md` is the from-scratch
  recipe; see the status log entry below for the proof. Emulator-on-mars
  stays deferred, unchanged.

## Sequencing

A → B → (C6, D1) → C1–C3 → D2–D3 → E1–E2 → F1 → F2 → G → C5/E3/F3 → H.
A and B are pure cheap-agent work. C/D/E/F Newton-side code is where the
NewtonScript footguns live — sessions doing those must read
`docs/newton-networking-lessons.md` §2 and `docs/phase3-chat-round.md`
"What cost the most time" first (this is already the START-HERE rule).

## Decisions still open for the human

1. **Delete vs keep superseded example sources** (Track A3): recommended
   delete — git history retains them; nothing on-device depends on host
   sources.
2. **`~/newton-archive/` location** for the 120 MB of old emulator flash
   snapshots (Track A4): recommended over deletion; confirm the path.
3. **Track D backend**: recommended to stay on codex + MCP now; say the word
   if you want Claude wired in as an alternate backend while D1 is being
   built, since it changes the config work slightly.
