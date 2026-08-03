#!/usr/bin/env python3
"""MCP server (stdio, JSON-RPC 2.0) that gives the chat agent Newton tools.

ROADMAP Track D1 (+ D2's rails folded in). Stdlib only, no MCP SDK: the
protocol surface an agent runner actually needs is three methods --
`initialize`, `tools/list`, `tools/call` -- plus notifications it can ignore,
so it is hand-rolled here and stays one file.

The safety rails live in this code, not in a prompt (Track D2):

  * mutating emulator ops (tap/text/key/newtonscript/install) refuse the
    SHARED emulator unless `NEWTON_ALLOW_SHARED=1`; `emulator_screen` is
    always allowed;
  * `newton_tool` refuses ops that would change a physical device and hands
    back the command for the human instead;
  * there is no physical-device install tool here at all. `stage_hw` stages a
    package into `runtime/staging/hardware/`; a human types the filename into
    the ZC40 loader and taps Install (`docs/install-paths.md` row 2).

Environment:
  NEWTON_TOOLS_URL     base URL of the pkg_publisher tools broker
                       (default http://10.42.0.1:18081)
  NEWTON_CONTROL_URL   base URL of the SHARED emulator control API
                       (default http://127.0.0.1:18080)
  NEWTON_ALLOW_SHARED  "1" to allow mutating ops on the shared emulator
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
EXAMPLES_DIR = REPO_ROOT / "examples"
SERVER_NAME = "newton"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2025-06-18"
MAKE_TIMEOUT = 600.0

# Ops that would mutate a physical MessagePad. None of them exist on the
# Newton client yet (ROADMAP C5); the rail is here so they cannot arrive
# without a human gate. docs/notes-bridge.md:16.
HUMAN_GATED_OPS = {"pkg_install", "pkg_remove", "note_write", "note_delete",
                   "note_create", "reset", "restart"}


class ToolError(RuntimeError):
    """A tool failed in a way the agent should see as text, not a crash."""


def tools_url() -> str:
    return os.environ.get("NEWTON_TOOLS_URL", "http://10.42.0.1:18081").rstrip("/")


def shared_control_url() -> str:
    return os.environ.get("NEWTON_CONTROL_URL", "http://127.0.0.1:18080").rstrip("/")


# --------------------------------------------------------------------------
# HTTP -- one chokepoint, so tests can monkeypatch exactly one function.


def http_request(url: str, *, data: bytes | None = None,
                 content_type: str | None = None,
                 timeout: float = 15.0) -> tuple[int, bytes, str]:
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(
        url, data=data, headers=headers,
        method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return (response.status, response.read(),
                    response.headers.get_content_type())
    except urllib.error.HTTPError as exc:
        # The /tools route answers unknown_op / timeout with a JSON body and a
        # 4xx/5xx code; pass that through rather than losing it.
        body = exc.read()
        kind = exc.headers.get_content_type() if exc.headers else "text/plain"
        return exc.code, body, kind
    except (urllib.error.URLError, OSError) as exc:
        raise ToolError(f"could not reach {url}: {exc}") from exc


# --------------------------------------------------------------------------
# Argument helpers


def want_str(arguments: dict, field: str, *, required: bool = True) -> str:
    value = arguments.get(field, "")
    if not isinstance(value, str):
        raise ToolError(f"{field} must be a string")
    if required and not value.strip():
        raise ToolError(f"{field} is required")
    return value


def want_int(arguments: dict, field: str) -> int:
    value = arguments.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolError(f"{field} must be an integer")
    return value


def control_target(arguments: dict) -> tuple[str, bool]:
    """Return (base_url, is_shared) for an emulator tool call."""
    instance = want_str(arguments, "instance", required=False).strip()
    if not instance:
        return shared_control_url(), True
    try:
        from emulator.client import instance_url
    except ImportError as exc:  # pragma: no cover - only in a trimmed image
        raise ToolError(
            "instance lookup needs emulator/client.py next to newton_mcp.py"
        ) from exc
    try:
        return instance_url(instance), False
    except SystemExit as exc:  # instance_url exits with the podman error text
        raise ToolError(str(exc)) from exc


def guard_shared(action: str, shared: bool) -> None:
    if not shared or os.environ.get("NEWTON_ALLOW_SHARED") == "1":
        return
    raise ToolError(
        f"refusing to {action} on the shared emulator "
        "(newton-harness_emulator_1) -- other sessions and the physical-bench "
        "workflow depend on it. Use an isolated instance: "
        "`make emulator-instance-up INSTANCE=<name>`, then pass "
        "instance=\"<name>\". Set NEWTON_ALLOW_SHARED=1 in this MCP server's "
        "env only if a human has said the shared emulator is yours.")


def example_dir(arguments: dict, field: str) -> Path:
    value = want_str(arguments, field)
    path = (REPO_ROOT / value).resolve()
    if path == EXAMPLES_DIR or EXAMPLES_DIR not in path.parents:
        raise ToolError(f"{field} must name a directory under examples/, got {value!r}")
    if not path.is_dir():
        raise ToolError(f"no such directory: {value}")
    return path


def run_make(args: list[str]) -> tuple[int, str]:
    try:
        finished = subprocess.run(
            args, cwd=REPO_ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=MAKE_TIMEOUT, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"{args[0]} timed out after {MAKE_TIMEOUT:.0f}s") from exc
    except OSError as exc:
        raise ToolError(f"could not run {args[0]}: {exc}") from exc
    return finished.returncode, finished.stdout.decode("utf-8", "replace")


def tail(text: str, limit: int = 2000) -> str:
    text = text.strip()
    return text if len(text) <= limit else "...\n" + text[-limit:]


def text_result(text: str, *, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


# --------------------------------------------------------------------------
# Tools


def tool_newton_tool(arguments: dict) -> dict:
    op = want_str(arguments, "op")
    if op in HUMAN_GATED_OPS:
        raise ToolError(
            f"{op!r} changes the device and needs human confirmation. Ask the "
            "human to run it: "
            f"curl -s -X POST {tools_url()}/tools -H 'Content-Type: application/json' "
            f"-d '{json.dumps({'op': op, 'args': arguments.get('args') or {}})}'")
    tool_args = arguments.get("args") or {}
    if not isinstance(tool_args, dict):
        raise ToolError("args must be an object")
    timeout = arguments.get("timeout", 20)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ToolError("timeout must be a number")
    if not 0 < timeout <= 120:
        raise ToolError("timeout must be greater than 0 and at most 120 seconds")
    body = json.dumps({"op": op, "args": tool_args}).encode("utf-8")
    url = f"{tools_url()}/tools?timeout={timeout:g}"
    status, payload, _ = http_request(
        url, data=body, content_type="application/json", timeout=timeout + 10)
    return text_result(payload.decode("utf-8", "replace").strip() or f"HTTP {status}",
                       is_error=status >= 400)


def tool_emulator_screen(arguments: dict) -> dict:
    base, shared = control_target(arguments)  # screen is always allowed
    status, payload, kind = http_request(base + "/screen.png", timeout=20)
    if status != 200 or kind != "image/png":
        raise ToolError(
            f"{base}/screen.png returned {status} {kind}: "
            f"{payload.decode('utf-8', 'replace')[:200]}")
    where = "shared emulator" if shared else base
    return {
        "content": [
            {"type": "text",
             "text": f"320x480 Newton screen from the {where}"},
            {"type": "image",
             "data": base64.b64encode(payload).decode("ascii"),
             "mimeType": "image/png"},
        ],
        "isError": False,
    }


def control_json(arguments: dict, action: str, path: str, payload: dict) -> dict:
    base, shared = control_target(arguments)
    guard_shared(action, shared)
    status, body, _ = http_request(
        base + path, data=json.dumps(payload).encode("utf-8"),
        content_type="application/json", timeout=30)
    text = body.decode("utf-8", "replace").strip()
    return text_result(text or f"HTTP {status}", is_error=status >= 400)


def control_text(arguments: dict, action: str, path: str, body: str) -> dict:
    base, shared = control_target(arguments)
    guard_shared(action, shared)
    status, reply, _ = http_request(
        base + path, data=body.encode("utf-8"), timeout=30)
    text = reply.decode("utf-8", "replace").strip()
    return text_result(text or f"HTTP {status}", is_error=status >= 400)


def tool_emulator_tap(arguments: dict) -> dict:
    x, y = want_int(arguments, "x"), want_int(arguments, "y")
    return control_json(arguments, f"tap ({x},{y})", "/tap", {"x": x, "y": y})


def tool_emulator_text(arguments: dict) -> dict:
    value = want_str(arguments, "value")
    return control_json(arguments, "type text", "/text", {"text": value})


def tool_emulator_key(arguments: dict) -> dict:
    key = want_str(arguments, "key")
    return control_json(arguments, f"send key {key!r}", "/key", {"key": key})


def tool_emulator_newtonscript(arguments: dict) -> dict:
    source = want_str(arguments, "source")
    return control_text(arguments, "evaluate NewtonScript", "/newtonscript", source)


def tool_emulator_install(arguments: dict) -> dict:
    pkg_path = want_str(arguments, "pkg_path")
    if not pkg_path.startswith("/packages/"):
        raise ToolError(
            "pkg_path must be a path inside the emulator under /packages/ "
            "(the read-only mount of examples/), e.g. "
            "/packages/hello/hello.pkg -- docs/install-paths.md row 1")
    return control_text(arguments, f"install {pkg_path}", "/install", pkg_path)


def tool_build_pkg(arguments: dict) -> dict:
    path = example_dir(arguments, "dir")
    code, output = run_make(["make", "-C", str(path)])
    pkg = path / f"{path.name}.pkg"
    if not pkg.exists():
        candidates = sorted(path.glob("*.pkg"))
        pkg = candidates[-1] if candidates else pkg
    if code != 0 or not pkg.exists():
        return text_result(f"build failed (make exited {code})\n{tail(output)}",
                           is_error=True)
    return text_result(f"{pkg}\n{tail(output, 400)}")


def tool_stage_hw(arguments: dict) -> dict:
    path = example_dir(arguments, "pkg_dir")
    relative = path.relative_to(REPO_ROOT)
    code, output = run_make(["make", "stage-hw", f"PKG={relative}"])
    if code != 0:
        return text_result(f"stage-hw failed (make exited {code})\n{tail(output)}",
                           is_error=True)
    staged = [line for line in output.splitlines() if line.startswith("Staged ")]
    summary = staged[-1] if staged else tail(output, 400)
    return text_result(
        summary + "\n\nStaged only. Nothing was installed: a human opens the "
        "ZC40 Loader on the Newton, types that filename, and taps Install "
        "(docs/install-paths.md row 2).")


TOOLS: list[dict] = [
    {
        "name": "newton_tool",
        "description": (
            "Call a fixed operation on the Newton tools client over the "
            "pkg_publisher broker (POST /tools on 18081). Works against "
            "whichever Newton is polling -- the physical MessagePad or an "
            "emulator with networking. Read-only ops available today: ping, "
            "front_app, get_note, note_probe, battery, store_info, pkg_list. "
            "Ops that would change the device are refused and handed back as a "
            "command for the human."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "op": {"type": "string", "description": "operation name, e.g. front_app"},
                "args": {"type": "object", "description": "operation arguments, e.g. {\"id\": 1}"},
                "timeout": {"type": "number", "description": "seconds to wait for the Newton (default 20, max 120)"},
            },
            "required": ["op"],
        },
        "handler": tool_newton_tool,
    },
    {
        "name": "emulator_screen",
        "description": (
            "Screenshot the 320x480 Newton screen of an Einstein emulator and "
            "return it as an image. Allowed on the shared emulator."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "instance": {"type": "string", "description": "isolated instance name; omit for the shared emulator"},
            },
        },
        "handler": tool_emulator_screen,
    },
    {
        "name": "emulator_tap",
        "description": (
            "Tap the Newton screen at (x, y) in 320x480 screen coordinates. "
            "Refused on the shared emulator without an instance."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "instance": {"type": "string"},
            },
            "required": ["x", "y"],
        },
        "handler": tool_emulator_tap,
    },
    {
        "name": "emulator_text",
        "description": (
            "Type text into the emulator window via xdotool. Refused on the "
            "shared emulator without an instance."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
                "instance": {"type": "string"},
            },
            "required": ["value"],
        },
        "handler": tool_emulator_text,
    },
    {
        "name": "emulator_key",
        "description": (
            "Send one key (xdotool key name, e.g. Return) to the emulator. "
            "Refused on the shared emulator without an instance."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "instance": {"type": "string"},
            },
            "required": ["key"],
        },
        "handler": tool_emulator_key,
    },
    {
        "name": "emulator_newtonscript",
        "description": (
            "Evaluate one line of NewtonScript inside the emulator through the "
            "Einstein control socket. Refused on the shared emulator without "
            "an instance."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "one line, e.g. GetRoot().|Foo:jbfly|:Open();"},
                "instance": {"type": "string"},
            },
            "required": ["source"],
        },
        "handler": tool_emulator_newtonscript,
    },
    {
        "name": "emulator_install",
        "description": (
            "Install a package into an emulator. pkg_path is a path as the "
            "emulator sees it, under /packages/ (the read-only mount of "
            "examples/) -- not an upload. Refused on the shared emulator "
            "without an instance. There is no tool that installs onto the "
            "physical Newton; use stage_hw and let a human finish."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pkg_path": {"type": "string", "description": "/packages/<dir>/<name>.pkg"},
                "instance": {"type": "string"},
            },
            "required": ["pkg_path"],
        },
        "handler": tool_emulator_install,
    },
    {
        "name": "build_pkg",
        "description": (
            "Build one package with the host toolchain: runs `make -C <dir>` "
            "for a directory under examples/. Returns the built .pkg path, or "
            "the compiler error text if the build failed."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dir": {"type": "string", "description": "e.g. examples/hello"},
            },
            "required": ["dir"],
        },
        "handler": tool_build_pkg,
    },
    {
        "name": "stage_hw",
        "description": (
            "Build a package and stage it for the physical Newton "
            "(`make stage-hw PKG=<dir>`): copies into "
            "runtime/staging/hardware/ and refreshes SHA256SUMS. This does NOT "
            "install anything. It returns the short filename a human then "
            "types into the ZC40 Loader on the device before tapping Install."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pkg_dir": {"type": "string", "description": "e.g. examples/harness-client"},
            },
            "required": ["pkg_dir"],
        },
        "handler": tool_stage_hw,
    },
]

HANDLERS = {tool["name"]: tool["handler"] for tool in TOOLS}
PUBLIC_TOOLS = [{k: v for k, v in tool.items() if k != "handler"} for tool in TOOLS]


def call_tool(name: str, arguments: dict) -> dict:
    handler = HANDLERS.get(name)
    if handler is None:
        return text_result(f"unknown tool {name!r}", is_error=True)
    if not isinstance(arguments, dict):
        return text_result("arguments must be an object", is_error=True)
    try:
        return handler(arguments)
    except ToolError as exc:
        return text_result(str(exc), is_error=True)
    except Exception as exc:  # never take the whole server down for one call
        return text_result(f"{type(exc).__name__}: {exc}", is_error=True)


# --------------------------------------------------------------------------
# JSON-RPC 2.0 / MCP plumbing


def ok(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def fail(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def handle(request: dict) -> dict | None:
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return fail(None, -32600, "invalid request")
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return None  # a notification: initialized, cancelled, ... -- ignore
    if not isinstance(method, str):
        return fail(request_id, -32600, "invalid request")
    params = request.get("params")
    params = params if isinstance(params, dict) else {}

    if method == "initialize":
        asked = params.get("protocolVersion")
        return ok(request_id, {
            "protocolVersion": asked if isinstance(asked, str) else DEFAULT_PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method == "ping":
        return ok(request_id, {})
    if method == "tools/list":
        return ok(request_id, {"tools": PUBLIC_TOOLS})
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str):
            return fail(request_id, -32602, "params.name must be a string")
        return ok(request_id, call_tool(name, params.get("arguments") or {}))
    return fail(request_id, -32601, f"unknown method {method!r}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            response = fail(None, -32700, "parse error")
        else:
            response = handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
