# newton-harness

Read **`docs/START-HERE.md`** first. It says which docs are authoritative and
which are stale plans.

## Keeping knowledge

1. A finding is not real until it is in a doc **with its evidence** — a
   `file:line`, a commit sha, an evidence file, or the quoted error text.
2. When you resolve something a doc calls open/TODO/unverified, update that doc
   **in the same commit**. Then `grep` the tree for the stale claim: it is
   usually in more than one place.
3. Anything that exists only on the physical Newton, or only in an untracked
   working tree, is one hard reset from gone. Commit it.
