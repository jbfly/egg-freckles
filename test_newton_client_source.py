from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "examples/harness-client/Main.newt").read_text()
PROJECT = (ROOT / "examples/harness-client/harness-client.nprj").read_text()


def test_chat_transport_stays_non_blocking():
    assert "async: nil" not in SOURCE
    assert "endpoint:Input(" not in SOURCE
    # 6 chat (Bind, connect, handshake, hello, ACK, send) + 3 ink (Bind,
    # connect, POST). The ink POST folded in from ink-capture was synchronous
    # there and would have blocked the app for the whole vision call.
    assert SOURCE.count("async: true") == 9
    assert SOURCE.count("form: 'string") == 7
    assert "ViewQuitScript: func()" in SOURCE
    assert "self.endpoint:SetInputSpec(nil)" in SOURCE
    assert "self.inkEndpoint:SetInputSpec(nil)" in SOURCE


def test_a7_identity_and_mars_default_match():
    assert "kAppSymbol := '|HarnessClientA7:jbfly|;" in SOURCE
    assert 'kVersion := "2.4-a7";' in SOURCE
    assert 'kAppTitle := "Newton Chat A7 " & kVersion;' in SOURCE
    assert 'kAppLabel := "Chat A7";' in SOURCE
    assert "text: kAppLabel" in SOURCE
    assert 'name: "HarnessClientA7:jbfly"' in PROJECT
    assert "version: 15" in PROJECT
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


def test_the_note_rides_the_chat_path_not_an_http_endpoint():
    # Track F2: "Ask Note" reads the soup and calls the same Send() a typed
    # prompt calls, so a long note splits into MSGP parts instead of dying on
    # the host's 240-byte frame with "No answer: LENGTH".
    assert "AskNote: func()" in SOURCE
    assert "return :Send(note);" in SOURCE
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


def test_the_ink_encoder_does_not_add_the_view_origin():
    # E1 found Encode() adding the canvas origin to points GetPointsArray
    # already hands back as screen-global, shifting every host render +16,+54.
    # The origin now exists only in StrokeShape, which draws view-locally.
    assert "self.inkLeft" not in SOURCE
    assert "self.inkTop" not in SOURCE
    assert "local x := points[1];\n                local y := points[0];" in SOURCE
    assert "local nextX := points[index + 1];" in SOURCE
    assert "coords[index] := points[index + 1] - originLeft;" in SOURCE


def test_the_ink_overlay_shares_the_chat_link():
    # Dropping the chat link and re-grabbing one for the POST failed with
    # -16009; the ink endpoint rides the link the chat already holds.
    assert "if self.linkID then return :InkOpen();" in SOURCE
    # A slot named inkOpen would shadow the InkOpen method (-48200): symbols
    # are case-insensitive.
    assert "inkOpen:" not in SOURCE
    assert "self.inkPanel:Show();" in SOURCE
    assert "self.inkPanel:Hide();" in SOURCE
    # The reading joins the transcript instead of a private status line.
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
        ("Ask Note", "{left: 14, top: 388, right: 96, bottom: 410}"),
        ("Save Note", "{left: 104, top: 388, right: 196, bottom: 410}"),
        ("Ink", "{left: 238, top: 388, right: 290, bottom: 410}"),
    ):
        assert f"viewBounds: {bounds}" in SOURCE
        assert f'text: "{text}",' in SOURCE


def test_host_errors_remain_visible_in_transcript():
    assert 'self.responseText := "ERROR: " & SubStr(line, 15, star - 15);' in SOURCE
