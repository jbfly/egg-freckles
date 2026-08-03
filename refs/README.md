# refs/ — the Newton documentation this repo argues with

Run this once, before anything else:

```sh
./refs/fetch-refs.sh
```

Nothing in this directory except the script, `SHA256SUMS`, and this README is
tracked. The manuals and Apple's developer Q&A notes are Apple copyright and
are not redistributed here; the script pulls them from
[UNNA](http://www.unna.org/) and checks every byte against `SHA256SUMS`.

| Path | What it is | Where it comes from |
|---|---|---|
| `NewtonProgrammerGuide20.pdf` / `.txt` | *Newton Programmer's Guide 2.0* — the prose manual | UNNA `/unna/development/documentation/` |
| `NewtonProgrammerRef20.pdf` / `.txt` | *Newton Programmer's Reference 2.0* — the slot-by-slot API reference | UNNA, same directory |
| `nie11/nie11api.pdf` / `.txt` | Newton Internet Enabler 1.1 API reference | extracted from UNNA `/unna/apple/development/NIE1.x/NIEDVLPR.EXE` |
| `nie11/incldfls/*.txt` | Apple's NIE constant/error/name-map include files | same archive |
| `qa/endpoint.htm`, `qa/inptspec.htm` | Apple developer Q&A on endpoint behaviour and input specs | UNNA `/unna/apple/documentation/developer/QAs-2.x/html/` |

## Why the `.txt` files are generated, not downloaded

Docs across this repo carry their evidence as line citations into the
extractions — `docs/newton-networking-lessons.md`, for instance, backs its
input-spec rule with `refs/NewtonProgrammerGuide20.txt:50167-50178`. The script
regenerates them
with `pdftotext` at default settings, which is how the originals were made, and
`SHA256SUMS` is what proves your poppler numbers the lines identically.
Verified byte-identical with poppler 26.07.0. A checksum failure limited to the
`.txt` entries means your poppler formats differently: the PDFs are still
correct, but line citations will be off.

## Verification

Every URL above was re-checked on 2026-08-03: all returned HTTP 200 and every
downloaded file hashed identically to the copy this repo was developed against.
UNNA's HTTPS chain does not validate against a stock Linux trust store, so the
script uses plain HTTP and relies on `SHA256SUMS` for integrity — the same
trade-off `scripts/fetch-recovery-packages.sh` already makes.
