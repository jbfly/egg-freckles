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


def test_a3_identity_and_mars_default_match():
    assert "kAppSymbol := '|HarnessClientA3:jbfly|;" in SOURCE
    assert 'kVersion := "2.3-a3";' in SOURCE
    assert 'kAppLabel := "Chat A3";' in SOURCE
    assert "text: kAppLabel" in SOURCE
    assert 'name: "HarnessClientA3:jbfly"' in PROJECT
    assert "version: 13" in PROJECT
    assert "serverAddress: [10, 42, 0, 1]" in SOURCE
    assert "serverPort: 6801" in SOURCE


def test_prompt_is_a_large_multiline_handwriting_area():
    assert "else if top = 236 then self.promptView := child" in SOURCE
    assert "viewBounds: {left: 14, top: 236, right: 290, bottom: 354}" in SOURCE
    assert "viewJustify: vjLeftH" in SOURCE
    assert "viewLineSpacing: 24" in SOURCE
    assert "viewBounds: {left: 178, top: 360, right: 230, bottom: 382}" in SOURCE
    assert "viewBounds: {left: 238, top: 360, right: 290, bottom: 382}" in SOURCE


def test_host_errors_remain_visible_in_transcript():
    assert 'self.responseText := "ERROR: " & SubStr(line, 15, star - 15);' in SOURCE
