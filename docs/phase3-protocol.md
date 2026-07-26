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

Long prompts are rejected rather than split. Long replies use multiple `TEXT` frames.

## Checksum and delivery

`HH` is uppercase hexadecimal SUM8: add each ASCII byte in `SS OP payload` (or `SS OP` for an empty payload), keep the low eight bits, and print two hex digits. This byte-oriented checksum is deliberately simpler than model100's line-oriented checksum.

Each direction has at most one unacknowledged frame. ACK every valid frame. NAK a recoverable parse, length, or checksum error using the recovered sequence. On timeout or matching NAK, resend the identical bytes with the identical sequence; stop after three retries beyond the first send. A receiver remembers the last accepted sequence, ACKs that duplicate again, and applies it only once. Sequence state resets on each TCP connection.
