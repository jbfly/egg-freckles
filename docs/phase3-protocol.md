# Phase 3 native protocol

Connect to TCP port 6801 and immediately send the exact ASCII line `~NEWTONCLI 1\r\n`. Any other first input uses the existing PT100 terminal protocol.

## Frames

```text
:SS OP payload*HH\r\n
ACK SS\r\n
NAK SS REASON\r\n
```

`SS` is decimal `00` through `99`. The optional payload is omitted with its preceding space when empty. Every encoded frame, including CRLF, is at most 240 bytes and contains ASCII only.

| Direction | Type | Payload |
|---|---|---|
| Client → host | `HELLO` | `NEWTON1`, optionally followed by a space and app version |
| Client → host | `MSG` | One prompt; `/new` resets the conversation |
| Host → client | `STAT` | `READY`, `THINKING`, or `ERROR short-text` |
| Host → client | `TEXT` | One ASCII display chunk |
| Host → client | `PROMPT` | Empty; the turn is complete |

Long replies use multiple `TEXT` frames. A prompt too long for one frame uses
the `MSGP` extension below; a client that does not implement it still sends one
`MSG` and the host still answers it, unchanged.

## Extension: `MSGP` — multi-frame prompts

Added by Track F1 (2026-08-03). Nothing above changed: `MSGP` is a new
client → host op, and a host that speaks it answers a plain `MSG` exactly as
before.

```text
:SS MSGP KK NN <chunk>*HH\r\n
```

`KK` is the part number and `NN` the total, each **exactly two decimal digits**,
`01` through `99`. `<chunk>` is a literal slice of the prompt — the host
concatenates chunks with nothing between them, so leading and trailing spaces
inside a chunk are significant. Parts are acknowledged like any other frame, one
outstanding at a time; the ACK for part `KK` is what releases part `KK+1`.

The chunk budget is **220 characters**: a frame is `":"` + body + `"*HH"` +
CRLF, so 240 bytes leaves 234 for the body and `"SS MSGP KK NN "` costs 14 of
them. A single-frame prompt therefore fits 227 characters as a plain `MSG`.

Host state, per connection, deliberately minimal:

- Part `01` always **restarts** the buffer and fixes `NN` for the run.
- Any other part must be exactly `len(buffer) + 1` and carry the same `NN`;
  anything else — including a malformed payload — is `NAK SS PART` and does not
  touch the buffer, so the correct part may follow.
- A plain `MSG` **drops** any partial buffer and is handled as itself.
- On part `NN` the chunks are joined and treated exactly like a `MSG` payload.
- The assembled prompt is capped at **8192 bytes**, matching the note bridge's
  note limit. Crossing it clears the buffer and answers `STAT ERROR prompt over
  8192 bytes` followed by `PROMPT`, ending the turn visibly.

Buffers are per TCP connection and reset with the sequence state.

## Checksum and delivery

`HH` is uppercase hexadecimal SUM8: add each ASCII byte in `SS OP payload` (or `SS OP` for an empty payload), keep the low eight bits, and print two hex digits. This byte-oriented checksum is deliberately simpler than model100's line-oriented checksum.

Each direction has at most one unacknowledged frame. ACK every valid frame. NAK a recoverable parse, length, or checksum error using the recovered sequence. On timeout or matching NAK, resend the identical bytes with the identical sequence; stop after three retries beyond the first send. A receiver remembers the last accepted sequence, ACKs that duplicate again, and applies it only once. Sequence state resets on each TCP connection.
