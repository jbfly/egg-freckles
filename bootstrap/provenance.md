# Provenance for `nsbasic-bootstrap.bas`

## Sources and method

The program never existed as one file. It was recovered by applying the physical-device edits in chronological order to the last complete intended listing.

- **S** — Omnigent conversation `5a7949e17d464fcfb3183e1a10a593d5` (`newton bootstrap` / `Debug NS Basic loader`), exported read-only with `omnigent session export --id 5a7949e17d464fcfb3183e1a10a593d5 --output /tmp/nsbasic-session.jsonl`. The export contained 992 items. Citations give its stable item ID and export line.
- **F** — complete stale listing headed `=== nsb-final3.bas (latest intended) ===` in `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/f3f8e630-ab00-4c99-ae52-0890a41cee8f/tool-results/mcp-omnigent-sys_os_shell-1785254303922.txt`.
- **G** — another extract of the intended listing in `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/f3f8e630-ab00-4c99-ae52-0890a41cee8f/tool-results/call_ZQ8e5Nk31ckt9bglyU8yK2Tb.json`.
- **C** — candidate/on-device artifacts in `/home/jbfly/.claude/projects/-home-jbfly-git-newton-harness/e6db5283-27f7-4ee2-ad0e-6db5df31252f/tool-results/mcp-omnigent-sys_os_shell-1785296010008.txt`.

F/G predate the on-device corrections. S records the screen transcription, edits, emulator proof, successful transfer/install, and final house-LAN address. Later evidence wins.

## Per-line evidence

| Line | Status | Source and quoted snippet |
|---:|---|---|
| 10 | RECONSTRUCTED | **S item `e96fd75a515847f7b89a531245694b13` (line 88):** `svc() {label:"inet",type:'service,opCode:512,result:nil}`. **S item `570d6a34241e49d2a071fdcdc89f99fe` (104):** line 300 is byte-identical to line 10 and quotes the same body. F supplies `10 FUNCTION`. |
| 20 | VERBATIM | **S 88:** `ldata(id){arglist:[id],typeList:['struct,'ulong]}`. F confirms `20 FUNCTION` and the displayed spacing. |
| 30 | RECONSTRUCTED | **F:** `30 FUNCTION lid(id) {label:"ilid",type:'option,opCode:opSetRequired,form:'template,data:U:ldata(id)}`. **S 88:** `lid(id) {label:"ilid",…opCode:512,result:nil,form:'template,data:U:ldata(id)}`. |
| 40 | VERBATIM | **S 88:** `vdata() {arglist:[1],typeList:['struct,'ulong]}`. |
| 50 | RECONSTRUCTED | **F:** full `50 FUNCTION ver()` line. **S 88:** `ver() {label:"itsv",…opCode:512,result:nil,form:'template,data:U:vdata()}`. |
| 60 | VERBATIM | **S item `be9e1869e77e4d69a7d6671349016c26` (395):** `60 FUNCTION opts(id) BEGIN LOCAL a,b,c;a:=U:svc();b:=U:lid(id);c:=U:ver();[a,b,c] END`. The same item proves the inline predecessor failed before `Instantiate`. |
| 70 | VERBATIM | **S item `84911038a4e441a4899ede843046cc2e` (884):** `70 FUNCTION adata() {arglist:[192,168,1,11,18081],typelist:['struct,'byte,'byte,'byte,'byte,'short]}`. **S items `55fd8605a86f442bb52511439234406e` (969) and `3a4e4d767cf0467f8b8559f9bbd06c61` (993)** confirm this remains saved. |
| 80 | RECONSTRUCTED | **F:** full `80 FUNCTION addr()` line with stale opcode symbol. **S 88:** confirms final `opCode:512,result:nil,form:'template,data:U:adata()`. |
| 90 | RECONSTRUCTED | **F:** `90 FUNCTION suck(a) GetDefaultStore():SuckPackageFromBinary(a,nil)`. **S 88:** lines 90–130 “all match.” |
| 100 | RECONSTRUCTED | **F:** `100 FUNCTION install(d) begin ClearVBOCache(d);AddDelayedCall(U.suck,[d],1000) end`. **S 88:** lines 90–130 all match. |
| 110 | RECONSTRUCTED | **F:** `110 FUNCTION got(ep,d,t,o) if t and t.condition='byteCount and t.byteCount=15000 then U:install(d)`. **S 88:** lines 90–130 all match. |
| 120 | RECONSTRUCTED | **F:** `120 FUNCTION vbo() GetDefaultStore():NewVBO('package,15000)`. **S 88:** lines 90–130 all match. |
| 130 | RECONSTRUCTED | **F:** `130 FUNCTION term() {byteCount:15000}`. **S 88:** lines 90–130 all match. |
| 140 | VERBATIM | **S item `f53f8e5d63d546858a0a7754cb7876de` (100):** `0140 FUNCTION spec(v) {form:'binary,target:{data:v,offset:0},termination:U:term(),discardAfter:15000,InputScript:U.got}`. **S 104** repeats it. The later 20000 suggestion was not performed; the user pivoted in the next message. |
| 150 | VERBATIM | **S item `fbc85883983648c5b620c42f6058258f` (297):** `150 FUNCTION ep() {_proto:@383,_parent:U}`. **S item `be9e1869e77e4d69a7d6671349016c26` (395)** repeats it and records Stage 5 success. |
| 155 | RECONSTRUCTED | **S 100:** `0155 | err() call GetGlobalFn('InetGetExceptionError) with (CurrentException())`. The listing context establishes `FUNCTION`. |
| 160 | VERBATIM | **S item `d4a8bf2bf2fd407280d71a6764434370` (228):** `160 FUNCTION setup(id) try begin U.e:=U:ep();U.e:Instantiate(U.e,U:opts(id));U.e:Bind(nil,{async:nil,reqTimeout:10000});'ok end onexception |evt.ex| do U:err()`. **S item `796d58b608bf427f9243efb12e2630c5` (250)** says the photo showed `Instantiate`, `Bind`, and the exception handler exactly right. |
| 170 | RECONSTRUCTED | **F:** `170 FUNCTION conn() U.e:connect(U:addr(),{async:nil,reqTimeout:45000})`. **S 100:** lines 170–200 are clean. |
| 180 | RECONSTRUCTED | **F:** `180 FUNCTION listen() U.e:SetInputSpec(U:spec(U:vbo()))`. **S 100:** lines 170–200 are clean. |
| 190 | RECONSTRUCTED | **F:** `190 FUNCTION send() U.e:output("G",nil,{form:'string,async:nil,reqTimeout:10000})`. **S 100:** lines 170–200 are clean. **S item `99ea713568b748d099ea2b1d3148ee4d` (426):** sender received `b'G'`. |
| 200 | RECONSTRUCTED | **F:** `200 FUNCTION start(id) begin U:setup(id);U:conn();U:listen();U:send();true end`. **S 100:** lines 170–200 are clean. |
| 210 | RECONSTRUCTED | **S 100:** `grab(id,s,x) begin U.gid:=id;if x or U.e or s.linkStatus <> 'connected then nil else U:start(id) end`. |
| 220 | RECONSTRUCTED | **S 100:** `go() call GetGlobalFn('InetGrabLink) with (nil,U,'grab)`. |
| 230 | RECONSTRUCTED | **S 100:** `LET e=NIL`. |
| 240 | RECONSTRUCTED | **S 100:** `U:go()`. |
| 250 | VERBATIM | **S item `570d6a34241e49d2a071fdcdc89f99fe` (104):** `0250 | WAIT 60000`; it explicitly corrects F's stale `WAIT -1`. |
| 300 | RECONSTRUCTED | **S 104:** `svc() {label:"inet",type:'service,opCode:512,result:nil}` and “byte-identical to line 10”; the same item calls it a `FUNCTION` redefinition. |

## Deleted line 310

Line 310 is intentionally absent.

- **S item `d4a8bf2bf2fd407280d71a6764434370` (228):** “Delete line 310 by entering only: `310`.” It explains that the stale line overwrote corrected line 150 on every `RUN`.
- **S item `796d58b608bf427f9243efb12e2630c5` (250):** “Line 310 is deleted.”

The successful line-60 test happened after those edits. Restoring the obsolete `protoBasicEndpoint` line would break the recovered state.

## Hardware success evidence

**S item `99ea713568b748d099ea2b1d3148ee4d` (426):**

> `peer ('10.42.0.36', 33015)`
> `received b'G'`
> `sent 15000`

**S item `847a752defba4efda05709e5201fd0a6` (435):**

> “Yes. That's it — it installed.”
> “NS Basic opened a NIE endpoint, connected to `10.42.0.1:18081`, sent `G`, received all 15,000 bytes into a VBO, and `SuckPackageFromBinary` installed it.”

**S item `3a4e4d767cf0467f8b8559f9bbd06c61` (993):**

> “NS Basic bootstrap works end to end. Six packages installed over WiFi today.”

## Confidence conclusion

There are **no UNCERTAIN lines**. RECONSTRUCTED lines are not guesses: their full text exists in F/G and S later says the corresponding physical-device line or range matched while documenting every subsequent edit. Only line 310 was ordered deleted and later confirmed absent; no later line-300 deletion appears before the final saved state.
