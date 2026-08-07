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
    assert names == ["newton_tool", "emulator_screen", "emulator_tap",
                     "emulator_text", "emulator_key", "emulator_newtonscript",
                     "emulator_install", "build_pkg", "stage_hw"]
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


def test_build_pkg_refuses_paths_outside_examples(monkeypatch):
    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("make ran for a path outside examples/")

    monkeypatch.setattr(newton_mcp, "run_make", explode)
    for value in ("..", "runtime", "examples", "examples/../runtime"):
        result = newton_mcp.call_tool("build_pkg", {"dir": value})
        assert result["isError"] is True
        assert "examples/" in result["content"][0]["text"]


def test_build_pkg_allows_only_sandboxed_agent_workspace(monkeypatch, tmp_path):
    workspace = tmp_path / "agent-workspace"
    project = workspace / "my-app"
    project.mkdir(parents=True)
    seen = {}

    def fake_make(args):
        seen["args"] = args
        (project / "my-app.pkg").write_bytes(b"pkg")
        return 0, "built"

    monkeypatch.setattr(newton_mcp, "AGENT_WORKSPACE", workspace)
    monkeypatch.setattr(newton_mcp, "run_make", fake_make)
    monkeypatch.setattr(newton_mcp.shutil, "which", lambda name: "/usr/bin/bwrap")
    result = newton_mcp.call_tool("build_pkg", {"dir": str(project)})

    assert result["isError"] is False
    assert seen["args"][:5] == ["/usr/bin/bwrap", "--ro-bind", "/", "/", "--bind"]
    assert "--unshare-net" in seen["args"]
    assert seen["args"][-3:] == ["make", "-C", str(project)]
    assert "/agent-workspace/my-app/my-app.pkg" in result["content"][0]["text"]


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
    assert "examples/ or runtime/agent-workspace/" in result["content"][0]["text"]


def test_emulator_install_refuses_parent_traversal(monkeypatch):
    monkeypatch.setenv("NEWTON_ALLOW_SHARED", "1")
    monkeypatch.setattr(
        newton_mcp, "http_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("HTTP must not run")))
    result = newton_mcp.call_tool(
        "emulator_install", {"pkg_path": "/agent-workspace/../secret.pkg"})
    assert result["isError"] is True
    assert "without '..'" in result["content"][0]["text"]
