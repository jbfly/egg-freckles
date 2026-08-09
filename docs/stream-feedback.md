# Chat stream feedback — prepare-only finding

Date: 2026-08-09

Branch: `task/stream-feedback`
Base: `5eee14be3b93590ee4832fc3794571662b8d286d`

## Bottom line

The port-6801 connection supports multiple host frames during one turn. The
server half was prepared and locally socket-proven as transient `STAT PROGRESS`
frames; M2 then added the matching client status render on
`task/m2-ef22-integration`. Final answer text still renders only when `PROMPT`
ends the turn.

## Protocol evidence

- The client arms a CRLF-terminated input callback and sends every line to
  `HandleLine` (`examples/harness-client/Main.newt:1090-1104`). It therefore
  receives every server write on the existing connection.
- `HandleLine` ACKs every valid frame (`examples/harness-client/Main.newt:1153-
  1166`). For `TEXT`, it only accumulates bytes in `responseText`; it does not
  redraw (`examples/harness-client/Main.newt:1201-1205`).
- Only `PROMPT` appends `Agent: <responseText>` and calls `ShowTranscript`
  (`examples/harness-client/Main.newt:1206-1210`). Therefore the answer is
  **final-only rendering**, not incremental display.
- The host already reads `codex exec --json` one line at a time and maps Newton
  MCP tool events to short labels (`server.py:524-554,594-622`). Native mode now
  sends each label as transient `STAT PROGRESS`, then sends the final answer as
  the existing `TEXT` frames followed by `PROMPT` (`server.py:827-850`).

## Local proof

A disposable local `codex` shim emitted delayed structured events while a plain
TCP client spoke the exact framed protocol and ACKed every server frame. The
transcript shows progress arriving before completion at distinct timestamps:

- writing source at +0.21 s;
- package build at +0.76 s;
- failed build detail at +1.31 s and retry at +1.86 s;
- emulator boot/install/launch/screenshot from +2.41 s through +4.06 s;
- final `TEXT` at +4.61 s, immediately followed by `PROMPT`.

Evidence: `runtime/evidence/stream-feedback-local.txt:7-17`; matching parsed
Codex events and generation boundaries are in
`runtime/evidence/stream-feedback-server.log`.

## Client step — completed in M2

`task/m2-ef22-integration` added the branch to `HandleLine` immediately before
the existing `STAT ERROR` / `TEXT` branches:

```newtonscript
else if BeginsWith(line, ":" & seqText & " STAT PROGRESS ") then
    :SetStatus(SubStr(line, 18, star - 18))
```

Do not append it to `responseText`; that keeps transient work out of the final
assistant message. The existing `TEXT` accumulation and `PROMPT` commit path
remain unchanged.

Isolated Einstein instance `m2ef23-0809a` painted `Writing source` and
`Building package` while its recorded `responseText` was empty, then committed
`LOCAL PROGRESS OK` only after `TEXT` + `PROMPT`. Evidence:
`runtime/evidence/m2-ef23-integration/progress-*-state.txt`, matching screenshots,
and `throwaway-progress-server.log`. Physical Newton validation remains
explicitly human-gated.
