import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "examples/harness-client/Main.newt").read_text()
PROJECT = (ROOT / "examples/harness-client/egg-freckles.nprj").read_text()
# The comments in that file quote the very API names some of these tests
# forbid ("never RemoveSlot", "does NOT RemoveFolder"), so the negative
# assertions run against the source with its // comments stripped.
CODE = re.sub(r"//[^\n]*", "", SOURCE)


def test_chat_transport_stays_non_blocking():
    assert "async: nil" not in SOURCE
    assert "endpoint:Input(" not in SOURCE
    # 6 chat (Bind, connect, handshake, hello, ACK, send) + 3 ink (Bind,
    # connect, POST) + 5 tools (Bind, connect, POLL, reply, re-POLL). Track L1
    # folded the tools client in without relaxing one timing rule.
    assert SOURCE.count("async: true") == 14
    assert SOURCE.count("form: 'string") == 12
    assert "ViewQuitScript: func()" in SOURCE
    assert "self.endpoint:SetInputSpec(nil)" in SOURCE
    assert "self.inkEndpoint:SetInputSpec(nil)" in SOURCE
    assert "self.toolEndpoint:SetInputSpec(nil)" in SOURCE


def test_ef8_identity_is_named_for_a_human_and_mars_default_matches():
    # Track L1: the round tag lives in the identity and the version string, and
    # nowhere the human reads. Extras shows "Egg Freckles", not "Chat A9 2.4".
    assert "kAppSymbol := '|EggFrecklesEF8:jbfly|;" in SOURCE
    assert 'kVersion := "1.0-ef8";' in SOURCE
    assert 'kAppTitle := "Egg Freckles " & kVersion;' in SOURCE
    assert 'kAppLabel := "Egg Freckles";' in SOURCE
    assert "text: kAppLabel" in SOURCE
    assert 'name: "EggFrecklesEF8:jbfly"' in PROJECT
    assert "version: 20" in PROJECT
    # No dev cruft left in anything the human reads. Comments still name the
    # old packages for provenance, so this checks the display strings only:
    # every literal that reaches the screen as a title, a label or a button.
    shown = [line.split('"')[1] for line in SOURCE.splitlines()
             if line.strip().startswith(("kAppTitle", "kAppLabel", "text: \""))]
    assert "Egg Freckles" in shown
    for label in shown:
        for cruft in ("Chat", "A9", "Harness", "R10P", "Newton"):
            assert cruft not in label, label
    assert "serverAddress: [10, 42, 0, 1]" in SOURCE
    assert "serverPort: 6801" in SOURCE
    assert "inkPort: 18081" in SOURCE


def test_long_prompts_go_out_as_msgp_parts():
    # The split sizes are the wire budget: 240 - len(":..*HH\r\n") - len(body head).
    assert "kFrameBytes := 227;" in SOURCE
    assert "kPartBytes := 220;" in SOURCE
    assert "kMaxPrompt := 8192;" in SOURCE
    assert 'return :SendBody(" MSG " & text);' in SOURCE
    assert '" MSGP " & :SeqText(self.partIndex) & " "' in SOURCE
    # Stop-and-wait: the next part only leaves on the previous part's ACK.
    assert "if (self.pendingParts <> nil) and (self.partIndex < Length(self.pendingParts)) then" in SOURCE
    assert 'if StrLen(text) > self.maxPrompt then return :SetStatus("Prompt too long");' in SOURCE


def test_a_text_only_note_rides_the_chat_path_not_an_http_endpoint():
    # Track F2/A9: a text-only note calls the same Send() a typed prompt calls,
    # so a long note splits into MSGP parts instead of dying on the host's
    # 240-byte frame with "No answer: LENGTH".
    assert "Ask: func()" in SOURCE
    assert "return :Send(text);" in SOURCE
    assert "POST /note" not in SOURCE
    # The two-step create is the only sanctioned write path (notes-bridge N12).
    assert "paperroll:MakeTextNote(self.lastReply, nil);" in SOURCE
    assert "paperroll:NewNote(note, nil, nil);" in SOURCE


def test_the_newest_note_is_read_without_the_off_by_one():
    # ResetToEnd lands *on* the last entry and returns it; note-export's
    # `ResetToEnd(); Prev()` therefore read the second-newest note. Measured in
    # the F2 round: reset=3 entry=3 while Prev() gave 2.
    assert "local entry := cursor:ResetToEnd();" in SOURCE
    assert "cursor:ResetToEnd();\n        local entry := cursor:Prev();" not in SOURCE


def test_the_newest_note_is_the_last_one_the_store_allocated():
    # Track L1. The device's clock had been set to 2008 and corrected, so every
    # date on it lies: a note written while it was wrong sorts to the FRONT of
    # the timeStamp index, where a scan running back from the end never sees it.
    # That is why a fresh cat drawing lost to months-old D&D notes twice.
    # EntryUniqueID comes off a per-soup counter that never consults the clock
    # (soup:GetNextUid, refs/NewtonProgrammerRef20.txt:33348), and _uniqueID is
    # a real index on this ROM. Proven side by side on the same 25-note soup in
    # runtime/evidence/efround-ordering.txt: the old rule answered id=23
    # "EF dnd session 18", this one answers id=24 "EF cat drawing page".
    assert "FindNewest: func()" in SOURCE
    assert "kScanLimit := 16;" in SOURCE
    assert "scanLimit: kScanLimit," in SOURCE
    assert "try cursor := soup:Query({indexPath: '_uniqueID})" in SOURCE
    assert "local bestUid := EntryUniqueID(entry);" in SOURCE
    assert "while (entry <> nil) and (scanned < self.scanLimit) do" in SOURCE
    # Highest ID wins; EntryModTime only breaks a cross-store ID tie.
    assert "or (uid > bestUid)" in SOURCE
    assert "((uid = bestUid) and (stamp <> nil)" in SOURCE
    # `mod` is the modulo operator; a local named that is a syntax error.
    assert "local mod :=" not in SOURCE
    # Ask is the only caller; the timeStamp-ordered reads are gone by name.
    assert "ReadNote: func()" not in SOURCE
    assert "AskNote: func()" not in SOURCE
    # Ask is the ONLY caller now. The third hardware test proved this rule
    # cannot be used to find a note you just wrote (see the filing test below),
    # so :FileReply and :SaveNote no longer call it at all.
    assert CODE.count(":FindNewest()") == 1
    assert "Ask: func()" in SOURCE
    # Save Note names the entry it created, off the frame NewNote adopted.
    assert 'return :SetStatus("Saved note id=" & EntryUniqueID(note));' in SOURCE


def test_the_tools_client_lives_inside_this_package_now():
    # Track L1: one install, one app, one NIE link. The separate
    # HarnessToolsR10P package is deleted, which also removes the second NIE
    # client that raised the cosmetic Communications alerts on hardware.
    for op in ("ping", "front_app", "battery", "store_info", "pkg_list",
               "note_list", "get_note", "note_probe"):
        assert f'StrEqual(op, "{op}")' in SOURCE
    assert "ToolDispatch: func(line)" in SOURCE
    assert 'self.toolEndpoint:Output("POLL\\r\\n", nil, {' in SOURCE
    # The watchdog stays above the host's 3 s heartbeat cadence.
    assert "if self.toolMisses > 2 then :ToolRetry();" in SOURCE
    assert "view:ToolWatch() onexception |evt.ex| do nil, [self], 4000);" in SOURCE
    # EF6: and there is exactly ONE watchdog chain. Starting a fresh one per
    # connect made toolMisses climb once per chain per 4 s and turned the
    # channel into a reconnect storm -- 15 reconnects in 60 s, measured against
    # the host log; 0 with the guard.
    assert "toolWatching: nil," in SOURCE
    assert "if not self.toolWatching then" in SOURCE
    assert "self.toolWatching := nil;" in SOURCE
    # Names are prefixed so nothing collides case-insensitively with the chat
    # side's Stop/Bound/Connected/ArmInput/Grabbed.
    for name in ("ToolStart", "ToolGrabbed", "ToolBound", "ToolConnected",
                 "ToolPoll", "ToolArmInput", "ToolReply", "ToolStop"):
        assert f"{name}: func" in SOURCE
    # One link, three connections: nobody releases it while another holds it.
    assert "ReleaseLink: func()" in SOURCE
    assert "if self.endpoint or self.inkEndpoint or self.toolEndpoint then return nil;" in SOURCE
    assert "if self.linkID then return :OpenSession();" in SOURCE
    assert "if self.linkID then return :ToolOpen();" in SOURCE


def test_the_tools_poll_belongs_to_the_package_not_the_window():
    # The fifth hardware test: an agent-driven install failed with "Newton not
    # responding to pings" because the human had the window closed, and the poll
    # only ran between Boot and ViewQuitScript. It is owned by the same
    # install-hook agent as "Send to AI" now.
    boot = SOURCE.index("Boot: func()")
    quit_script = SOURCE.index("ViewQuitScript: func()")
    assert ":ToolStart()" not in SOURCE[boot:SOURCE.index("Wire: func()", boot)]
    assert ":ToolStop();" not in SOURCE[quit_script:boot]
    # Started from the hook, on the agent frame, by a delayed call -- and a
    # delayed call with a FRAME receiver is safe where one with a view receiver
    # is not (the L1 -48809 trap), because this frame has no view to close.
    assert "who:ToolStart() onexception |evt.ex| do nil,\n            [agent], 3000);" in SOURCE
    # Exactly one poll instance: a package replacement retires the old agent's
    # poll before the new agent starts one.
    assert "FindAgent: func(paperroll)" in SOURCE
    assert "local previous := :FindAgent(paperroll);" in SOURCE
    assert "previous.toolStopping := true;" in SOURCE
    # The agent owns its own copies of every tools slot, never the template's.
    for slot in ("toolEndpoint", "toolReady", "toolStopping", "toolMisses",
                 "toolID", "toolOutcome", "toolValue", "toolWatching",
                 "toolBindRetried"):
        assert f"agent.{slot} := " in SOURCE
    assert "agent.ToolGrabbed := self.ToolGrabbed;" in SOURCE
    # Removing the package is what stops it now -- the flag first, because it is
    # a slot write that cannot throw once the package's code is going away.
    remove = SOURCE.index("RemoveScript: func(frame)")
    assert "item.agent.toolStopping := true;" in SOURCE[remove:]
    assert "try item.agent:ToolStop()" in SOURCE[remove:]


def test_every_nie_callback_is_armored_against_throwing_into_the_fsm():
    # The fourth hardware test photographed the MP2000 showing an
    # `evt.ex.fr.intrp` / -48803 raised inside InetManagerFSM's RemoveLinkClient
    # event, then `Bind error -60047`. -48803 is "wrong number of arguments ...
    # when a callback can't be called"; an exception escaping one of OUR
    # callbacks lands inside NIE's own state machine and reaches the human as a
    # modal alert. So nothing of ours may throw out of a callback.
    #
    # Every CompletionScript, InputScript and ExceptionHandler body opens a try.
    for kind in ("CompletionScript: func(endpoint, options, result)",
                 "InputScript: func(endpoint, data, terminator, options)",
                 "ExceptionHandler: func(error)"):
        bodies = re.findall(re.escape(kind) + r"\s*\n?\s*try\b", SOURCE)
        assert len(bodies) == SOURCE.count(kind), kind
    # The three link callbacks NIE invokes by symbol, likewise.
    for name in ("Grabbed", "InkGrabbed", "ToolGrabbed"):
        at = SOURCE.index(f"{name}: func(id, state, error)")
        assert SOURCE[at:at + 220].count("try") >= 1, name
    # And InetReleaseLink itself is guarded: RemoveLinkClient is exactly what it
    # drives, and an exception here would leave via ViewQuitScript.
    assert ("try call GetGlobalFn('InetReleaseLink) with (self.linkID, self, 'Released)\n"
            "            onexception |evt.ex| do nil;") in SOURCE


def test_a_bind_failure_gets_one_retry_before_it_is_surfaced():
    # `Bind error -60047` in the fourth hardware test was the next connection
    # failing against a link that was still half torn down -- the failure a
    # short wait fixes. One retry, five seconds, then the error is real.
    for slot in ("bindRetried", "inkBindRetried", "toolBindRetried"):
        assert f"{slot}: nil," in SOURCE
    assert "BindFailed: func(message)" in SOURCE
    assert "if self.bindRetried then return :Failed(message);" in SOURCE
    assert "InkBindFailed: func(message)" in SOURCE
    assert "if self.inkBindRetried then return :InkFailed(message);" in SOURCE
    assert "ToolBindFailed: func()" in SOURCE
    assert "if self.toolBindRetried then return :ToolRetry();" in SOURCE
    # Each Bind completion routes to the retry, not straight to the failure.
    assert 'self._parent:BindFailed("Bind error " & result)' in SOURCE
    assert 'self._parent:InkBindFailed("Ink bind error " & result)' in SOURCE
    assert "self._parent:ToolBindFailed()" in SOURCE
    # Cleared on success, so the retry is per connection attempt and not once
    # per lifetime.
    assert "self.bindRetried := nil;" in SOURCE
    assert "self.inkBindRetried := nil;" in SOURCE
    assert "self.toolBindRetried := nil;" in SOURCE
    # The five-second waits themselves.
    assert "view:Connect() onexception |evt.ex| do nil,\n            [self], 5000);" in SOURCE
    assert "view:InkRebind() onexception |evt.ex| do nil,\n            [self], 5000);" in SOURCE
    assert "who:ToolResume() onexception |evt.ex| do nil,\n            [self], 5000);" in SOURCE


def test_every_endpoint_catches_its_own_exceptions():
    # "If no ExceptionHandler method is specified, the exception is passed up
    # the handler chain. Exceptions that are not caught are displayed as warning
    # messages to the user" (refs/NewtonProgrammerRef20.txt:57321-57323) -- that
    # warning is the modal Communications slip the hardware test complained
    # about. Three endpoints, three handlers.
    assert SOURCE.count("ExceptionHandler: func(error)") == 3
    # And a delayed call that lands on a closed view -- or on an agent whose
    # package has been removed -- raises -48809; every one of them opens with a
    # try, which is what makes closing the window silent.
    guarded = re.findall(r"AddDelayedCall\(func\([^)]*\)\s*\n?\s*try ", SOURCE)
    assert len(guarded) == SOURCE.count("AddDelayedCall(")


def test_the_window_is_centred_on_whatever_screen_the_rom_reports():
    # A9 hardcoded the box. The second hardware test said it loads off-centre,
    # and a constant can only be centred on the screen it was measured against.
    assert "kWinWidth := 304;" in SOURCE
    assert "kWinHeight := 428;" in SOURCE
    assert "ViewSetupFormScript: func()" in SOURCE
    assert "CenterBounds: func()" in SOURCE
    assert "try box := GetRoot():LocalBox()" in SOURCE
    assert "local left := box.left + ((wide - self.winWidth) div 2);" in SOURCE
    assert "local top := box.top + ((high - self.winHeight) div 2);" in SOURCE


def test_one_ask_button_classifies_the_note_instead_of_offering_two():
    # Still one button with one meaning -- send the newest note, whatever kind
    # it is -- but labelled for what it acts on. Track L1: the bare verbs did
    # not say what they applied to. Never an "Ask Note"/"Ask Sketch" pair.
    assert 'text: "Ask Note",' in SOURCE
    assert "buttonClickScript: func() self:Parent():Ask()," in SOURCE
    assert 'text: "Ask Sketch",' not in SOURCE
    # The classification ORDER is load-bearing: every sketch item's _proto is a
    # clPolygonView template with its own empty `points` binary, so testing
    # points/ink before viewStationery reports every stroke as an empty shape.
    order = SOURCE.index("CollectNote: func(data)")
    para = SOURCE.index("item.viewStationery = 'para", order)
    poly = SOURCE.index("item.viewStationery = 'poly", order)
    pict = SOURCE.index("item.viewStationery = 'pict", order)
    ink = SOURCE.index("ClassOf(item.ink) = 'ink2", order)
    assert para < poly < pict < ink


def test_the_two_converters_disagree_and_both_are_pinned():
    # 'poly points are RELATIVE to viewBounds and ordered x,y; 'ink2 points are
    # ABSOLUTE in the note's space and ordered y,x. Getting either backwards
    # produces plausible-looking wrong geometry.
    assert "AddArraySlot(points, array[index] + box.left);" in SOURCE
    assert "AddArraySlot(points, array[index + 1] + box.top);" in SOURCE
    assert "local bundle := ExpandInk(item, 0);" in SOURCE
    assert "local strokes := CountStrokes(bundle);" in SOURCE
    assert "GetStrokePointsArray(GetStroke(bundle, index), 0);" in SOURCE
    # SwapPairs is the y,x -> x,y conversion, and the only one.
    assert "points[index] := flat[index + 1];" in SOURCE
    assert "points[index + 1] := flat[index];" in SOURCE
    # Ink Text hides inside a paragraph: no data item, an 'inkWord in styles.
    assert "InkConvert(style, 'ink2)" in SOURCE
    assert "GetInkWordInfo(style)" in SOURCE


def test_the_ink_text_placeholder_is_stripped_not_prompted():
    # A paragraph holding ink words carries character 63233 (0xF701) once per
    # word. A7 put it straight into the prompt.
    assert "kInkPlaceholder := 63233;" in SOURCE
    assert "placeholder: kInkPlaceholder," in SOURCE
    assert "if code = self.placeholder then nil" in SOURCE


def test_the_note_origin_comes_off_and_every_point_is_clamped():
    # Sketch points are absolute in the paper roll's own space, not the
    # screen's (a uniform 0,-36 for the probe note), and /ink rejects any point
    # outside 320x480. The drawn items' bounding-box origin comes off here.
    assert "local originLeft := self.askLeft;" in SOURCE
    assert ":ClampAt(points[index] - originLeft, 319)" in SOURCE
    assert ":ClampAt(points[index + 1] - originTop, 479)" in SOURCE
    assert "local at := Floor(value);" in SOURCE


def test_ink_is_decimated_never_truncated():
    # The fifth hardware test: a handwritten sentence arrived at the host as its
    # first three words, because A9's kMaxPoints := 400 was spent by whichever
    # strokes were read first and :AddStroke then REFUSED every later stroke.
    # EF6 keeps every stroke and thins the points inside it.
    #
    # The budget is arithmetic against the host's 16 KiB /ink body cap
    # (pkg_publisher.py) at a pessimistic 8 bytes per point; measured on the
    # wire it is 4.27 (runtime/evidence/ef6round-ink-decimation.txt).
    assert "kMaxPoints := 1600;" in SOURCE
    assert "kMaxItems := 256;" in SOURCE
    assert "kMaxRaw := 12000;" in SOURCE
    assert "maxRaw: kMaxRaw," in SOURCE
    # The refusal is gone. Nothing anywhere may drop a stroke for being late.
    assert "if (self.askPoints + count) > self.maxPoints then" not in CODE
    assert "askTruncated" not in SOURCE
    # One linear pass, integer stride, first and last point of every stroke kept.
    assert "ThinInk: func()" in SOURCE
    assert "local stride := (total div target) + 1;" in SOURCE
    assert "local target := self.maxPoints - (2 * count);" in SOURCE
    assert "if (since >= stride) or (at = size - 1) then" in SOURCE
    # Every encode thins first, so both callers inherit it.
    encode = SOURCE.index("EncodeInk: func(hint, mode)")
    assert SOURCE.index(":ThinInk();", encode) < SOURCE.index("local body :=", encode)
    # And the human is told, in the transcript and in the reply note.
    assert 'if self.askThinned then :AppendLine("Note: ink thinned to fit ("' in SOURCE
    assert '& self.askRaw & " points sent as " & self.askPoints & ")");' in SOURCE
    assert 'self.aiLabel := self.aiLabel & " (ink thinned to fit)";' in SOURCE
    # The count reported is the true drawn count, not a survivor count.
    assert "local strokes := Length(self.askStrokes);" in SOURCE
    assert ':SetStatus("Sending " & strokes & " strokes");' in SOURCE


def test_nsi1_carries_the_tapped_mode_without_changing_its_tag():
    # M and H are optional, so an older client body still parses as Ask.
    assert r'local body := "NSI1 320 480 " & Length(self.askStrokes) & "\r\n";' in SOURCE
    assert r'body := body & "M text\r\n"' in SOURCE
    assert r'body := body & "M ask\r\n"' in SOURCE
    assert r'body := body & "H " & hint & "\r\n";' in SOURCE
    assert "kHintBytes := 200;" in SOURCE
    assert "if StrLen(hint) > self.hintBytes then hint := SubStr(hint, 0, self.hintBytes);" in SOURCE


def test_the_capture_canvas_is_gone_multi_stroke_defect_and_all():
    # The InkPad-derived canvas dropped all but the first stroke when drawing
    # freely (hardware 2026-08-03, finding 5). It is deleted, not fixed: stock
    # Notes keeps every stroke, including ones that physically cross.
    # Slot-declaration form, so the NSI1 grammar comment can still name the
    # header field <strokeCount> without tripping this.
    for slot in ("inkPanel", "inkCanvas", "inkStatusView", "strokeCount:",
                 "self.shapes", "vStrokesAllowed"):
        assert slot not in SOURCE
    for method in ("ShowInk: func()", "HideInk: func()", "InkStatus: func(",
                   "StrokeText: func()", "StrokeShape: func(", "Repaint: func()",
                   "CountStroke: func(", "InkUndo: func()", "InkClear: func()",
                   "ViewStrokeScript: func(unit)", "ViewDrawScript: func()"):
        assert method not in SOURCE
    assert "MakePolygon" not in SOURCE
    assert "GetPointsArray(unit)" not in SOURCE
    # The transport it sat on survives and Ask reuses it unchanged.
    assert "SendInk: func(body, strokes)" in SOURCE
    assert "POST /ink HTTP/1.0" in SOURCE


def test_the_ink_overlay_shares_the_chat_link():
    # Dropping the chat link and re-grabbing one for the POST failed with
    # -16009; the ink endpoint rides the link the chat already holds.
    assert "if self.linkID then return :InkOpen();" in SOURCE
    # A slot named inkOpen would shadow the InkOpen method (-48200): symbols
    # are case-insensitive.
    assert "inkOpen:" not in SOURCE
    # The reading joins the transcript instead of a private status line -- and
    # with the overlay gone, that status line no longer exists at all.
    assert ':AppendLine("Ink: " & reading);' in SOURCE


def test_two_notes_actions_share_one_agent_and_route_their_own_modes():
    assert 'kTextMenuTitle := "Convert to Text";' in SOURCE
    assert 'kAskMenuTitle := "Ask AI";' in SOURCE
    assert "InstallScript: func(partFrame)" in SOURCE
    assert "paperroll.routeScripts := :NotesRebuild(paperroll, textEntry, askEntry);" in SOURCE
    assert "aiMode: 'text," in SOURCE
    assert "aiMode: 'ask," in SOURCE
    assert "RouteScript: self.NotesTextRoute," in SOURCE
    assert "RouteScript: self.NotesAskRoute," in SOURCE
    assert "NotesTextRoute: func(target, targetView)" in SOURCE
    assert "NotesAskRoute: func(target, targetView)" in SOURCE
    assert "return item.agent:Route(target, targetView, 'text);" in SOURCE
    assert "return item.agent:Route(target, targetView, 'ask);" in SOURCE
    # One heap agent owns both entries and therefore exactly one tools poll.
    assert SOURCE.count("local agent := {_proto: self};") == 1
    assert SOURCE.count("who:ToolStart() onexception") == 1
    for closure in ("func(target, targetView) agent:", "func() agent.", "func() kAppSymbol"):
        assert closure not in SOURCE
    assert "try form:NotesHook(0, 'window) onexception |evt.ex| do nil;" in SOURCE
    assert "if :NotesHooked(paperroll) and (via <> 'install) then return nil;" in SOURCE


def test_offline_send_stashes_once_and_resends_from_ready():
    assert "pendingPrompt: nil," in SOURCE
    assert 'return :SetStatus("Connecting, will send...");' in SOURCE
    assert "self.pendingPrompt := prompt;" in SOURCE
    assert "local prompt := self.pendingPrompt;" in SOURCE
    assert "self.pendingPrompt := nil;" in SOURCE
    ready = SOURCE.index("local prompt := self.pendingPrompt;")
    assert SOURCE.index("self.pendingPrompt := nil;", ready) < SOURCE.index(
        ":Send(prompt);", ready)


def test_install_sweeps_stale_ai_entries_but_uninstall_stays_scoped():
    assert "if not (IsFrame(item) and (item.aiHook <> nil)) then" in SOURCE
    assert "if IsFrame(item) and (item.aiHook = frame.app) then" in SOURCE


def test_uninstall_removes_our_entry_and_never_the_whole_array():
    # RemoveSlot restores the ROM array exactly, discarding any entry a
    # different package appended after us (design section 1, evidence section 6).
    assert "RemoveSlot(" not in CODE
    assert "RemoveScript: func(frame)" in SOURCE
    # EF6 turned the one-liner into a block, because removing the package is now
    # also what stops the package-level tools poll, but the rule is unchanged:
    # our marked entry is dropped and every other entry is copied through.
    assert "if IsFrame(item) and (item.aiHook = frame.app) then" in SOURCE
    assert "dropped := true;" in SOURCE
    assert "else AddArraySlot(rebuilt, item);" in SOURCE
    assert "if dropped then paperroll.routeScripts := rebuilt;" in SOURCE
    # RemoveScript runs on every deactivation, package replacement included, so
    # it must not delete the user's filed answers along with the folder.
    assert "RemoveFolder(" not in CODE
    assert "RemoveAppFolders(" not in CODE


def test_the_route_script_reuses_the_ask_extractor_and_the_ask_transport():
    # The agent's proto is the client's own base template: one extractor, one
    # ink transport, no second copy to keep in step.
    assert "local agent := {_proto: self};" in SOURCE
    assert "foreach tag, value in self.noteAgent do agent.(tag) := value;" in SOURCE
    # Same POST the Ask button makes, and the same 150 s watchdog with it.
    assert ":SendInk(body, strokes);" in SOURCE
    # It must not read a live window's link through the proto chain.
    assert "agent.linkID := nil;" in SOURCE
    # A blank page's data is nil; Length(nil) raises -48410/-48418.
    assert "if not IsArray(data) then return nil;" in SOURCE
    # Multi-select from the overview: first entry, no special case.
    assert "local cursor := GetTargetCursor(target, nil);" in SOURCE
    # A note the harness wrote itself has an item with no class slot at all.
    assert "else if item.text then :CollectPara(item);" in SOURCE


def test_the_reply_comes_back_as_a_note_filed_in_the_ai_folder():
    assert 'kAIFolder := "AI";' in SOURCE
    assert "try tag := AddFolder(self.aiFolder, 'paperroll)" in SOURCE
    # THE THIRD HARDWARE TEST'S BUG. EF4 wrote the note and then went looking
    # for it again with :FindNewest() -- the highest _uniqueID in the Notes
    # UNION soup -- and filed whatever came back. `_uniqueID` is allocated per
    # member soup (measured on the ROM: two soups on one store both start at 0,
    # runtime/evidence/effix-filing-bug.txt), so on the MP2000's multi-store
    # Notes soup that named the wrong entry: the reply arrived Unfiled and the
    # user's source note was filed into AI. The entry is now held, never
    # searched for, and the label goes in with the data.
    assert "local note := paperroll:MakeTextNote(body, nil);" in SOURCE
    assert "if tag <> nil then note.labels := tag;" in SOURCE
    assert "paperroll:NewNote(note, nil, nil);" in SOURCE
    assert "if (tag <> nil) and IsSoupEntry(note) then" in SOURCE
    assert "try EntryChangeXmit(note, nil) onexception |evt.ex| do nil;" in SOURCE
    # The source note must never be written to on this path.
    assert "entry.labels := tag;" not in CODE
    assert "EntryChangeXmit(entry, nil);" not in CODE
    # Exactly one note per tap: a failure has to say so somewhere, and this is
    # the only surface a menu user has.
    assert 'try :FileReply("(not sent) " & why) onexception |evt.ex| do nil;' in SOURCE


def test_both_icons_are_one_drawn_bitmap_built_at_package_time():
    # The human asked for an icon for Extras and one for the menu entry, and
    # for a ROM icon to be reused if one fitted. The only icons reachable from
    # the hook are Duplicate and Delete (runtime/evidence/effix-icons.txt), so
    # this is drawn -- but the 16-byte `bits` header is copied verbatim off the
    # ROM's own 20x14 Duplicate icon, which is why no part of the binary layout
    # had to be guessed. tntk evaluates this file to build the package, so
    # MakeBinaryFromHex runs on the host and the binary is what ships.
    assert "kIconBits := MakeBinaryFromHex(" in SOURCE
    assert "\"00000000000400fd00fd008d010b00a1\"" in SOURCE
    assert ("kAppIcon := {bits: kIconBits, "
            "bounds: {top: 0, left: 0, bottom: 14, right: 20}};") in SOURCE
    # 16 header bytes + 14 rows x 4 rowBytes = 72 bytes, as 144 hex characters.
    hexes = re.findall(r'"([0-9a-f]{16,32})"', SOURCE)
    assert sum(len(h) for h in hexes) == 144
    # Used twice: the Extras drawer reads the part frame's slot, the picker
    # reads the route entry's. A top-level constant may not be read from inside
    # a function body (tntk segfaults -- the twenty-second finding), so the
    # menu entry goes through a template slot.
    assert "icon: kAppIcon," in SOURCE
    assert "menuIcon: kAppIcon," in SOURCE
    assert SOURCE.count("icon: self.menuIcon,") == 2
    assert "icon: nil," not in SOURCE


def test_the_line_scan_avoids_strpos_with_a_carriage_return():
    # StrPos(text, Chr(13), 0) raises -48802 on this ROM; see the F1 round.
    assert "FindBreak: func(text, from)" in SOURCE
    assert "if Ord(text[index]) = 13 then return index;" in SOURCE
    assert "self.newline, 0)" not in SOURCE


def test_a_nak_ends_the_turn_visibly():
    assert 'if BeginsWith(line, "NAK ") then' in SOURCE
    assert "return :SetStatus(line);" in SOURCE


def test_prompt_is_a_large_multiline_handwriting_area():
    assert "else if top = 236 then self.promptView := child" in SOURCE
    assert "viewBounds: {left: 14, top: 236, right: 290, bottom: 354}" in SOURCE
    assert "viewJustify: vjLeftH" in SOURCE
    assert "viewLineSpacing: 24" in SOURCE
    assert "viewBounds: {left: 178, top: 360, right: 230, bottom: 382}" in SOURCE
    assert "viewBounds: {left: 238, top: 360, right: 290, bottom: 382}" in SOURCE


def test_the_second_control_row_carries_the_panel_buttons():
    for text, bounds in (
        ("Ask Note", "{left: 14, top: 388, right: 110, bottom: 410}"),
        ("Save Note", "{left: 118, top: 388, right: 214, bottom: 410}"),
    ):
        assert f"viewBounds: {bounds}" in SOURCE
        assert f'text: "{text}",' in SOURCE


def test_the_transcript_is_windowed_by_rendered_rows_not_characters():
    # The defect the first hardware test found: A7 fed the pane the last 640
    # *characters*, but the pane can only draw twelve *rows*, so a short-line
    # reply (/help, /status) ran off the bottom and was unreachable. A8 wraps
    # the transcript onto the row grid itself and shows one window of it.
    assert "kRowChars := 38;" in SOURCE
    assert "kVisibleRows := 12;" in SOURCE
    assert "kScrollOverlap := 2;" in SOURCE
    assert "WrapRows: func()" in SOURCE
    assert "local text := :VisibleText();" in SOURCE
    # Fixing the line height is what makes a row count a pixel count.
    assert "viewLineSpacing: 14," in SOURCE
    # The character window is gone, name and all.
    assert "kTranscriptTail" not in SOURCE
    assert "TranscriptTail: func()" not in SOURCE
    assert "tailBytes" not in SOURCE
    # A new line always snaps the window back to the live bottom.
    assert "self.scrollRow := 0;" in SOURCE


def test_the_scroll_buttons_page_the_transcript_window():
    # The divider gives up its right half so the buttons cost no transcript
    # height and no new view machinery.
    assert "viewBounds: {left: 0, top: 214, right: 198, bottom: 232}" in SOURCE
    for text, bounds in (
        ("Up", "{left: 206, top: 210, right: 246, bottom: 232}"),
        ("Dn", "{left: 250, top: 210, right: 290, bottom: 232}"),
    ):
        assert f"viewBounds: {bounds}" in SOURCE
        assert f'text: "{text}",' in SOURCE
    assert "ScrollUp: func() :ScrollBy(self.visibleRows - self.scrollOverlap)," in SOURCE
    assert "ScrollDown: func() :ScrollBy(self.scrollOverlap - self.visibleRows)," in SOURCE
    # The ROM's own scroll arrows cannot reach this window, and Track L1 tried
    # it rather than assuming: viewFlags 580 went in, the live window read 581,
    # the handlers worked when called directly, and tapping the arrow changed
    # nothing at all. Scroll routing excludes floating views by definition
    # (refs/NewtonProgrammerRef20.txt:4510-4512), so the flag is reverted and
    # the handlers are gone rather than shipped dead.
    assert "viewFlags:" not in SOURCE
    assert "ViewScrollUpScript: func()" not in SOURCE
    assert "ViewScrollDownScript: func()" not in SOURCE
    assert "ViewOverviewScript: func()" not in SOURCE


def test_host_errors_remain_visible_in_transcript():
    assert 'self.responseText := "ERROR: " & SubStr(line, 15, star - 15);' in SOURCE
