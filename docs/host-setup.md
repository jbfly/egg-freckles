# Host setup — building the Newton package toolchain from scratch

This is the from-zero recipe for the one piece of this project that is not
`git clone` and `pip install`: the compiler that turns a `.newt`/`.nprj`
source project into a `.pkg` file NewtonOS can install. If you have cloned
this repo onto a fresh Linux box and want `make newton-packages` or
`make -C examples/hello` to work, this page is the whole story.

It **only** covers the package compiler. The always-on chat server
(`server.py`) needs nothing beyond Python's standard library, and the
Einstein emulator + rootless-Podman containers are a separate, optional piece
covered in `docs/dev-harness.md`. You do not need a ROM dump or Einstein to
build and stage packages — only to run them without real hardware.

## What you are installing

Three small, actively maintained open-source projects, all by the same
author (Eckhart Köppen / `ekoeppen`), each a thin CMake project:

| Project | Repo | What it gives you |
| --- | --- | --- |
| **cDCL** | <https://github.com/ekoeppen/cDCL> | `libDCL.so` — the Newton Desktop Connection Library reimplementation. `tntk` links against it. |
| **tntk** | <https://github.com/ekoeppen/tntk> | The compiler itself: NewtonScript → `.pkg`. This repo carries two small local patches for it (below). |
| **NEWT/0** | <https://github.com/ekoeppen/NEWT0> | A standalone NewtonScript interpreter (`newt`). **Not required** to build packages — `tntk`'s own CMake build fetches its own private copy of NEWT/0's parser automatically via `FetchContent`. Build it only if you want the `newt` command-line tool for its own sake. |

None of this is redistributed in the repo — you clone the upstream sources
yourself, same as any other dependency.

## 1. Prerequisites

Everything below is a normal development package, no exotic dependencies.
On Arch Linux (verified 2026-08-04 on two independent Arch hosts):

```sh
sudo pacman -S --needed gcc cmake make ninja git curl unzip flex bison
```

`flex`/`bison` are needed to regenerate NEWT/0's parser (`newt.l`/`newt.y`),
which `tntk`'s build pulls in automatically. On another distribution, install
the equivalent packages (`build-essential`/`gcc`/`g++`, `cmake`, `ninja-build`
or plain `make`, `git`, `curl`, `unzip`, `flex`, `bison`). **Check what is
already installed before adding anything** — a stock dev box usually has
most of this already; both hosts this was verified on needed zero new
packages.

Pick an install root. This repo's Makefiles default to `~/newton-dev`
(override with the `NEWTON_DEV` Make variable if you use something else):

```sh
mkdir -p ~/newton-dev
```

Everything from here on installs *inside* that directory — no `sudo`, no
system-wide `/usr/local` writes, nothing that touches the rest of the host.

## 2. Build and install cDCL

```sh
cd ~/newton-dev
git clone https://github.com/ekoeppen/cDCL.git
cd cDCL
cmake -S . -B build \
  -DCMAKE_INSTALL_PREFIX="$HOME/newton-dev/prefix" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
cmake --install build
```

This installs `libDCL.so` to `~/newton-dev/prefix/lib` (and a pile of
`DCL`/`K` headers to `prefix/include` that `tntk` needs at compile time),
along with a handful of standalone utilities (`DumpPkgDir`, `DumpPkgPart`,
`ELFtoNTK`, `ELFtoPKG`, `NSOFtoXML`, `Rex`, `WatsonEnabler`, `nespackager`,
`pbbookmaker`) that this project does not use but cost nothing extra to
build.

## 3. Build and install tntk (with the two local patches)

Clone it, then apply the two patches this repo vendors under `tools/`
*before* configuring:

```sh
cd ~/newton-dev
git clone https://github.com/ekoeppen/tntk.git
cd tntk
git apply /path/to/newton-harness/tools/tntk-project-version.patch
git apply /path/to/newton-harness/tools/tntk-gcc16-cstring.patch
```

**Why both patches are needed, not just one:**

- `tntk-project-version.patch` (`package.cpp`, `package.h`) makes `tntk` read
  an integer `version` slot from the `.nprj` project file instead of always
  hardcoding package header version `1`. Without it, every rebuild silently
  regresses to version 1 no matter what the project file says — see
  `docs/phase3-chat-round.md`, "Risk: the `tntk` patch is uncommitted and
  outside this repo". This has not been proposed upstream.
- `tntk-gcc16-cstring.patch` (`tntk.cpp`) adds one `#include <cstring>`.
  Recent GCC (16.x, verified on this project) no longer pulls in `memset`'s
  declaration transitively through the headers `tntk.cpp` already includes,
  so `tntk.cpp:195`'s `memset(command, 0, FILENAME_MAX)` fails to compile
  with `'memset' was not declared in this scope` — reproduced verbatim on a
  second Arch host during this write-up. This is an upstream GCC-version
  portability gap, unrelated to the version patch; older GCC does not need
  it, but anything current-generation does.

Now configure and build. The extra `CMAKE_CXX_FLAGS` are macros the DCL/`K`
headers from step 2 expect to see defined (byte order and 64-bit-literal
support flags); `CMAKE_PREFIX_PATH` is what lets `find_library(DCL)` see the
`libDCL.so` you just installed into a non-system prefix:

```sh
cmake -S . -B build \
  -DCMAKE_INSTALL_PREFIX="$HOME/newton-dev/prefix" \
  -DCMAKE_PREFIX_PATH="$HOME/newton-dev/prefix" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_STANDARD=17 \
  -DCMAKE_CXX_FLAGS="-I$HOME/newton-dev/prefix/include -DHAS_C99_LONGLONG=1 -DTARGET_RT_BIG_ENDIAN=0 -DTARGET_RT_LITTLE_ENDIAN=1 -Wno-multichar" \
  -DCMAKE_INSTALL_RPATH='$ORIGIN/../lib'
cmake --build build -j"$(nproc)"
cmake --install build
```

Watch the configure step: it clones its own private copy of NEWT/0's parser
(`FetchContent_Declare(newt0 ...)` in `tntk`'s `CMakeLists.txt`) — this is
normal and is *not* the standalone NEWT/0 interpreter from the table above,
just its parser source reused as a library.

`cmake --install` writes `~/newton-dev/prefix/bin/tntk`, RPATH'd to find
`libDCL.so` next to it (`$ORIGIN/../lib`), so nothing needs `LD_LIBRARY_PATH`
set globally — the repo's example Makefiles set it per-invocation anyway,
belt and suspenders.

## 4. Get the NTK platform files

`tntk` needs Apple's Newton 2.1 platform file (the machine-readable listing
of every proto/constant/frame the ROM exposes) to compile against. It is on
UNNA, the community Newton archive, as a direct download — no browser
session or account needed:

```sh
mkdir -p ~/newton-dev/ntk-platform-files
cd ~/newton-dev/ntk-platform-files
curl --fail --location --retry 2 -o 21PTF.ZIP \
  http://www.unna.org/unna/apple/development/NTK/platformfiles/21PTF.ZIP
unzip 21PTF.ZIP
cp 21PTF/NEWTON21.PTF "Newton 2.1"
```

Verify the download (checked 2026-08-04; UNNA's TLS chain is not generally
trusted so this uses plain HTTP, same choice `refs/fetch-refs.sh` makes for
the same host):

```text
sha256sum 21PTF.ZIP
# d93a066ea2f11982a50f0486747f639088ff6cdd739f4114987421a5b4a3310a
sha256sum "Newton 2.1"
# 6b68a58a354e59e0454797895dae8969da97d1ff56c8515f23b18d6d4c5e4be0
```

The rename matters: every `.nprj` in this repo declares `platform: "Newton
2.1"` (the literal platform string tntk looks up), and `tntk -P` names the
*directory* holding that file, not the file itself
(`docs/newton-client-notes.md`, "Package and compiler gotchas"). UNNA ships
it as `NEWTON21.PTF` inside the zip; it has to be renamed to match.

This URL is a discoverable, stable location, not a private mirror — it is
the exact link `tntk`'s own upstream README points readers at ("You will
also need the NTK Platform Files"). Point of provenance: the file is
Apple's, redistributed by UNNA under the same long-standing community
practice as everything else this repo fetches from there
(`refs/fetch-refs.sh`, `downloads/fetch-downloads.sh`).

## 5. Optional: the standalone NEWT/0 interpreter

Nothing in this repo's build path invokes it — every example's Makefile
calls `tntk` only. Build it if you want the `newt` REPL/interpreter itself:

```sh
cd ~/newton-dev
git clone https://github.com/ekoeppen/NEWT0.git
cd NEWT0
cmake -S . -B build \
  -DCMAKE_INSTALL_PREFIX="$HOME/newton-dev/prefix" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
cp build/newt "$HOME/newton-dev/prefix/bin/newt"   # its CMakeLists has no
                                                    # install(TARGETS newt);
                                                    # only the library rule.
```

## 6. Wire it to this repo

Nothing to configure — every example Makefile defaults to exactly this
layout:

```make
NEWTON_DEV ?= $(HOME)/newton-dev
TNTK ?= $(NEWTON_DEV)/prefix/bin/tntk
PLATFORMS ?= $(NEWTON_DEV)/ntk-platform-files
```

If you installed anywhere else, override on the command line
(`make -C examples/hello NEWTON_DEV=/opt/newton-dev`) or export the three
variables.

## 7. Prove it

```sh
cd newton-harness   # repo root
make -C examples/hello
```

Expected: `tntk` prints the project read, the compiled part, and ends with
`Package hello.pkg created.` A correct build is a few KB.

Then the real acceptance check — rebuild the current chat client and loader
with the reproducible-timestamp pipeline:

```sh
make newton-packages
cat runtime/staging/SHA256SUMS
```

`tntk` stamps its own build time into every package at byte offset 32
(`docs/newton-client-notes.md`), so a naive rebuild never hash-matches a
prior one even from identical source. `make newton-packages` overwrites that
one big-endian timestamp with a fixed value derived from
`NEWTON_SOURCE_DATE_EPOCH` (`docs/newton-client-notes.md`, "Reproducible
build"), so **the gate that matters is that the build succeeds and produces
the expected size** — and, if your toolchain matches this recipe exactly, it
can go further: on a second host built from this exact page, both
`harness-loader.pkg` and `harness-client.pkg` came out **byte-for-byte
identical**, matching SHA256, to the same build on the original host,
confirming the whole chain (compiler, patches, platform file, flags) is
truly reproducible and not just "close enough."

## Verified 2026-08-04

This recipe is exactly what was run, unmodified, to bring up a second host
("mars") from nothing (`ABSENT`: no prior `~/newton-dev`) beside the
original development host ("alpha"), both Arch Linux (`gcc` 16.1.1, `cmake`
4.4.x). Zero system packages were installed on the second host — everything
in §1's prerequisite list was already present. All three repos were cloned
at the tip of `master`:

| Repo | Commit |
| --- | --- |
| cDCL | `46aef5750e0275380c7b9488626a3294643d8504` |
| tntk | `f9f3f5dd2444997f1febd5648f60ec71a3a08afd` |
| NEWT/0 (standalone, optional) | `025bc268742c493fb1ce2dcea10ebeb4846652cf` |

Both patches applied cleanly to a fresh `tntk` clone in sequence
(`tntk-project-version.patch` then `tntk-gcc16-cstring.patch`); omitting the
second one reproduced the exact compile failure predicted above,
`'memset' was not declared in this scope`, confirming it is load-bearing on
this GCC version and not a leftover from something else. `tntk` built to
309,584 bytes and `libDCL.so` to 752,976 bytes on both hosts — identical
sizes, different hosts, same source and flags.

`make -C examples/hello` produced a 1,104-byte `hello.pkg`. `make
newton-packages` then produced `harness-loader.pkg` and `harness-client.pkg`
whose SHA256 matched a fresh `make newton-packages` run on the original host
exactly:

```text
79eb20930e3e6bd1b905e098a82536100f0c4373661e0e51f28616c89e235de1  harness-loader.pkg
70a5b901fe0955f1f2c1f6f15edd4b698fb8c4debe182a30aea69f2792d27a1a  harness-client.pkg
```

The NTK platform file fetched fresh from UNNA in §4 was also byte-identical
(same SHA256) to the copy already present on the original host, which had
been in place since this project's very first toolchain bring-up — so the
UNNA URL is confirmed stable and the file unchanged since.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `tntk` configure step fails to find `DCL_LIBRARY` | `CMAKE_PREFIX_PATH` missing from the `tntk` configure command, or cDCL not installed/installed elsewhere | Re-run cDCL's `cmake --install`, then re-configure `tntk` with `-DCMAKE_PREFIX_PATH` pointing at the same prefix |
| `tntk.cpp:195:9: error: 'memset' was not declared in this scope` | `tntk-gcc16-cstring.patch` not applied | Apply it (§3) |
| Rebuilding `harness-client.pkg` regresses to package version 1 | `tntk-project-version.patch` not applied to the live `tntk` checkout | Apply it (§3); the live checkout stays uncommitted in `tntk`'s own tree — this is expected, see `docs/phase3-chat-round.md` |
| `tntk: Reading platform file` then a symbol/parse error | Platform file misnamed, or the wrong directory passed to `-P` | Confirm `ntk-platform-files/Newton 2.1` exists (exact name, no extension) and `PLATFORMS` points at its parent directory, not the file |
| `error while loading shared libraries: libDCL.so` running `tntk` directly (outside `make`) | `tntk`'s RPATH is `$ORIGIN/../lib`, correct for the installed prefix layout, but the binary was copied somewhere else | Run it from `prefix/bin/`, or set `LD_LIBRARY_PATH` to `prefix/lib` |

## What this does not cover

Running the emulator (Einstein) or the always-on chat/tools servers is a
separate, container-based setup with its own one-time requirements (a Newton
ROM dump you must own, the NTK platform file again for package installs from
inside the container, rootless Podman) — see `docs/dev-harness.md`.
Installing a built `.pkg` onto real or emulated hardware is
`docs/install-paths.md`.
