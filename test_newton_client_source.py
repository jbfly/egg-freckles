from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "examples/harness-client/Main.newt").read_text()
PROJECT = (ROOT / "examples/harness-client/harness-client.nprj").read_text()


def test_chat_transport_stays_non_blocking():
    assert "async: nil" not in SOURCE
    assert "endpoint:Input(" not in SOURCE
    # 6 chat (Bind, connect, handshake, hello, ACK, send) + 3 ink (Bind,
    # connect, POST). A9 deleted the capture canvas but kept every one of the
    # ink endpoint's calls: Ask reuses that transport unchanged.
    assert SOURCE.count("async: true") == 9
    assert SOURCE.count("form: 'string") == 7
    assert "ViewQuitScript: func()" in SOURCE
    assert "self.endpoint:SetInputSpec(nil)" in SOURCE
    assert "self.inkEndpoint:SetInputSpec(nil)" in SOURCE


def test_a9_identity_and_mars_default_match():
    assert "kAppSymbol := '|HarnessClientA9:jbfly|;" in SOURCE
    assert 'kVersion := "2.4-a9";' in SOURCE
    assert 'kAppTitle := "Newton Chat A9 " & kVersion;' in SOURCE
    assert 'kAppLabel := "Chat A9";' in SOURCE
    assert "text: kAppLabel" in SOURCE
    assert 'name: "HarnessClientA9:jbfly"' in PROJECT
    assert "version: 17" in PROJECT
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


def test_the_newest_note_is_the_most_recently_modified_one():
    # The hardware bug: the human drew a cat, tapped Ask, and got an answer
    # about an older D&D text note. timeStamp is CREATION time and drawing on
    # an existing page only moves EntryModTime (measured nine minutes apart on
    # the probe note). There is no _modTime index to order by -- that query
    # raises evt.ex.fr.store -- so the comparison is done by hand, and bounded
    # so the event loop cannot starve.
    assert "FindNewest: func()" in SOURCE
    assert "kScanLimit := 16;" in SOURCE
    assert "scanLimit: kScanLimit," in SOURCE
    assert "local bestMod := EntryModTime(entry);" in SOURCE
    assert "while (entry <> nil) and (scanned < self.scanLimit) do" in SOURCE
    # `mod` is the modulo operator; a local named that is a syntax error.
    assert "local mod :=" not in SOURCE
    assert "local stamp := EntryModTime(entry);" in SOURCE
    # Ask is the only caller; the timeStamp-ordered read is gone by name.
    assert "ReadNote: func()" not in SOURCE
    assert "AskNote: func()" not in SOURCE


def test_one_ask_button_classifies_the_note_instead_of_offering_two():
    # One button, one meaning: send the newest note, whatever kind it is.
    # Never an "Ask Note"/"Ask Sketch" pair, never a silent skip.
    assert 'text: "Ask",' in SOURCE
    assert "buttonClickScript: func() self:Parent():Ask()," in SOURCE
    assert 'text: "Ask Note",' not in SOURCE
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
    # Bounded work: an unbounded string is never built on the Newton.
    assert "kMaxPoints := 400;" in SOURCE
    assert "kMaxItems := 64;" in SOURCE
    assert "if (self.askPoints + count) > self.maxPoints then" in SOURCE


def test_nsi1_grows_one_optional_hint_line_and_keeps_its_tag():
    # The mixed-note rule: ONE request carrying both. The header's four fields
    # do not change and H is optional, because the physical MP2000 still runs
    # an older client whose bodies have no H line.
    assert r'local body := "NSI1 320 480 " & Length(self.askStrokes) & "\r\n";' in SOURCE
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
        ("Ask", "{left: 14, top: 388, right: 96, bottom: 410}"),
        ("Save Note", "{left: 104, top: 388, right: 196, bottom: 410}"),
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
    # The ROM's own scroll arrows reach only a view with vApplication set
    # (refs/NewtonProgrammerRef20.txt:3193-3199); this float window measured
    # viewFlags 576 through ns_eval, so wiring them would be dead code.
    assert "ViewScrollUpScript: func()" not in SOURCE
    assert "ViewScrollDownScript: func()" not in SOURCE


def test_host_errors_remain_visible_in_transcript():
    assert 'self.responseText := "ERROR: " & SubStr(line, 15, star - 15);' in SOURCE
