# EF26 physical MP2000 — one-session runbook

**Keep EF13 and ZC40 installed, add EF26 under its fresh identity, and stop at
the first failed gate. Tic-tac-toe comes only after chat, Notes text, and ink
all pass.**

*Prepared 2026-08-11 from the checked-in EF26 candidate, the preserved EF13
package, and the ZC40 install path. No physical device was touched.*

## 1. Preserve fallback and make the rollback gate explicit

1. Treat the 2026-08-03 716-entry export as a **selective soup export**, not a
   full restorable hardware backup. Its contents and tree digest are recorded at
   `docs/newton-client-notes.md:162-173`. It preserves raw exported entries but
   does not prove a package/system restore path. Do not infer a checksum or a
   proven restore procedure from `docs/newton-backup-runbook.md`.
2. Leave EF13 installed and verify it still opens before installing EF26. EF26
   has a fresh identity, so EF13 remains the installed known-good application
   fallback; do not remove it during this session.
3. Leave **ZC40 Loader 2.4** installed and verify it opens. It preserves the
   established package-install fallback; do not replace or delete it.
4. **Pre-install operator gate:** explicitly confirm that preserved EF13 plus
   ZC40 is adequate rollback for this additive fresh-identity install. If the
   operator requires restoration of package/system/store state, or cannot
   confirm an independently adequate rollback, stop before staging or tapping
   Install. A soup export alone does not satisfy that gate.
5. Confirm at least twice the 114,704-byte package size is free for ZC40's
   download VBO and installation copy.

## 2. Stage and install through ZC40

On the bench host, verify and stage the exact candidate under the established
zero-typing alias:

```sh
sha256sum examples/harness-client/egg-freckles.pkg
cp -- examples/harness-client/egg-freckles.pkg runtime/staging/hardware/install.pkg
sha256sum runtime/staging/hardware/install.pkg
python3 runtime/dual_send.py
```

Both hashes must be
`bcc36db8db643a1e9e1825699a52ffad9bf705617a4af97bed59641f5736b14f`.
On the Newton, open **ZC40 Loader 2.4**, confirm `install.pkg`, tap **Install
once**, and wait. ZC40's known `Install not confirmed` message is not a pass or
fail by itself; Extras must show **Egg Freckles**, and opening it must show
**Egg Freckles 1.0-ef26**. Record the visible result before continuing.

## 3. Run the gates in order

1. **Chat:** select the established Newton server entry, send `/status` once,
   and require a reply plus a return to **Ready**. Stop and record the exact
   status/error if it fails; do not retry with changed parameters.
2. **Notes Send to AI:** create a short, uniquely worded text-only stock Note.
   From that page's envelope menu choose **Send to AI**. Require a reply note in
   the AI folder that clearly corresponds to that page.
3. **Ink:** create a new drawing-only stock Note with a few distinct strokes,
   then use EF26 **Ask** on that newest note. Require visible progress, a reply,
   and no memory/communications alert.
4. **Tic-tac-toe:** only after all three gates pass, run one game action. It is
   optional follow-up, not part of the return-to-physical acceptance gate.

## 4. Close the session

Record the exact package title/identity, each visible status, whether a reply
arrived, and any host-side connection evidence. A gate failure returns to the
preserved application fallback by closing EF26 and reopening EF13; this is not a full hardware-state restore. Retain EF26,
EF13, ZC40, and all exports/backups for diagnosis.
Do not call EF26 hardware-proven unless all three ordered gates pass on the
physical MP2000.
