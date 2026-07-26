# Native Notes bridge: one read-only note

## Bottom line

NewtonOS 2.1 stores stock Notes entries in the union soup named by
`ROM_paperRollSoupName`. A real plain note created in stock Notes was entry ID
`3`, class `'paperroll`, with optional `title` absent/empty and one `data` item:
`{viewStationery: 'para, text: <rich string>, ...}`. Decoding that rich string
and posting one bounded JSON document over the proven NIE/HTTP path worked.

The read-only exporter is `examples/note-export`. It reads only the newest entry
through the documented `timeStamp` index, which is the explicitly created test
note for this spike. It does not call any soup or entry change method.

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

- Polygon (`'poly`), ink, and picture (`'pict`) objects are ignored; no safe
  plain-text accessor was established for them.
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

## Create-only experiment (N2/N3): entry 4 is malformed

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
**Verdict: entry 4 is genuinely malformed, not healthy or merely uncommitted.**
It was left untouched.

No decoder change can recover entry 4 because the persisted entry contains no
text object. The exporter should still handle both valid representations seen
elsewhere: use a plain string directly when `IsString(item.text)` is true, and
use `DecodeRichString(...).text` only for a rich string. It must also treat a
plain-note entry with `data=nil` as malformed instead of reporting a legitimate
empty note.

`MakeTextNote(answer, true)` is **not usable as the main create path** despite
its scratch success; the same call failed on the target store. The single next
write-back action is to test the documented two-step replacement on the scratch
emulator only: create the frame with `MakeTextNote(answer, nil)`, then add it
with `paperroll:NewNote(note, nil, nil)`, and require a persisted round trip
before any further main-emulator write.

The source entry remained byte-for-byte unchanged. Before and after exports are
`runtime/evidence/n2-source-before.json` and
`runtime/evidence/n2-source-after.json`; both have SHA-256
`5df783f1700c2bd366d65408ad73299d51f9fd778f8989b18321d1b78bb97135`, ID `3`,
and `EntryModTime` `64465065` (`runtime/evidence/n2-source-integrity.txt`).

## Honest limits

- The shipped bridge remains read-only: the attempted create path was reverted
  after the malformed main entry, and native answer write-back is not proven.
- It reads only the newest plain stock note; ink, pictures, outlines, and
  checklists remain unsupported.
- Validation still permits 8 KiB of note text, but the reused chat protocol
  deliberately accepts only one 240-byte frame. A longer valid note therefore
  gets a visible `No answer: LENGTH` response; multipart prompts are a later
  protocol rung, not part of this change.
- The returned display line is ASCII-cleaned and capped at 200 characters for
  the Newton status view. There is no polling, queue, or bridge-owned history;
  every export resets the shared chat before its one model turn.
