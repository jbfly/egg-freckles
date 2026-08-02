# Newton Harness client and loader notes

## Current source state

- `examples/harness-loader/Main.newt` is the NewtonOS 2.1 package installer. The user enters a staged `.pkg` filename; it opens an NIE link, connects to `10.42.0.1:18081`, downloads that name with HTTP/1.0, validates a `Content-Length` from 1 to 524,288 bytes, stores the exact body in a VBO, and installs it with `SuckPackageFromBinary`.
- `examples/harness-client/Main.newt` is Newton Chat 2.1-a1 with the fresh package identity `HarnessClientA1:jbfly`. It holds one framed TCP session to port 6801, sends bounded ASCII prompts, and renders the model response in a 6 KiB transcript.
- `pkg_publisher.py` is the source-level reference server for `/harness-client.pkg` and `/status`. The separate live raw server is operational runtime state, not part of this build path.
- Each app has a `.nprj` file and a small Makefile that invokes tntk against the Newton 2.1 platform file.

## Reproducible build

From the repository root:

```sh
make newton-packages
```

This builds both projects and writes install candidates to:

```text
runtime/staging/harness-loader.pkg
runtime/staging/harness-client.pkg
runtime/staging/SHA256SUMS
```

The defaults use the local toolchain under `~/newton-dev`. Override the existing per-project Make variables when needed:

```sh
make newton-packages \
  TNTK=/usr/local/bin/tntk \
  PLATFORMS=/platforms
```

`tntk` embeds its current Newton epoch time at package bytes 32 through 35, so otherwise identical builds have different hashes. The top-level target replaces that one big-endian timestamp with `NEWTON_SOURCE_DATE_EPOCH + 2082844800` (Unix-to-Newton epoch offset). The default Unix epoch is `1767225600` (`2026-01-01T00:00:00Z`). Set `NEWTON_SOURCE_DATE_EPOCH` to another stable Unix timestamp if release policy requires it.

## Package and compiler gotchas

- A Newton package starts with `package0`. The reproducible target checks this magic and minimum header length before changing the timestamp.
- A distinct build must receive a fresh `.nprj` `name` and matching `appSymbol`; changing only the package version does not permit replacement. The exact same verified binary may of course be installed on multiple devices. Loader and client identities remain separate.
- The project platform string is exactly `Newton 2.1`, and tntk's `-P` argument names the directory containing that platform file, not the file itself.
- tntk's generated package changes only at the package timestamp for identical source in the currently pinned toolchain. If a future tntk changes other bytes, the two-build hash check should fail rather than expanding normalization casually.
- NewtonScript method names may print with different capitalization in tntk's diagnostic dump (`Stop` appears as `stop`); that is normal symbol behavior.
- Keep device strings ASCII and responses small. The chat client caps each wire frame at 240 bytes and retains at most 6 KiB of transcript.
- The chat input path is `SetInputSpec`-only. Bind, connect, handshake, ACK, and message outputs use `async: true`; every output explicitly uses `form: 'string`.

## `SuckPackageFromBinary`

The loader allocates a package VBO with:

```newtonscript
GetDefaultStore():NewVBO('package, contentLength)
```

It copies response bytes into that VBO with `BinaryMunger` and only installs after the exact advertised body length arrives. `ClearVBOCache` is not a NewtonOS 2.1 global and must not be called. Installation is delayed until after the endpoint receive callback returns:

```newtonscript
AddDelayedCall(
    func(theBinary)
        GetDefaultStore():SuckPackageFromBinary(theBinary, nil),
    [binary],
    5000);
```

Deferring matters: package installation can alter application state, so it should not run inside the endpoint receive stack. Keep the binary referenced until the deferred call runs. The current install exception is intentionally contained because there is no safe UI reference in that deferred function; a later version can report install completion through a persistent status slip.

## Loader and client behavior

Loader ZC40 v2.4 shows its version, accepts a name-only `.pkg` filename, reports fetch/install progress on its large button, and performs one deferred retry after a link, TCP, HTTP, allocation, or length failure. The removed LAN/Mars toggle bought enough package space for the fix; ZC40 always connects to `10.42.0.1`. Filenames are limited to ASCII letters, digits, `-`, `_`, and `.`, and must end in `.pkg`; no directory-listing protocol was added. ZC40 also sets `installQueued` before deferring installation, so a repeated final input callback cannot schedule the same binary twice; only a genuinely new `TryFetch` resets that guard.

Output is asynchronous and explicitly uses `form: 'string`; its completion script reports send failure. Input remains `'binary` for the complete HTTP response. The first 1,024-byte target contains the header and initial body bytes; `HeaderReceived` copies that body suffix with `BinaryMunger`, then installs binary body specs at advancing VBO offsets. For the 82-byte-header / 18,320-byte-body hardware case, the offsets are 942, 9,134, 17,326, and 18,320.

An input spec normally persists after `InputScript`: Newton automatically reposts the same spec. Calling `SetInputSpec` inline is needed only to change or stop it (and to repost one-shot options), not before every callback. Evidence: `refs/NewtonProgrammerGuide20.txt:50167-50178,50543-50547` and `refs/NewtonProgrammerRef20.txt:56549-56557`. ZC39 changes specs inline because each binary target offset and final chunk count differ; it never calls synchronous `Input()`. The NIE handling and ZC38 teardown re-entry guard remain unchanged.

The emulator acceptance run downloaded the staged `inetenbl.pkg` at 318,276 bytes and opened its live `PCMCIA Ethernet` / `NE2000` configuration UI after installation. During a repeat large transfer, the Newton opened `AllIcons` while `ss -tnp` still showed the sole client connection to `10.42.0.1:18081` in `ESTAB`, demonstrating that the event loop remained responsive. The physical Newton was not used.

For ZC39, the one-shot `scripts/verify-loader-download.py` check served the exact 82-byte header plus 18,320-byte `harness-tools.pkg` body. Both unchanged ZC38 and fixed ZC39 ACKed all 18,402 bytes in the private emulator, so Einstein did not reproduce the hardware-only 2,920-byte stall. ZC39 parsed 18,320 and reached `SuckPackageFromBinary`; the copied flash then rejected the already-present package identity. Evidence: `runtime/evidence/zc39-baseline-ack.txt` and `runtime/evidence/zc39-fixed-ack.txt`.

Physical hardware proved the complete WiFi path with fresh packages. ZC40 installed and launched a 1,136-byte proof, then installed and launched a 321,920-byte proof; Mars logged one GET for the large success and TCP ACKs for all 322,003 HTTP response bytes. The first large attempt reached installation but failed with Newton error `-10617` (card memory full); freeing the `Ultimate Newton` flash card from 498 KB to 893 KB made the unchanged package succeed. Allow roughly twice the package size for the download VBO plus installation copy.

The earlier same-name warning followed a real retry: Mars logged a first partial transfer and a second complete GET. ZC40's `installQueued` guard remains cheap protection against repeated final callbacks, but duplicate callback scheduling was not the cause observed on hardware. Its post-install `GetPkgRef` check can still display `Install not confirmed` even when a package installs and launches, so treat that text as a status-check defect rather than transfer failure.

Newton Chat 2.1-a1 uses the unchanged Phase 3 framed protocol. On 2026-08-02
an isolated configured Einstein flash connected through one TCP session, sent
`Reply with exactly A1 ASYNC OK`, rendered `Agent: A1 ASYNC OK`, cleared the
in-flight state, and returned to `Ready`. Its production address remains
`10.42.0.1:6801`; the address is a view slot so an isolated emulator can point
at its rootless-container host without rebuilding or reusing the identity.

On the physical MP2000, the A1 package appears in Extras with the short caption
**Newton Chat**, not **Newton Chat 2.1-a1**. Opening it shows the full window
title **Newton Chat 2.1-a1**, which is the reliable on-device version check.
Do not assume an Extras item captioned **Newton Chat** is an older build without
opening it. This hardware install followed a single HTTP 200 response for the
19,040-byte package, with all 19,122 HTTP bytes acknowledged; ZC40 nevertheless
ended with its known-faulty `Install not confirmed` status.

## Path toward ink and notes (not implemented in v1)

Keep the current view as the connection/status shell. A later version can add one Newton-native drawing/ink view and serialize completed strokes or selected Notes data into a bounded request body. Send one item at a time to a harness endpoint, wait for an explicit server acknowledgement, and retain the local item until acknowledged. That preserves the current small-memory, close-after-each-request transport and leaves batching, interpretation, and richer synchronization on the server. Do not add an ink abstraction or queue until the Newton APIs and payload format have been verified on-device.
