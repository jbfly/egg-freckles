# Chat-client UI round + radio/battery lifecycle (planned)

Date: 2026-08-06. Source: Omnigent session `47cbab8241a74a2383ed75340ded3115`
(decided in conversation; **not yet built**). Captured here because the
pagination handoff that followed carried only the ink fix and dropped these.

Line references are from the EF9-era source (`task/ef9`); re-verify against the
current `examples/harness-client/Main.newt` when implementing.

## A. Chat-client UI changes

The standalone chat client predates the Notes-menu integration (Egg Freckles
"Convert to Text" / "Ask AI"). Now that Ask lives in the Notes envelope menu,
the chat window should be simplified:

1. **Full-screen launch.** Open the client full-screen instead of a floating
   window.
   - Tension: an earlier design note argued a floating panel *beats* full-screen
     "because Newton multitasking is painful" (`docs/ROADMAP.md:466`). Revisit
     that tradeoff deliberately; the user now wants full-screen.
2. **Drop the Ask + Save Note buttons.** They are redundant once note actions
   live in the stock Notes menu. (Chat A9, commit `a45b661`, already removed
   `ReadNote`/`AskNote` and the `Ink` button; this finishes the job.)
3. **Native scroll arrows.**
   - Tension: prior ROM investigation found the native scroller protos "buy
     nothing" and the ROM's own scroll arrows "can never reach" the transcript,
     which is why A8 shipped a **custom** scroller
     (`docs/ROADMAP.md:570-590`, `docs/newton-dev-notes.md:1122`). Implement with
     eyes open; the custom scroller may have to stay.
4. **(maybe) Ask replies into the same source note.** File the AI answer back
   into the note it came from, instead of a new note in the AI folder. This is
   also the item deferred in `docs/ef10-ink-pagination.md` ("appending Ask
   answers to the source note") — placing paragraph frames relative to the
   source note's existing `viewBounds` is the fiddly part.

## B. Radio / battery lifecycle rule (EF10+) — higher priority

The battery drain the user flagged is real and design-level, not cosmetic.

**Problem.** The tools long-poll auto-starts from `InstallScript` via
`AddDelayedCall(... ToolStart() ...)` (~`Main.newt:1707-1719`, EF9 era), so the
WiFi radio is held open **continuously** after install — its stated purpose is
"answering while nobody is looking at the Newton." That is always-on radio on a
battery device.

**Rule (adopt for EF10+):**
- The Newton **always initiates** a connection; it never acts as a server.
- **Radio off until you send.** No passive/always-on channel.
- **Auto-disconnect after idle**, and **reconnect only when there is data to
  send**.

**Fix sketch.** Delete the `AddDelayedCall` that starts the tools poll in
`InstallScript`; start the poll (if kept at all) from the same send path that
opens the ink/chat endpoint (`Connect`/`InkOpen`). Add an idle timer that tears
the link down after inactivity.

**Tradeoff (logged so it isn't a surprise).** Off-until-send means the host
cannot push to the Newton out of the blue. The "drawing → generated image comes
back into your note" round-trip must be designed around an active send (request
the image, keep the link up until it returns), not a surprise server push.
Battery wins over passive push.

## Status / sequencing

- All of the above is **decided, not built.**
- Sequence: land the EF13 ink out-of-memory fix (in progress) first, then do
  this as its own round. Do not edit `Main.newt` for this while an ink worker is
  mid-edit on the branch.
