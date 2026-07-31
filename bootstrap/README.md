# NS Basic 2.52b Newton package bootstrap

This is the recovered program currently saved in NS Basic's single **Demo** slot on the physical MessagePad 2000. It is the only hardware-proven bare bootstrap in this project: the transcript records six package installs over Wi-Fi, including a complete 15,000-byte transfer followed by `SuckPackageFromBinary` installation.

The checked-in program preserves the Newton's last saved target, the house-LAN server at `192.168.1.11:18081`. See [Target address](#target-address-house-lan-versus-mars) before using mars.

## Program operation, line by line

| Line | What it does |
|---:|---|
| 10 | Builds the required NIE `inet` service option. `512` is the numeric value used on the device for `opSetRequired`; `result:nil` is intentionally present. |
| 20 | Builds template data containing the NIE link ID as a `struct` with one unsigned-long field. |
| 30 | Wraps line 20 as the required `ilid` option. |
| 40 | Builds template data containing Internet transport version `1`. |
| 50 | Wraps line 40 as the required `itsv` option. |
| 60 | Evaluates the three option-building functions separately into locals, then returns `[a,b,c]`. This is the decisive NS Basic 2.52b compatibility fix; the inline form throws `type.ref.frame` before `Instantiate` runs. |
| 70 | Builds the remote IPv4 address and TCP port as four bytes plus one short. The saved version targets `192.168.1.11:18081`. |
| 80 | Wraps line 70 as the required `itrs` remote-address option. |
| 90 | Passes a completed package VBO to the Newton store's package installer. |
| 100 | Clears the VBO cache, then delays installation by one second so package installation does not occur inside the endpoint input callback. |
| 110 | Accepts input only when the endpoint reports the full 15,000-byte termination count, then schedules installation. |
| 120 | Allocates a 15,000-byte package VBO in the default store. |
| 130 | Defines the endpoint termination condition: exactly 15,000 bytes. |
| 140 | Defines binary input into the VBO, starting at offset zero, with the 15,000-byte termination/discard limit and line 110 as `InputScript`. |
| 150 | Creates the endpoint frame from ROM magic pointer `@383`, with `U` as parent. Do not add or remove a prototype layer. |
| 155 | Converts the current NIE exception to its numeric error value for line 160's handler. |
| 160 | Creates the endpoint, calls `Instantiate(endpoint, options)` in the proven order, then binds it with the proven callback/options frame. Returns `'ok` on success and decodes an exception on failure. |
| 170 | Connects synchronously to the address from line 80, with a 45-second timeout. |
| 180 | Allocates the VBO and installs the binary input specification on the endpoint. |
| 190 | Sends the one-byte bootstrap request `G`; the host's raw sender responds with exactly 15,000 bytes. |
| 200 | Runs endpoint setup, connect, listen, and send in that order. |
| 210 | Receives the NIE link callback, records the link ID, rejects errors/duplicates/non-connected states, and starts the transfer only for a fresh connected link. |
| 220 | Requests an NIE link and names line 210's `grab` function as the callback. |
| 230 | Initializes the global endpoint slot to `NIL`. |
| 240 | Starts link acquisition. |
| 250 | Keeps NS Basic alive for 60 seconds so the link callback and transfer can complete. |
| 300 | Repeats line 10. This redundant line was still stored on the successful device and is therefore preserved exactly. Line 310, an obsolete endpoint redefinition, was explicitly deleted before success. |

## Exact re-entry procedure on the Newton

These steps preserve the workflow used in the successful transcript. Do this on external power or fresh batteries; losing power while installing a package risks data loss.

1. In **Extras**, open **NS Basic 2.52b Demo**.
2. Open the **Statement** entry view. If an old program is present and must not be preserved, start a new program first; otherwise entering a numbered line replaces only that line.
3. For each line in `nsbasic-bootstrap.bas`, in ascending numeric order:
   1. Tap the statement input field.
   2. Type the entire numbered line, including its line number.
   3. Press **Return** once to store it.
4. After line 300, enter only `310` followed by **Return**. In numbered BASIC this deletes any stale line 310; the successful program must not contain the old `protoBasicEndpoint` redefinition.
5. Enter `LIST` in the **Command** field and press **Return**. Page through the listing and compare every stored line with `nsbasic-bootstrap.bas`. Pay special attention to:
   - line 60: `BEGIN LOCAL a,b,c;...;[a,b,c] END`;
   - line 70: the intended server address;
   - line 140: `InputScript:U.got`;
   - line 150: exactly `{_proto:@383,_parent:U}`;
   - line 160: `Instantiate(U.e,U:opts(id))` followed by `Bind(nil,{async:nil,reqTimeout:10000})`;
   - absence of line 310.
6. Tap **REPLACE DEMO** and accept the replacement. This writes the program into NS Basic's single Demo slot; the transcript confirms it survives a soft reset.
7. Prepare the host raw sender so TCP port `18081` returns exactly 15,000 bytes after receiving the byte `G`. The repository's `runtime/dual_send.py` is the later proven dual-protocol server when its bootstrap payload is staged correctly.
8. In Internet Setup, select the network setup that reaches the address in line 70.
9. Return to NS Basic and tap **RUN** once. Allow the full 60-second `WAIT` window. A sender-side connection with `received b'G'` and `sent 15000` proves transfer; the package appearing in **Extras** proves installation.
10. A later “Connection may have been dropped” dialog can be the sender closing the socket after all bytes were delivered. Dismiss it and check **Extras** before treating it as a failed install.

Do not use a bare `opSetRequired` identifier, `protoBasicEndpoint`, reversed `Instantiate` arguments, or the old inline line 60. Those were investigated; the stored forms above are the proven ones.

## Target address: house LAN versus mars

The file intentionally records what is on the Newton now:

```basic
70 FUNCTION adata() {arglist:[192,168,1,11,18081],typelist:['struct,'byte,'byte,'byte,'byte,'short]}
```

For mars on the isolated `10.42.0.0/24` Newton network, replace only line 70 with:

```basic
70 FUNCTION adata() {arglist:[10,42,0,1,18081],typelist:['struct,'byte,'byte,'byte,'byte,'short]}
```

Then tap **REPLACE DEMO** again. Nothing else changes.

## Confidence by line

`VERBATIM` means the final line is quoted literally in the recovered conversation. `RECONSTRUCTED` means a literal intended listing is combined with later on-device transcription or an explicit edit sequence. Full quotes and source locations are in [provenance.md](provenance.md).

| Line | Confidence | Basis |
|---:|---|---|
| 10 | RECONSTRUCTED | Intended literal plus on-device transcription confirming `512` and `result:nil`; line 300 confirms the exact final body. |
| 20 | VERBATIM | On-device transcription quotes the complete stored line. |
| 30 | RECONSTRUCTED | Intended literal plus on-device confirmation of the final fields and literal `512`. |
| 40 | VERBATIM | On-device transcription quotes the complete stored line. |
| 50 | RECONSTRUCTED | Intended literal plus on-device confirmation of the final fields and literal `512`. |
| 60 | VERBATIM | The exact locals-based replacement is quoted, then identified as the bug fix after successful transfer/install. |
| 70 | VERBATIM | The exact house-LAN replacement line is quoted; later handoff confirms it remains saved. |
| 80 | RECONSTRUCTED | Intended literal plus on-device confirmation of `512`, `result:nil`, and `U:adata()`. |
| 90 | RECONSTRUCTED | Literal intended listing; on-device transcription says lines 90–130 all match. |
| 100 | RECONSTRUCTED | Literal intended listing; on-device transcription says lines 90–130 all match. |
| 110 | RECONSTRUCTED | Literal intended listing; on-device transcription says lines 90–130 all match. |
| 120 | RECONSTRUCTED | Literal intended listing; on-device transcription says lines 90–130 all match. |
| 130 | RECONSTRUCTED | Literal intended listing; on-device transcription says lines 90–130 all match. |
| 140 | VERBATIM | Exact corrected line quoted from the on-device listing/edit. |
| 150 | VERBATIM | Exact final `@383` line quoted and later emulator matrix confirms it. |
| 155 | RECONSTRUCTED | On-device transcription quotes the complete added line. |
| 160 | VERBATIM | Exact restored line quoted; later photo comparison says it was stored exactly and successful matrix confirms its calls. |
| 170 | RECONSTRUCTED | Literal intended listing; on-device transcription says lines 170–200 are clean. |
| 180 | RECONSTRUCTED | Literal intended listing; on-device transcription says lines 170–200 are clean. |
| 190 | RECONSTRUCTED | Literal intended listing; on-device transcription says lines 170–200 are clean. |
| 200 | RECONSTRUCTED | Literal intended listing; on-device transcription says lines 170–200 are clean. |
| 210 | RECONSTRUCTED | Complete on-device line quoted. |
| 220 | RECONSTRUCTED | Complete on-device line quoted. |
| 230 | RECONSTRUCTED | On-device line quoted as `LET e=NIL`. |
| 240 | RECONSTRUCTED | Complete on-device line quoted. |
| 250 | VERBATIM | On-device tail transcription quotes `WAIT 60000`. |
| 300 | RECONSTRUCTED | On-device tail transcription quotes the complete duplicate and says it is byte-identical to line 10. |

**UNCERTAIN lines: none.** Overall confidence is high. The reconstructed lines are not guesses: each is anchored by a literal earlier listing and a later statement that the corresponding on-device line or range matched, but the later transcript did not reprint every character individually.
