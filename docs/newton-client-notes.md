# Newton Harness client and loader notes

## Current source state

- `examples/harness-loader/Main.newt` is the NewtonOS 2.1 package installer. The user enters a staged `.pkg` filename; it opens an NIE link, connects to `10.42.0.1:18081`, downloads that name with HTTP/1.0, validates a `Content-Length` from 1 to 524,288 bytes, stores the exact body in a VBO, and installs it with `SuckPackageFromBinary`.
- `examples/harness-client/Main.newt` is Harness Client v1.1. It identifies itself in the window and package title and fetches the small plain-text `/status` resource over the same HTTP/1.0 network path.
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
- The `.nprj` `name` and the app's `appSymbol` must remain stable for an update to replace the intended application. The loader and client deliberately use different symbols, so the client update cannot replace the loader.
- The project platform string is exactly `Newton 2.1`, and tntk's `-P` argument names the directory containing that platform file, not the file itself.
- tntk's generated package changes only at the package timestamp for identical source in the currently pinned toolchain. If a future tntk changes other bytes, the two-build hash check should fail rather than expanding normalization casually.
- NewtonScript method names may print with different capitalization in tntk's diagnostic dump (`Stop` appears as `stop`); that is normal symbol behavior.
- Keep device strings ASCII and responses small. The client caps the complete HTTP status response at 2,048 bytes and displays at most 80 body characters for MP2100-class memory and screen constraints.
- `protoBasicEndpoint:Input` returns binary chunks and `nil` at EOF. HTTP parsing therefore cannot assume headers or body align with a chunk boundary.
- HTTP/1.0 plus `Connection: close` is intentional. It avoids persistent-connection and chunked-transfer handling on NewtonOS.

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

Loader ZC39 v2.3 shows its version, accepts a name-only `.pkg` filename, reports fetch/install progress on its large button, and performs one deferred retry after a link, TCP, HTTP, allocation, or length failure. The removed LAN/Mars toggle bought enough package space for the fix; ZC39 always connects to `10.42.0.1`. Filenames are limited to ASCII letters, digits, `-`, `_`, and `.`, and must end in `.pkg`; no directory-listing protocol was added.

Output is asynchronous and explicitly uses `form: 'string`; its completion script reports send failure. Input remains `'binary` for the complete HTTP response. The first 1,024-byte target contains the header and initial body bytes; `HeaderReceived` copies that body suffix with `BinaryMunger`, then installs binary body specs at advancing VBO offsets. For the 82-byte-header / 18,320-byte-body hardware case, the offsets are 942, 9,134, 17,326, and 18,320.

An input spec normally persists after `InputScript`: Newton automatically reposts the same spec. Calling `SetInputSpec` inline is needed only to change or stop it (and to repost one-shot options), not before every callback. Evidence: `refs/NewtonProgrammerGuide20.txt:50167-50178,50543-50547` and `refs/NewtonProgrammerRef20.txt:56549-56557`. ZC39 changes specs inline because each binary target offset and final chunk count differ; it never calls synchronous `Input()`. The NIE handling and ZC38 teardown re-entry guard remain unchanged.

The emulator acceptance run downloaded the staged `inetenbl.pkg` at 318,276 bytes and opened its live `PCMCIA Ethernet` / `NE2000` configuration UI after installation. During a repeat large transfer, the Newton opened `AllIcons` while `ss -tnp` still showed the sole client connection to `10.42.0.1:18081` in `ESTAB`, demonstrating that the event loop remained responsive. The physical Newton was not used.

For ZC39, the one-shot `scripts/verify-loader-download.py` check served the exact 82-byte header plus 18,320-byte `harness-tools.pkg` body. Both unchanged ZC38 and fixed ZC39 ACKed all 18,402 bytes in the private emulator, so Einstein did not reproduce the hardware-only 2,920-byte stall. ZC39 parsed 18,320 and reached `SuckPackageFromBinary`; the copied flash then rejected the already-present package identity. Evidence: `runtime/evidence/zc39-baseline-ack.txt` and `runtime/evidence/zc39-fixed-ack.txt`. Physical ZC39 remains unverified.

Client v1.1 shows its name and version and provides one large `Check harness status` control. It requests:

```http
GET /status HTTP/1.0
Host: 10.42.0.1
Connection: close
```

The expected response is HTTP/1.0 status 200 followed by a short plain-ASCII body such as `Harness server OK`.

## Path toward ink and notes (not implemented in v1)

Keep the current view as the connection/status shell. A later version can add one Newton-native drawing/ink view and serialize completed strokes or selected Notes data into a bounded request body. Send one item at a time to a harness endpoint, wait for an explicit server acknowledgement, and retain the local item until acknowledged. That preserves the current small-memory, close-after-each-request transport and leaves batching, interpretation, and richer synchronization on the server. Do not add an ink abstraction or queue until the Newton APIs and payload format have been verified on-device.
