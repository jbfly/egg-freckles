# UNNA archive survey for NewtonOS/Einstein development

Surveyed 2026-07-25. I searched UNNA's complete `unnalisting.txt` index and walked the relevant `development`, `apple/development`, `apple/documentation/developer`, `internet`, `unix`, `macos`, and `windows` browse pages. Every URL in the table was checked with a HEAD request and returned HTTP 200. UNNA's HTTPS certificate chain is not trusted by this host, so verification required `curl -k -I -L`; “verified” below means the server resolved the exact path and returned 200, not that its TLS chain validated normally.

## Top three recommendations

### 1. UnixNPI 1.1.3 source

Download this first because it is the closest UNNA item to replacing menu/OCR package installation with a host command. It is a small GPL C implementation of the built-in Newton package-upload protocol, invoked as `unixnpi package.pkg`, with no extra Newton package required. Its documented workflow still starts the Newton Dock/Connection application and taps Connect, so it is not proven zero-click on Einstein by itself; the value is the inspectable host-side protocol implementation, which could be aimed at Einstein's serial/pipe transport or combined with a Newton-side auto-connect mechanism.

### 2. Newton Programmer's Reference 2.0

This is the exact companion volume missing from the repository, not another copy of the Programmer's Guide. It is the authoritative slot-by-slot reference needed for endpoint methods and structures, including the input-specification details that had to be reconstructed experimentally in Rounds 12–14. It should be added to the local references before more communications work.

### 3. NewtonIM source

This is the strongest directly inspectable NIE TCP source I found. The ZIP contains an NTK project and NewtonScript source/resources whose extracted strings show `epInstantiate`, `epBind`, `epConnect`, `epInputSpec`, `SetInputSpec`, endpoint state callbacks, and NIE TCP option builders. It is a Jabber client rather than HTTP, but it provides a real application-level endpoint lifecycle and is therefore a better control example for the loader than API prose alone.

## Ranked downloads

| Rank | Item name | Direct download URL | Size / format | Priority served | Why it matters to us | URL check |
|---:|---|---|---|---|---|---|
| 1 | UnixNPI 1.1.3 source | <https://www.unna.org/unna/unix/unixnpi-1.1.3.tar.gz> | 21.44 KB, `.tar.gz` C source | **1 — automated install** | CLI package uploader using the built-in Newton upload protocol; best compact starting point for a Linux-to-Einstein serial/pipe installer. | HTTP 200 |
| 2 | Newton Programmer's Reference 2.0 | <https://www.unna.org/unna/development/documentation/NewtonProgrammerRef20.pdf> | 5.84 MB, PDF | **2 — Programmer's Reference** | Exact missing companion reference; documents endpoint APIs and input-spec frames at slot level. | HTTP 200 |
| 3 | NewtonIM source | <https://www.unna.org/unna/internet/NewtonIM/NIM-source.zip> | 88.59 KB, ZIP/NTK source | **3 — working NIE TCP source** | Verified source contains the full NIE TCP endpoint sequence and callback/state machinery used by a real network client. | HTTP 200 |
| 4 | `lpkg` source | <https://www.unna.org/unna/unix/lpkg.tar.gz> | 3.56 KB, `.tar.gz` C source | **1 — automated install** | Tiny `lpkg [-d device] package.pkg` implementation with explicit `newtdock` `dock`/`stim`/`lpkg` commands; especially easy to read or adapt, though its README warns its incomplete MNP handling can hang on retransmission. | HTTP 200 |
| 5 | Newtl 2.01 source | <https://www.unna.org/unna/unix/newtl-2.01.tar.gz> | 58.63 KB, `.tar.gz` C++ source | **1 and 4 — install/toolchain** | Unix CLI supports package loading through Newton Connection (`-l`), XMODEM (`-x`), and Slurpee, and can send `.nwt` NewtonScript source through Newt's preprocessor path. | HTTP 200 |
| 6 | NHttpLib 2.3.1 source | <https://www.unna.org/unna/internet/NHttpLib2.3.1/NHttpLib-2.3.1-src-macos.sit> | 23.24 KB, StuffIt/NTK source | **3 — HTTP over NIE** | Source for the HTTP library used by several archived Newton clients; likely the most concentrated HTTP implementation to compare with the loader. StuffIt contents were not inspectable with the tools installed here. | HTTP 200 |
| 7 | Courier 0.5 source | <https://www.unna.org/unna/internet/web-browsers/Courier0.5/Courier-0.5-src.sit> | 42.95 KB, StuffIt/NTK source | **3 — HTTP over NIE** | Complete source-labelled web browser release bundled in UNNA alongside NHttpLib 3.1; useful for seeing real request/response consumption above the HTTP library. StuffIt contents were not inspectable here. | HTTP 200 |
| 8 | Apple Async Serial endpoint sample | <https://www.unna.org/unna/apple/development/Examples/Endpoints/AsyncSerial.sea> | 21.24 KB, Mac self-extracting archive | **1 and 3 — serial path/endpoint lifecycle** | Apple sample for asynchronous endpoint setup and I/O; not NIE/TCP, but relevant to wiring a serial or pipe transport into an automated installer. | HTTP 200 |
| 9 | Apple Comms FSM sample | <https://www.unna.org/unna/apple/development/Examples/SampleCodeMac/Comms%20FSM-2.sea.hqx> | 81.98 KB, BinHex self-extracting archive | **3 and 5 — endpoint state handling** | Apple's communications finite-state-machine sample is directly relevant to the `Grabbed` progress-state bug found in Round 14. | HTTP 200 |
| 10 | Newt 3.4 distribution | <https://www.unna.org/unna/development/languages/NewtonScript/newt34.zip> | 300.71 KB, ZIP with `.pkg`, docs, and `.nwt` examples | **4 — `.newt`/NewtonScript toolchains** | On-Newton Newt development environment with source examples and package tools; not tntk, but useful for understanding the `.nwt` lineage and alternate compilation workflow. | HTTP 200 |
| 11 | Newton DIL Tester source | <https://www.unna.org/unna/macos/NewtonDILTester/NewtonDILTesterSource.sit> | 507.38 KB, StuffIt source | **1 — Dock/DIL automation** | Source for exercising Apple's Desktop Integration Libraries (DILs); potentially useful protocol/transport evidence if the simpler Unix uploaders cannot talk to Einstein. | HTTP 200 |
| 12 | NIE 2 developer installer | <https://www.unna.org/unna/development/nie2devin.zip> | 633.28 KB ZIP containing a 667.53 KB Windows installer | **5 — NIE documentation** | The only clearly labelled NIE 2 developer distribution found outside the already-held NIE 1.1 material; worth extracting to inventory later, but its ZIP contains only an `.exe`, so this survey could not confirm the embedded documents. | HTTP 200 |
| 13 | Apple endpoint Q&A collection entry | <https://www.unna.org/unna/apple/documentation/developer/QAs-2.x/html/endpoint.htm> | 37.57 KB, HTML | **3 and 5 — endpoint/NIE notes** | Searchable Apple developer Q&A on endpoint behavior and edge cases; lower value than working source but faster to consult than the full manuals. | HTTP 200 |
| 14 | Apple input-spec Q&A | <https://www.unna.org/unna/apple/documentation/developer/QAs-2.x/html/inptspec.htm> | 2.51 KB, HTML | **2, 3, and 5 — input specs** | Focused note on endpoint input specifications; useful as a cross-check for the `SetInputSpec`/`Input` behavior established experimentally. | HTTP 200 |

## Important limitations and things not found

- **No Einstein development or automation material was present in UNNA's index.** Searches for Einstein, emulator command-line flags, monitor/console/debug-port controls, and package injection produced no relevant archive entry. UNNA's `development/emulators` directory contains only `fo'newton` and `gnuton`.
- **No NCX, `newton-tools`, `dockingtool`, or explicitly named Desktop Connection Library distribution was found.** UNNA does have old Apple DIL samples and the DIL Tester source, but nothing I could identify as those modern tools.
- **No tntk archive or tntk-specific documentation was found.** Newt/Newtl are historically related `.nwt` workflows, not substitutes for the current tntk build.
- **No Cape or NewtHTTP source was found by name.** NHttpLib, Courier, NewtonIM, NetHopper's SDK, and several other application sources exist; NewtonIM was the only one whose downloaded source I could directly verify contained the full raw endpoint lifecycle during this survey.
- **NetHopper's archived SDK is an extension/API kit, not the browser's networking source**, so it was not ranked above the actual source-labelled HTTP archives.
- **The Unix installers do not prove zero-click operation.** UnixNPI and `lpkg` wait for the Newton-side Dock/Connection session, while Newtl's alternatives require Connection, XMODEM support, or Slurpee. They are valuable because they remove the host GUI and expose the protocol, not because the archive documents an Einstein-only unattended path.
- The already-held Programmer's Guide 2.0, NIE 1.1 developer material/Goodies, and NIE Patch v2 were deliberately excluded.
