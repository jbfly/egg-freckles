from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / "examples/harness-client/Main.newt").read_text()
PROJECT = (ROOT / "examples/harness-client/harness-client.nprj").read_text()


def test_chat_transport_stays_non_blocking():
    assert "async: nil" not in SOURCE
    assert "endpoint:Input(" not in SOURCE
    assert SOURCE.count("async: true") == 6
    assert SOURCE.count("form: 'string") == 5
    assert "ViewQuitScript: func()" in SOURCE
    assert "self.endpoint:SetInputSpec(nil)" in SOURCE


def test_a4_identity_and_mars_default_match():
    assert "kAppSymbol := '|HarnessClientA4:jbfly|;" in SOURCE
    assert 'kVersion := "2.4-a4";' in SOURCE
    assert 'kAppTitle := "Newton Chat A4 " & kVersion;' in SOURCE
    assert 'kAppLabel := "Chat A4";' in SOURCE
    assert "text: kAppLabel" in SOURCE
    assert 'name: "HarnessClientA4:jbfly"' in PROJECT
    assert "version: 14" in PROJECT
    assert "serverAddress: [10, 42, 0, 1]" in SOURCE
    assert "serverPort: 6801" in SOURCE


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


def test_host_errors_remain_visible_in_transcript():
    assert 'self.responseText := "ERROR: " & SubStr(line, 15, star - 15);' in SOURCE
