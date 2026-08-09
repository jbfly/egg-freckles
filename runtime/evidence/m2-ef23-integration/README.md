# M2 EF23 integration evidence

Date: 2026-08-09. Prepared only on `task/m2-ef22-integration`; no hardware,
Mars, shared emulator, service, or remote branch was changed.

## Integration and conflicts

- Parent/base: `2fbbd4baefb9504de4826dd439fc2b46f20b5ca6`.
- Source range replayed as seven commits: `041b22c..ab55de3`.
- `Main.newt`: trunk remained the merge baseline; the autofind favorite/prefs,
  active-target, native-marker ordering, and minimized HS-A/HS-B/HS-C changes
  applied on top. The sole textual conflict was the title block; M2 replaced it
  with fresh EF23 identity while retaining the stable human-facing label.
- `egg-freckles.nprj`: fresh `EggFrecklesEF23:jbfly`, version 37.
- `egg-freckles.pkg`: every binary cherry-pick conflict chose the base side;
  the committed binary was rebuilt from integrated source only.
- `test_newton_client_source.py`: retained trunk package-tool/native-scroll
  assertions, replayed autofind assertions, and added the smallest progress
  branch check.
- Conflicting recovery docs kept the newer trunk timeline, then received this
  evidence-backed M2 status update.

`identity-uniqueness.txt` records zero EF23 hits in all refs/content and all
history before the M2 edits.

## Tests and package

- `client-tests.txt`: 44 passed.
- `full-tests.txt`: 139 passed.
- `build-1.log`, `build-2.log`, `reproducible-package.txt`: two normalized
  builds are byte-identical, 114,704 bytes, SHA-256
  `093d7784c8d097646cfdd1e7cb7b38cb68ef23e8330cc0fd6af9fc5b3cbe6d53`.
- `file` identifies Newton NOS 1.x, NoCompression, package version 37; package
  strings contain `EggFrecklesEF23:jbfly`.

## Isolated emulator and local server

Instance `m2ef23-0809a` used its own container, state volume, and kernel-picked
control ports. It was seeded from the archived working NIE flash, then removed
with its state volume (`instance-up.txt`, `boot-health.txt`,
`instance-down.txt`). `shared-emulator-untouched.txt` records the shared
`newton-harness_emulator_1` container identity without acting on it.

- Install/launch: `install-version.txt` returns 37; `launched.png` and
  `launched-ocr.txt` show **Egg Freckles 1.0-ef23**.
- Picker: `lan-selected-state.txt` and the searchable OCR sidecar
  `advanced-lan-selected-ocr.txt` normalize the active index 1, **LAN (iPad)**
  private test address as `<lan-ip>`. The original
  `advanced-lan-selected.png` remains byte-identical historical evidence and
  may visibly retain that address. For the throwaway loop only,
  that same row was changed inside the disposable flash to
  `10.42.0.1:<ephemeral-port>` (`lan-local-server-state.txt`).
- Progress: `throwaway-progress-server.log` records native marker, EF23 HELLO,
  prompt, two `STAT PROGRESS` frames, final `TEXT`, and `PROMPT`, all ACKed.
  `progress-writing-state.txt` and `progress-building-state.txt` show each
  label while `responseText` is empty; matching screenshots contain the user
  turn but no second final answer. `progress-final-state.txt` and
  `progress-final.png` show the answer only after `PROMPT`.
- Teardown: `throwaway-server-teardown.txt` shows port <ephemeral-port> clear.

This proves Linux Einstein behavior only. It cannot answer the iOS NIE
zero-byte question. M4 remains exactly one human-gated iPad `/status` Send with
the EF23 package, preserving and photographing the final HS-A/HS-B/HS-C status.
