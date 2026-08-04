# Native Notes bridge: one read-only note

## Bottom line

NewtonOS 2.1 stores stock Notes entries in the union soup named by
`ROM_paperRollSoupName`. A real plain note created in stock Notes was entry ID
`3`, class `'paperroll`, with optional `title` absent/empty and one `data` item:
`{viewStationery: 'para, text: <rich string>, ...}`. Decoding that rich string
and posting one bounded JSON document over the proven NIE/HTTP path worked.

**Current state (Track A9, 2026-08-04): the bridge is the chat client, and
the read path is one button.** `examples/note-export` is deleted;
`examples/harness-client` (`HarnessClientA9:jbfly`) carries the read and create
paths as **Ask** and `Save Note`. `POST /note` still exists in
`pkg_publisher.py` and still works; nothing on the Newton calls it any more, so
treat it as the historical host API this page documents, not as a live path.

**The Ask flow.** One tap means *send the newest note, whatever kind it is* —
never a second "Ask Sketch" button to choose between, and never a silent skip.
`FindNewest` walks the `timeStamp` cursor back over at most 16 entries and takes
the highest `EntryModTime`, because `timeStamp` is creation time and drawing on
an existing page only moves the modification stamp (`:41-42` below; there is no
`_modTime` index to order by — that query raises `evt.ex.fr.store`). It then
classifies the entry's `data` array in the order `'para` → `'poly` → `'pict` →
`ClassOf(item.ink) = 'ink2`, which is load-bearing: testing `points` first
resolves through every ink item's `_proto` and reports an empty shape. A
paragraph's `text` has the Ink Text placeholder **63233 (0xF701)** stripped, and
its `'inkWord` styles are expanded into strokes like anything else. Then:

| Newest note holds | Route |
|---|---|
| text only | the **ordinary chat transport** — one `MSG` frame under 227 characters, `MSGP` parts above it, which is what retires the `No answer: LENGTH` failure under "Honest limits" below |
| any strokes | **one** `POST /ink` — `NSI1` `S` lines, plus one optional `H <text>` line carrying the page's text so a mixed note is one request and one reply |

The reading joins the transcript as `Ink: …`. Full design and proof:
`docs/ink-client-design.md`, "Sketch-note pivot" and "A9 result"; the soup
shapes are `docs/newtonscript-eval.md` seventeenth finding, the `EntryModTime`
limits its nineteenth.

Everything below is the N1–N13 investigation that produced those paths, and it
is still the authority on the soup schema and on what does *not* work. Two
corrections from F2 are folded in where they apply.

The original exporter was `examples/note-export`. Its export path reads only the
newest entry through the documented `timeStamp` index. N13's single Ask button
sends that note to the model, creates one native note from the returned answer,
and immediately reads the new entry back.

Destructive operations require an explicit human confirmation gate on real
hardware. Disposable emulators are exempt from that confirmation requirement.

## Actual schema finding

The Newton 2.1 manuals and platform file identify:

- application: `GetRoot().paperroll`
- union soup name: `ROM_paperRollSoupName`
- entry `viewStationery`: `'paperroll`
- plain-note entry `class`: `'paperroll`
- creation time: entry slot `timeStamp`, minutes since 1904-01-01
- modification time: `EntryModTime(entry)`, also minutes since 1904-01-01
- stable system identifier: `EntryUniqueID(entry)`
- optional file/folder label: entry slot `labels`; `nil` means Unfiled
- optional name: entry slot `title`, string or rich string
- plain-note content: entry slot `data`, an array of object frames
- text object: `viewStationery: 'para`; its `text` was a rich string on this
  device and required `DecodeRichString(...).text`

The real test entry had ID `3`, class `'paperroll`, modification time
`64465065`, no exposed title, and one paragraph object. The temporary bounded
schema probe is `runtime/evidence/notes-schema-probe.txt`; the received export
is `runtime/evidence/notes-latest.json`.

## Test setup

The note was created through the stock Notes UI on the networked main emulator.
The first line was `Harness export test`; a second line was entered as
`The Newton sees this note.`. The correctness check reopened stock Notes on the
main emulator and compared the rendered note in
`runtime/evidence/notes-test-setup.png` with
`runtime/evidence/notes-latest.json`. **Verdict: this is a synthetic-typing
artifact, not an exporter bug.** The screen itself shows the same scrambled
words, and the entry is one 49-byte paragraph frame, so neither
`DecodeRichString` nor paragraph ordering changed the text:

```text
harness export test the nthis note.ewton sees [trailing space]
```

Evidence of the stock UI setup is `runtime/evidence/notes-test-setup.png` and
its OCR sidecar `runtime/evidence/notes-test-setup.txt`.

## Export shape and safety

The Newton package posts one ASCII JSON object to `POST /note`:

```json
{
  "id": 3,
  "title": "",
  "modified": 64465065,
  "text": "harness export test the nthis note.ewton sees ",
  "truncated": false
}
```

`pkg_publisher.py` accepts only those five keys, validates UTF-8, types, a
512-byte title cap, an 8 KiB text cap, and a 9 KiB request cap, then atomically
replaces `runtime/evidence/notes-latest.json`. It synchronously resets the
existing port-6801 chat session, sends the note text as one framed `MSG`, joins
the returned `TEXT` frames, and returns one bounded ASCII `NOTE ...` response.
The Newton package displays that response without changing the source note.

The source note was exported twice. `runtime/evidence/notes-before.json` and
`runtime/evidence/notes-after.json` are byte-identical and both hash to
`5df783f1700c2bd366d65408ad73299d51f9fd778f8989b18321d1b78bb97135`.
They contain the same ID, modification time, and text, so the source entry was
unchanged by export.

## Unsupported note content

- Polygon (`'poly`), ink, and picture (`'pict`) objects are ignored by the
  exporter, and there is no plain-*text* accessor for them. **Their geometry is
  no longer unknown, though** — as of 2026-08-04 the sketch-note probe extracts
  exact points from all three ink representations (`'ink2` freehand, `'poly`
  shapes, `'inkWord` embedded in a paragraph's `styles`). See
  `docs/newtonscript-eval.md`, "Seventeenth finding", and the design that
  consumes it in `docs/ink-client-design.md`, "Sketch-note pivot".
  A related trap the exporter does not yet handle: an Ink Text paragraph leaves
  placeholder character **63233** in its `text`.
- Outlines (`class 'list`) and checklists (`class 'checkList`) use `topics`
  rather than `data` and are not exported.
- Folder `labels` was documented and the test note was Unfiled, but it is not
  included in the five-field wire shape.
- The optional `title` was absent for the test note, so JSON reports `""`
  rather than deriving a title from body text.

## Real model proof

Package identity `NoteExportN1:jbfly` posted the real note to the real server
container (`NEWTON_FAKE_BACKEND=0`). The Newton displayed:

```text
Export test received. The Newton sees this note.
```

Evidence:

- `runtime/evidence/n1-model-answer.png` — the answer visible on the main Newton
- `runtime/evidence/n1-model-answer.txt` — OCR sidecar
- `runtime/evidence/n1-wire-host.log` — `/new`, the exact note `MSG`, model
  `STAT/TEXT/PROMPT`, and the successful `POST /note`
- `runtime/evidence/n1-real-server.log` — matching real server connection

`grep -R FAKE` over those proof files returned zero hits. The full clean test
run is 24 passed, including model success/failure response coverage.

## Create-only experiment (N2/N3): historical failed write

The documented one-call creation path was:

```newtonscript
GetRoot().paperroll:MakeTextNote(answer, true);
```

A throwaway `NoteExportN2:jbfly` build called that method only after receiving a
successful `NOTE <answer>` response. On the scratch emulator it rendered
`Scratch answer round trip.` in stock Notes and the package's read path showed
the same text (`runtime/evidence/n2-scratch-roundtrip.png`).

The same call did not create a healthy entry on the main emulator. Stock Notes
rendered the model answer
`Export test received. I see: "the nthis note.ewton sees"`
(`runtime/evidence/n2-native-note.png`; exact model frames in
`runtime/evidence/n2-create-wire.log`), while the persisted newest soup entry,
ID `4`, read back with empty `title` and `text`
(`runtime/evidence/n2-answer-readback.json`).

N3 tested whether this was merely an open, uncommitted editor view. Before the
probe, Notes had already been closed or switched away from and Newton Chat was
showing `Ready` (`runtime/evidence/n3-main-before.png` and its OCR sidecar).
A read-only soup probe then reported:

```text
id=4 mod=64465075 entry.class=paperroll
data=nil
```

The exact persisted `data` shape is therefore `nil`, not an array: it has no
array length, contains no elements, has no element classes or slot names, and
has no `text` slot or raw text type to decode. Evidence is
`runtime/evidence/n3d-shape-final.png` and
`runtime/evidence/n3d-shape-final.txt`. Its modification time is unchanged from
the N2 readback. Closing or switching apps did not flush answer text into it.
**Verdict: entry 4 was failed-write garbage, not a healthy or merely
uncommitted note.** It was deleted during the successful N13 MAIN gate below.

No decoder change can recover entry 4 because the persisted entry contains no
text object. The exporter should still handle both valid representations seen
elsewhere: use a plain string directly when `IsString(item.text)` is true, and
use `DecodeRichString(...).text` only for a rich string. It must also treat a
plain-note entry with `data=nil` as malformed instead of reporting a legitimate
empty note.

`MakeTextNote(answer, true)` is **not usable as the main create path** despite
its scratch success; the same call failed on the target store.

## Scratch create follow-up (N4-N12): API passes on-device gate

The documented two-step is:

```newtonscript
local notes := GetRoot().paperroll;
local note := notes:MakeTextNote(text, nil);
notes:NewNote(note, nil, nil);
```

N4-N9 sent that code through the emulator-only `/newtonscript` queued
evaluator. Calls that executed produced healthy array-backed notes, including
IDs `5`, `6`, and `10`, but later byte-equivalent requests returned `queued`
without creating entries. Direct `AddFlushedXmit` requests sent through the
same evaluator behaved identically. That experiment is preserved in
`runtime/evidence/n7-create-reliability-negative.txt`, but its earlier API
verdict was wrong: the endpoint has no execution/result signal, so it measured
the queued evaluator as well as the Notes API.

N12 removed that evaluator from creation. Fresh package identity
`NoteExportN12:jbfly` runs the two-step inside its Create button, immediately
re-reads the newest creation minute, and resolves same-minute ties by highest
entry ID. Three consecutive `/window/tap` UI actions produced and displayed:

- `id=18 mod=64465167 data=array text="N12C3"`
- `id=19 mod=64465167 data=array text="N12C4"`
- `id=20 mod=64465167 data=array text="N12C5"`

The full-window screenshots are `runtime/evidence/n12-gate-1.png`,
`runtime/evidence/n12-gate-2.png`, and
`runtime/evidence/n12-gate-3.png`; the run summary is
`runtime/evidence/n12-on-device-create.txt`, and the undefined-symbol-free
build is `runtime/evidence/n12-build.log`. No write was sent to the main
emulator.

**Corrected verdict: the documented Notes create API is reliable for the
three-consecutive-create gate. The flaky link was the emulator's queued
NewtonScript evaluator, not `MakeTextNote` plus `NewNote`. The sanctioned write
path is the package's on-device Create button.** Creation remains deliberately
disconnected from the model/chat path.

The source entry remained byte-for-byte unchanged. Before and after exports are
`runtime/evidence/n2-source-before.json` and
`runtime/evidence/n2-source-after.json`; both have SHA-256
`5df783f1700c2bd366d65408ad73299d51f9fd778f8989b18321d1b78bb97135`, ID `3`,
and `EntryModTime` `64465065` (`runtime/evidence/n2-source-integrity.txt`).

## N13 create-only loop: MAIN gate passed

Fresh package identity `NoteExportN13:jbfly` makes the smallest join of the
proven paths: its single Ask button uses the existing export/model request, and
the existing `NOTE <answer>` callback passes the answer to
`MakeTextNote(answer, nil)` plus `NewNote(note, nil, nil)`. The create method
then reads back the newest same-minute/highest-ID entry and displays its ID,
`data` shape, and decoded text. No second network path was added.

On MAIN, one on-device Ask tap created entry ID `5`. The package immediately
read it back as `data=array` with text matching the model answer, and stock
Notes visibly rendered:

```text
Export test received. The Newton sees this note.
```

The exact prompt/answer pair is in `runtime/evidence/n13-main-wire.log`; it has
zero `FAKE` hits. The package readback is
`runtime/evidence/n13-main-answer-readback.png`, the native Notes proof is
`runtime/evidence/n13-main-stock-answer.png`, and the complete result is
`runtime/evidence/n13-main-gate.txt`.

Failed-write garbage entry ID `4` was deleted. Fresh diagnostic identity
`NoteDeleteN15:jbfly` then re-read the complete soup and visibly reported
`entry4=absent` in `runtime/evidence/n15-main-entry4-absent.png`; its source and
undefined-symbol-free build are `runtime/evidence/n15-delete-main.newt` and
`runtime/evidence/n15-delete-build.log`.

## Correction (F2): `ResetToEnd` lands *on* the last entry

`ReadOne` and `Create` both walked the `timeStamp` index with

```newtonscript
cursor:ResetToEnd();
local entry := cursor:Prev();
```

which reads the **second** newest entry, not the newest. Measured directly on
the emulator during Track F2, on a soup holding entries `0 1 2 3`:

```text
local a := c:ResetToEnd(); local b := c:Entry();
=> "reset=3 entry=3"                 while c:Prev() gave 2
```

`ResetToEnd` positions on the last entry *and returns it*. Consequences seen on
screen: the first F2 build read a `data=nil` seed note and reported
`Newest note has no text` (`runtime/evidence/f2round-03-asknote.png`), and its
create readback said `Saved note id=3` for an entry that was really `id=4`
(`runtime/evidence/f2round-08-savenote.png`). The fix is one line —
`local entry := cursor:ResetToEnd();` — and after it the on-screen id matched an
independent `ns_eval` read of the soup twice
(`f2round-11-savenote.png` id=6, `f2round-18-a7-savenote.png` id=8).

This is a real defect in the shipped `NoteExportN13`, so the N13 gate below
proved the *create* call, not the readback's choice of entry. The two-step
`MakeTextNote(answer, nil)` + `NewNote(note, nil, nil)` itself is unaffected and
is still the sanctioned write path.

## Honest limits

- The model-answer write-back is proven on MAIN for one plain-text model answer.
- **Ink is supported as of Track A9** — sketches (`'ink2`), recognised shapes
  (`'poly`) and ink text (`'inkWord`) all extract and go out to `/ink`. Pictures
  (`'pict`), outlines and checklists remain unsupported, and a note older than
  the 16-entry `EntryModTime` window is still not reachable.
- The 240-byte `No answer: LENGTH` limit is **gone as of Track F2**. `Ask`
  calls the client's own `Send()` for a text-only note, so a note over 227 characters splits into
  `MSGP` parts and the host reassembles up to 8192 bytes
  (`docs/phase3-protocol.md`, "Extension: `MSGP`"). Proven with a 266-character
  note: `MSGP part 1/2 220B` + `part 2/2 46B` → `assembled 2 parts into 266B
  prompt` (`runtime/evidence/f2round-round.txt`). The client caps the note it
  sends at 2048 characters — not a protocol limit but a CPU one, because the
  ASCII/control-character clean-up rebuilds the string one character at a time.
- `POST /note`'s own validation (five keys, 512-byte title, 8 KiB text, 9 KiB
  request) is unchanged, but no Newton package calls that endpoint now.
- The returned display line is ASCII-cleaned and capped at 200 characters for
  the Newton status view. There is no polling, queue, or bridge-owned history;
  every export resets the shared chat before its one model turn.

## Which note is "the newest" — the ordering rule (Track L1, 2026-08-04)

The rule the `Ask Note` button uses, and the reason it is not the obvious one.
Full evidence in `docs/newtonscript-eval.md`, "Twentieth finding"; raw transcript
[`efround-ordering.txt`](../runtime/evidence/efround-ordering.txt).

**The rule.** The newest note is the one the store **allocated last**:

```newtonscript
cursor := GetUnionSoupAlways(ROM_paperRollSoupName):Query({indexPath: '_uniqueID});
entry  := cursor:ResetToEnd();          // highest EntryUniqueID
// then scan back kScanLimit (16) entries, keeping the highest EntryUniqueID;
// EntryModTime breaks a tie ONLY (a union soup interleaves independent
// per-store ID spaces). Falls back to the 'timeStamp cursor if the ID query
// ever throws.
```

**Why not a date.** All three date-shaped candidates fail on this device:

| Candidate | Why it fails |
|---|---|
| `timeStamp` | creation time, never moves — a drawing added to an existing page never becomes newest (A7's bug, seventeenth finding) |
| `EntryModTime` | one-minute granularity, and stale until the user leaves the page (nineteenth finding) |
| either, on this MessagePad | the clock had been set to **2008** and corrected, so a note written while it was wrong sorts to the *front* of the `timeStamp` index and loses every `EntryModTime` comparison. Both halves of A9's rule are poisoned at once |
| `Query({indexPath: '_modTime})` | raises `evt.ex.fr.store` on this ROM — the index does not exist |

`EntryUniqueID` is the only recency signal on the device that never consults the
clock: IDs come off a per-soup counter (`soup:GetNextUid()` is documented as
"the unique identifier to be assigned to the next entry added to the soup",
`refs/NewtonProgrammerRef20.txt:33348`), and `_uniqueID` is queryable as an
index even though the manuals never document it as one.

**Measured, both rules over the same 25-note soup** — a "cat" note created last
but stamped 2008-06-01, behind eighteen ordinary D&D notes:

```text
A9  (timeStamp cursor, max EntryModTime)  -> id=23  "EF dnd session 18"     wrong
EF1 (_uniqueID cursor, max EntryUniqueID) -> id=24  "EF cat drawing page"   right
```

**What it costs.** A9 could answer with an *older* page you had just drawn on;
this cannot — it will answer with the newest page you *created*. That trade was
made deliberately: only one of the two survives a wrong clock, and the hardware
has a wrong clock. Reading the **open** note (Track F3) is the fix that needs
neither, and it is still the right long-term answer.

`Save Note` reads its confirmation back through the same `FindNewest()`, so the
id in "Saved note id=27" is the entry that was actually written — no
same-minute tie-break needed any more.
