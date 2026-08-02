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


def test_a1_identity_and_mars_default_match():
    assert "kAppSymbol := '|HarnessClientA1:jbfly|;" in SOURCE
    assert 'kVersion := "2.1-a1";' in SOURCE
    assert 'name: "HarnessClientA1:jbfly"' in PROJECT
    assert "serverAddress: [10, 42, 0, 1]" in SOURCE
    assert "serverPort: 6801" in SOURCE
