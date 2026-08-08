"""Tests for newton_mcp.py -- the Track D1 MCP server.

No network, no containers: the JSON-RPC round trips go over a pipe to a
subprocess, and the one HTTP-shaped test monkeypatches newton_mcp.http_request.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import newton_mcp

SERVER = Path(__file__).resolve().parent / "newton_mcp.py"


def speak(requests: list[dict], env: dict | None = None) -> list[dict]:
    """Send JSON-RPC lines to a fresh server process, read the replies."""
    child_env = dict(os.environ)
    child_env.pop("NEWTON_ALLOW_SHARED", None)
    # Point at a closed port so a rail failure cannot silently touch a
    # real broker or emulator.
    child_env["NEWTON_TOOLS_URL"] = "http://127.0.0.1:9"
    child_env["NEWTON_CONTROL_URL"] = "http://127.0.0.1:9"
    child_env.update(env or {})
    stdin = "".join(json.dumps(request) + "\n" for request in requests)
    finished = subprocess.run(
        [sys.executable, str(SERVER)], input=stdin.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        env=child_env, check=True)
    return [json.loads(line)
            for line in finished.stdout.decode("utf-8").splitlines() if line.strip()]


def test_initialize_and_tools_list_round_trip():
    replies = speak([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18",
                    "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ])
    assert [reply["id"] for reply in replies] == [1, 2]  # the notification is silent
    init = replies[0]["result"]
    assert init["serverInfo"]["name"] == "newton"
    assert init["protocolVersion"] == "2025-06-18"
    assert "tools" in init["capabilities"]
    names = [tool["name"] for tool in replies[1]["result"]["tools"]]
    assert names == ["pkg_install", "pkg_remove", "emulator_remove",
                     "newton_tool", "emulator_boot", "emulator_screen",
                     "emulator_tap", "emulator_text", "emulator_key", "emulator_newtonscript",
                     "create_project", "write_source", "emulator_install",
                     "hardware_install", "build_pkg"]
    for tool in replies[1]["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object"
        assert "handler" not in tool


def test_unknown_method_and_unknown_tool():
    replies = speak([
        {"jsonrpc": "2.0", "id": 1, "method": "resources/list"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "launch_missiles", "arguments": {}}},
    ])
    assert replies[0]["error"]["code"] == -32601
    assert replies[1]["result"]["isError"] is True
    assert "unknown tool" in replies[1]["result"]["content"][0]["text"]


def test_shared_emulator_refuses_mutating_ops():
    calls = [
        {"jsonrpc": "2.0", "id": index, "method": "tools/call",
         "params": {"name": name, "arguments": arguments}}
        for index, (name, arguments) in enumerate([
            ("emulator_tap", {"x": 10, "y": 20}),
            ("emulator_text", {"value": "hi"}),
            ("emulator_key", {"key": "Return"}),
            ("emulator_newtonscript", {"source": "2+2"}),
            ("emulator_install", {"pkg_path": "/packages/hello/hello.pkg"}),
        ], start=1)
    ]
    for reply in speak(calls):
        text = reply["result"]["content"][0]["text"]
        assert reply["result"]["isError"] is True, text
        assert "shared emulator" in text and "instance" in text


def test_shared_refusal_lifts_with_the_env_override():
    # The rail is off, so the call proceeds to HTTP and fails on the closed
    # port instead -- proof the refusal came from the rail, not from the network.
    reply = speak(
        [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
          "params": {"name": "emulator_tap", "arguments": {"x": 1, "y": 2}}}],
        env={"NEWTON_ALLOW_SHARED": "1"})[0]
    text = reply["result"]["content"][0]["text"]
    assert reply["result"]["isError"] is True
    assert "shared emulator" not in text
    assert "could not reach" in text


def test_newton_tool_posts_to_the_broker(monkeypatch):
    seen = {}

    def fake_request(url, *, data=None, content_type=None, timeout=15.0):
        seen.update(url=url, data=json.loads(data), content_type=content_type)
        return 200, b'{"status":"result","result":"Notes"}', "application/json"

    monkeypatch.setattr(newton_mcp, "http_request", fake_request)
    monkeypatch.setenv("NEWTON_TOOLS_URL", "http://10.42.0.1:18081")
    result = newton_mcp.call_tool("newton_tool", {"op": "front_app", "timeout": 30})

    assert seen["url"] == "http://10.42.0.1:18081/tools?timeout=30"
    assert seen["data"] == {"op": "front_app", "args": {}}
    assert seen["content_type"] == "application/json"
    assert result["isError"] is False
    assert json.loads(result["content"][0]["text"])["result"] == "Notes"


def test_newton_tool_gates_device_mutating_ops(monkeypatch):
    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("a human-gated op reached the network")

    monkeypatch.setattr(newton_mcp, "http_request", explode)
    result = newton_mcp.call_tool("newton_tool", {"op": "pkg_remove",
                                                  "args": {"name": "Chat"}})
    assert result["isError"] is True
    assert "needs human confirmation" in result["content"][0]["text"]


def test_emulator_screen_is_allowed_on_the_shared_emulator(monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"fake"
    monkeypatch.setattr(newton_mcp, "http_request",
                        lambda url, **kwargs: (200, png, "image/png"))
    monkeypatch.delenv("NEWTON_ALLOW_SHARED", raising=False)
    result = newton_mcp.call_tool("emulator_screen", {})
    image = result["content"][1]
    assert result["isError"] is False
    assert image["mimeType"] == "image/png"
    assert base64.b64decode(image["data"]) == png



def test_emulator_boot_recreates_fresh_instance(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs["timeout"]))
        return newton_mcp.subprocess.CompletedProcess(command, 0, b"started")

    replies = iter([
        (200, b'{"status":"ready"}', "application/json"),
        (200, b'{"ok":true}', "application/json"),
        (200, b'{"ok":true}', "application/json"),
        (200, b'{"ok":true}', "application/json"),
        (200, b'{"ok":true}', "application/json"),
    ])
    monkeypatch.setattr(newton_mcp.subprocess, "run", fake_run)
    monkeypatch.setattr(newton_mcp, "control_target", lambda args: ("http://127.0.0.1:1234", False))
    monkeypatch.setattr(newton_mcp, "http_request", lambda *args, **kwargs: next(replies))
    monkeypatch.setattr(newton_mcp.time, "sleep", lambda seconds: None)

    result = newton_mcp.call_tool("emulator_boot", {"instance": "test-loop"})

    script = str(newton_mcp.REPO_ROOT / "scripts" / "emulator-instance.sh")
    assert calls == [
        ([script, "down", "test-loop"], newton_mcp.EMULATOR_COMMAND_TIMEOUT),
        ([script, "up", "test-loop"], newton_mcp.EMULATOR_COMMAND_TIMEOUT),
    ]
    assert result["isError"] is False
    assert "fresh emulator test-loop is healthy" in result["content"][0]["text"]


def test_emulator_boot_rejects_non_lowercase_instance():
    result = newton_mcp.call_tool("emulator_boot", {"instance": "Bad_Name"})
    assert result["isError"] is True
    assert "lowercase" in result["content"][0]["text"]

def test_hardware_install_requires_out_of_band_human_gate(monkeypatch):
    monkeypatch.delenv("NEWTON_ALLOW_HARDWARE_INSTALL", raising=False)
    monkeypatch.setattr(
        newton_mcp.subprocess, "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("installer must not run without the human gate")))

    result = newton_mcp.call_tool(
        "hardware_install", {"pkg_name": "my-app.pkg"})

    assert result["isError"] is True
    assert "needs human confirmation" in result["content"][0]["text"]


def test_hardware_install_listens_for_three_minutes(monkeypatch, tmp_path):
    staging = tmp_path / "hardware"
    staging.mkdir()
    package = staging / "my-app.pkg"
    package.write_bytes(b"package0")
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return newton_mcp.subprocess.CompletedProcess(command, 0, b"Package installed")

    monkeypatch.setattr(newton_mcp, "HARDWARE_STAGING", staging)
    monkeypatch.setenv("NEWTON_ALLOW_HARDWARE_INSTALL", "1")
    monkeypatch.setattr(newton_mcp.subprocess, "run", fake_run)

    result = newton_mcp.call_tool("hardware_install", {"pkg_name": package.name})

    assert result["isError"] is False
    assert seen["command"] == [str(newton_mcp.REPO_ROOT / "runtime" /
                                   "install-newton-tcp"), str(package)]
    assert seen["env"]["NEWTON_DOCK_TIMEOUT"] == "180"
    assert seen["timeout"] == 195


def test_build_pkg_refuses_paths_outside_agent_workspace(monkeypatch, tmp_path):
    workspace = tmp_path / "agent-workspace"
    workspace.mkdir()
    monkeypatch.setattr(newton_mcp, "AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(
        newton_mcp, "run_make",
        lambda args: (_ for _ in ()).throw(AssertionError("make must not run")))
    for value in ("..", "runtime", "examples/hello", str(workspace),
                  str(workspace / "../escape")):
        result = newton_mcp.call_tool("build_pkg", {"dir": value})
        assert result["isError"] is True
        assert "runtime/agent-workspace/" in result["content"][0]["text"]


def test_build_pkg_allows_only_sandboxed_agent_workspace(monkeypatch, tmp_path):
    workspace = tmp_path / "agent-workspace"
    project = workspace / "my-app"
    project.mkdir(parents=True)
    seen = {}

    def fake_make(args):
        seen["args"] = args
        (project / "my-app.pkg").write_bytes(b"pkg")
        return 0, "built"

    staging = tmp_path / "hardware"
    monkeypatch.setattr(newton_mcp, "AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(newton_mcp, "HARDWARE_STAGING", staging)
    monkeypatch.setattr(newton_mcp, "run_make", fake_make)
    monkeypatch.setattr(newton_mcp.shutil, "which", lambda name: "/usr/bin/bwrap")
    result = newton_mcp.call_tool("build_pkg", {"dir": str(project)})

    assert result["isError"] is False
    assert seen["args"][:5] == ["/usr/bin/bwrap", "--ro-bind", "/", "/", "--bind"]
    assert "--unshare-net" in seen["args"]
    assert seen["args"][-4:] == ["make", "-B", "-C", str(project)]
    assert "/agent-workspace/my-app/my-app.pkg" in result["content"][0]["text"]
    assert "Loader filename: my-app.pkg" in result["content"][0]["text"]
    assert (staging / "my-app.pkg").read_bytes() == b"pkg"


def test_build_pkg_does_not_publish_tntk_exception(monkeypatch, tmp_path):
    workspace = tmp_path / "agent-workspace"
    project = workspace / "bad-app"
    project.mkdir(parents=True)
    staging = tmp_path / "hardware"

    def fake_make(args):
        (project / "bad-app.pkg").write_bytes(b"package0partial")
        return 0, "Uncaught exception: kNErrUndefinedVariable"

    monkeypatch.setattr(newton_mcp, "AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(newton_mcp, "HARDWARE_STAGING", staging)
    monkeypatch.setattr(newton_mcp, "run_make", fake_make)
    monkeypatch.setattr(newton_mcp.shutil, "which", lambda name: "/usr/bin/bwrap")

    result = newton_mcp.call_tool("build_pkg", {"dir": str(project)})

    assert result["isError"] is True
    assert not (staging / "bad-app.pkg").exists()


def test_build_pkg_rejects_tntk_crash_without_identical_retry(monkeypatch,
                                                               tmp_path):
    workspace = tmp_path / "agent-workspace"
    project = workspace / "deep-app"
    project.mkdir(parents=True)
    fixture = (Path(__file__).parent / "runtime" / "evidence" /
               "tntk-crash-fixture" / "Main.newt")
    (project / "Main.newt").write_text(fixture.read_text())
    staging = tmp_path / "hardware"

    def fake_make(args):
        (project / "deep-app.pkg").write_bytes(b"stale package")
        return 2, "Segmentation fault (core dumped)"

    monkeypatch.setattr(newton_mcp, "AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(newton_mcp, "HARDWARE_STAGING", staging)
    monkeypatch.setattr(newton_mcp, "run_make", fake_make)
    monkeypatch.setattr(newton_mcp.shutil, "which", lambda name: "/usr/bin/bwrap")

    result = newton_mcp.call_tool("build_pkg", {"dir": str(project)})

    assert result["isError"] is True
    assert "tntk crashed" in result["content"][0]["text"]
    assert "do not retry byte-identical Main.newt" in result["content"][0]["text"]
    assert not (staging / "deep-app.pkg").exists()


def test_build_pkg_refuses_workspace_symlink_escape(monkeypatch, tmp_path):
    workspace = tmp_path / "agent-workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(newton_mcp, "AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(
        newton_mcp, "run_make",
        lambda args: (_ for _ in ()).throw(AssertionError("make must not run")))

    result = newton_mcp.call_tool("build_pkg", {"dir": str(workspace / "escape")})
    assert result["isError"] is True
    assert "direct project under runtime/agent-workspace/" in result["content"][0]["text"]


def test_emulator_install_refuses_parent_traversal(monkeypatch):
    monkeypatch.setenv("NEWTON_ALLOW_SHARED", "1")
    monkeypatch.setattr(
        newton_mcp, "http_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("HTTP must not run")))
    result = newton_mcp.call_tool(
        "emulator_install", {"pkg_path": "/agent-workspace/../secret.pkg"})
    assert result["isError"] is True
    assert "without '..'" in result["content"][0]["text"]


def test_emulator_newtonscript_refuses_open_on_symbol(monkeypatch):
    monkeypatch.setattr(
        newton_mcp, "http_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("HTTP must not run")))

    result = newton_mcp.call_tool("emulator_newtonscript", {
        "instance": "isolated", "source": "|TicTacToeCPUR1:nwh|:Open();"})

    assert result["isError"] is True
    assert "GetRoot().|MyAppR1:jbfly|:Open();" in result["content"][0]["text"]
    assert "-48809" in result["content"][0]["text"]


def test_create_and_write_source_are_confined_to_workspace(monkeypatch, tmp_path):
    workspace = tmp_path / "agent-workspace"
    monkeypatch.setattr(newton_mcp, "AGENT_WORKSPACE", workspace)

    created = newton_mcp.call_tool("create_project", {
        "project": "egg-timer-r1",
        "identity": "EggTimerR1:jbfly",
        "title": "Egg Timer",
        "version": "0.1-r1",
    })
    project = workspace / "egg-timer-r1"
    assert created["isError"] is False
    assert (project / "egg-timer-r1.nprj").is_file()
    assert "egg-timer-r1.pkg" in (project / "Makefile").read_text()
    assert "EggTimerR1:jbfly" in (project / "egg-timer-r1.nprj").read_text()

    source = "kAppSymbol := '|EggTimerR1:jbfly|;\n// generated source\n"
    written = newton_mcp.call_tool(
        "write_source", {"project": "egg-timer-r1", "source": source})
    assert written["isError"] is False
    assert (project / "Main.newt").read_text() == source

    for project_name in ("../escape", "nested/escape", ".", "egg_timer"):
        result = newton_mcp.call_tool("write_source", {
            "project": project_name, "source": "bad"})
        assert result["isError"] is True
    assert not (tmp_path / "escape").exists()


def test_write_source_refuses_symlink_escape(monkeypatch, tmp_path):
    workspace = tmp_path / "agent-workspace"
    project = workspace / "app"
    outside = tmp_path / "outside.newt"
    project.mkdir(parents=True)
    outside.write_text("keep")
    (project / "Main.newt").symlink_to(outside)
    monkeypatch.setattr(newton_mcp, "AGENT_WORKSPACE", workspace)

    result = newton_mcp.call_tool(
        "write_source", {"project": "app", "source": "replace"})
    assert result["isError"] is True
    assert outside.read_text() == "keep"


def test_workspace_root_refuses_symlink(monkeypatch, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace = tmp_path / "agent-workspace"
    workspace.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(newton_mcp, "AGENT_WORKSPACE", workspace)

    result = newton_mcp.call_tool("create_project", {
        "project": "app", "identity": "AppR1:jbfly",
        "title": "App", "version": "0.1",
    })
    assert result["isError"] is True
    assert "must not be symlinks" in result["content"][0]["text"]


def test_workspace_mount_control_path_and_read_only_agent_are_pinned():
    root = SERVER.parent
    server_source = (root / "server.py").read_text(encoding="utf-8")
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    control_patch = (root / "containers/patches/einstein-control-socket.patch").read_text(
        encoding="utf-8")

    assert '"--sandbox", "read-only"' in server_source
    assert '"--sandbox", "workspace-write"' not in server_source
    assert "./runtime/agent-workspace:/agent-workspace:ro" in compose
    assert 'path.compare(0, 17, "/agent-workspace/")' in control_patch


def test_pkg_install_validates_staged_basename_and_dispatches(monkeypatch, tmp_path):
    staging = tmp_path / "hardware"
    staging.mkdir()
    (staging / "my-app.pkg").write_bytes(b"package0")
    seen = {}

    def fake_request(url, *, data=None, content_type=None, timeout=15.0):
        seen.update(url=url, data=json.loads(data), timeout=timeout)
        return 200, b'{"status":"result","result":"installed"}', "application/json"

    monkeypatch.setattr(newton_mcp, "HARDWARE_STAGING", staging)
    monkeypatch.setattr(newton_mcp, "http_request", fake_request)
    result = newton_mcp.call_tool("pkg_install", {"basename": "my-app.pkg"})
    assert result["isError"] is False
    assert seen["data"] == {"op": "pkg_install", "args": {"id": "my-app.pkg"}}
    assert seen["url"].endswith("/tools?timeout=120")
    assert seen["timeout"] == 130

    for bad in ("../my-app.pkg", "missing.pkg", "not-pkg", "bad name.pkg"):
        result = newton_mcp.call_tool("pkg_install", {"basename": bad})
        assert result["isError"] is True


def test_pkg_remove_dispatches_exact_identity_and_refuses_protected(monkeypatch):
    seen = {}

    def fake_request(url, *, data=None, **kwargs):
        seen.update(json.loads(data))
        return 200, b'{"status":"result","result":"removed"}', "application/json"

    monkeypatch.setattr(newton_mcp, "http_request", fake_request)
    result = newton_mcp.call_tool("pkg_remove", {"identity": "My App:jbfly"})
    assert result["isError"] is False
    assert seen == {"op": "pkg_remove", "args": {"id": "My%20App:jbfly"}}

    for identity in ("EggFrecklesEF21:jbfly", "-Loader1:jbfly",
                     "NewtsCape:NewtsCape", "Newton Internet Enabler",
                     "LucentWaveLAN:Noguchi"):
        result = newton_mcp.call_tool("pkg_remove", {"identity": identity})
        assert result["isError"] is True
        assert "protected package" in result["content"][0]["text"]


def test_emulator_remove_uses_store_specific_lookup(monkeypatch):
    seen = {}
    monkeypatch.setattr(newton_mcp, "control_text",
                        lambda arguments, action, path, body: seen.update(
                            arguments=arguments, action=action, path=path, body=body) or
                        newton_mcp.text_result("removed"))
    result = newton_mcp.call_tool(
        "emulator_remove", {"identity": "MyApp:jbfly", "instance": "pkgproof"})
    assert result["isError"] is False
    assert seen["arguments"]["instance"] == "pkgproof"
    assert 'GetRoot().(Intern(identity))' in seen["body"]
    assert 'GetPkgRef(identity, store)' in seen["body"]
    assert 'SafeRemovePackage(p)' in seen["body"]
