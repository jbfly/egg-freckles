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
`The Newton sees this note.`. Einstein's synthetic typing reordered part of the
second line in the actual saved rich string. The exporter reported the stored
text exactly rather than repairing or inventing it:

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
replaces `runtime/evidence/notes-latest.json`. There is no model call.

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

## Next

Pass the validated `notes-latest.json` object as one user-provided context item
to the existing host model turn, preserving the same 8 KiB cap and making no
Newton-side change.
