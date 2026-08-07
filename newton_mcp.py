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
  * agent-authored files are confined to `runtime/agent-workspace/`; project
    creation and source writes reject path and symlink escapes, and builds make
    only that directory writable inside bubblewrap;
  * there is no physical-device install or staging tool here at all; a human
    follows `docs/install-paths.md` row 2 outside the agent surface.

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
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
EXAMPLES_DIR = REPO_ROOT / "examples"
AGENT_WORKSPACE = REPO_ROOT / "runtime" / "agent-workspace"
HARDWARE_STAGING = REPO_ROOT / "runtime" / "staging" / "hardware"
SERVER_NAME = "newton"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2025-06-18"
MAKE_TIMEOUT = 600.0
MAX_SOURCE_BYTES = 256 * 1024

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


def workspace_root(*, create: bool = False) -> Path:
    if AGENT_WORKSPACE.parent.is_symlink() or AGENT_WORKSPACE.is_symlink():
        raise ToolError("runtime/agent-workspace and its parent must not be symlinks")
    if create:
        AGENT_WORKSPACE.mkdir(parents=True, exist_ok=True)
    root = AGENT_WORKSPACE.resolve()
    if not root.is_dir():
        raise ToolError("runtime/agent-workspace does not exist")
    return root


def project_name(arguments: dict) -> str:
    name = want_str(arguments, "project")
    if (len(name) > 64 or not name.isascii() or not name[0].isalnum() or
            any(not (char.isalnum() or char == "-") for char in name)):
        raise ToolError("project must use 1-64 letters, digits, or hyphens")
    return name


def workspace_project(arguments: dict, *, must_exist: bool = True) -> Path:
    root = workspace_root(create=not must_exist)
    path = (root / project_name(arguments)).resolve()
    if path.parent != root:
        raise ToolError("project must be directly under runtime/agent-workspace/")
    if must_exist and not path.is_dir():
        raise ToolError(f"no such agent project: {path.name}")
    return path


def build_dir(arguments: dict) -> Path:
    value = want_str(arguments, "dir")
    root = workspace_root()
    path = (REPO_ROOT / value).resolve()
    if path.parent != root:
        raise ToolError(
            "dir must name a direct project under runtime/agent-workspace/, "
            f"got {value!r}")
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


def tool_create_project(arguments: dict) -> dict:
    project = workspace_project(arguments, must_exist=False)
    if project.exists():
        raise ToolError(f"agent project already exists: {project.name}")
    identity = want_str(arguments, "identity")
    identity_parts = identity.split(":")
    if (len(identity) > 80 or not identity.isascii() or len(identity_parts) != 2 or
            any(not part or not part[0].isalnum() for part in identity_parts) or
            any(not (char.isalnum() or char in "_-")
                for part in identity_parts for char in part)):
        raise ToolError(
            "identity must be a Newton package symbol such as MyAppR1:jbfly")
    title = want_str(arguments, "title")
    version = want_str(arguments, "version")
    if (len(title) > 120 or len(version) > 40 or
            not title.isascii() or not version.isascii() or
            any(char in title + version for char in "\r\n\"")):
        raise ToolError(
            "title/version must be short ASCII text without quotes or newlines")

    shutil.copytree(EXAMPLES_DIR / "hello", project)
    (project / "hello.pkg").unlink(missing_ok=True)
    (project / "hello.nprj").rename(project / f"{project.name}.nprj")
    makefile = (project / "Makefile").read_text(encoding="utf-8")
    (project / "Makefile").write_text(
        makefile.replace("hello", project.name), encoding="utf-8")
    nprj = project / f"{project.name}.nprj"
    nprj.write_text(
        nprj.read_text(encoding="utf-8").replace("HarnessHello:jbfly", identity),
        encoding="utf-8")
    source = project / "Main.newt"
    text = source.read_text(encoding="utf-8")
    text = text.replace("HarnessHello:jbfly", identity)
    text = text.replace('"Harness Hello"', f'"{title}"')
    text = text.replace('"0.1"', f'"{version}"')
    source.write_text(text, encoding="utf-8")
    return text_result(
        f"created runtime/agent-workspace/{project.name}; "
        "write Main.newt with write_source, then call build_pkg")


def tool_write_source(arguments: dict) -> dict:
    project = workspace_project(arguments)
    source = want_str(arguments, "source")
    size = len(source.encode("utf-8"))
    if size > MAX_SOURCE_BYTES:
        raise ToolError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    target = project / "Main.newt"
    if (target.is_symlink() or not target.is_file() or
            target.resolve().parent != project):
        raise ToolError("Main.newt must be a regular file inside the agent project")
    target.write_text(source, encoding="utf-8")
    return text_result(
        f"wrote {size} bytes to runtime/agent-workspace/{project.name}/Main.newt")


def tool_emulator_install(arguments: dict) -> dict:
    pkg_path = want_str(arguments, "pkg_path")
    if (not pkg_path.startswith(("/packages/", "/agent-workspace/"))
            or ".." in Path(pkg_path).parts):
        raise ToolError(
            "pkg_path must be under /packages/ or /agent-workspace/ without '..', e.g. "
            "/packages/hello/hello.pkg or "
            "/agent-workspace/my-app/my-app.pkg -- "
            "docs/install-paths.md row 1")
    return control_text(arguments, f"install {pkg_path}", "/install", pkg_path)


def tool_build_pkg(arguments: dict) -> dict:
    path = build_dir(arguments)
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise ToolError(
            "building agent-authored projects requires bubblewrap (bwrap) "
            "to keep writes inside runtime/agent-workspace/")
    command = [
        bwrap, "--ro-bind", "/", "/",
        "--bind", str(AGENT_WORKSPACE), str(AGENT_WORKSPACE),
        "--unshare-net", "--die-with-parent", "--chdir", str(REPO_ROOT),
        "make", "-B", "-C", str(path),
    ]
    code, output = run_make(command)
    pkg = path / f"{path.name}.pkg"
    if not pkg.exists():
        candidates = sorted(path.glob("*.pkg"))
        pkg = candidates[-1] if candidates else pkg
    if code != 0 or "Uncaught exception:" in output or not pkg.exists():
        return text_result(f"build failed (make exited {code})\n{tail(output)}",
                           is_error=True)
    relative = pkg.relative_to(AGENT_WORKSPACE)
    HARDWARE_STAGING.mkdir(parents=True, exist_ok=True)
    staged = HARDWARE_STAGING / pkg.name
    temporary = staged.with_suffix(staged.suffix + ".tmp")
    shutil.copyfile(pkg, temporary)
    temporary.replace(staged)
    location = (
        f"{pkg}\nemulator path: /agent-workspace/{relative}\n"
        f"Loader filename: {staged.name}"
    )
    return text_result(f"{location}\n{tail(output, 400)}")


TOOLS: list[dict] = [
    {
        "name": "newton_tool",
        "description": (
            "Call a fixed operation on the Newton tools client over the "
            "pkg_publisher broker (POST /tools on 18081). Works against "
            "whichever Newton is polling -- the physical MessagePad or an "
            "emulator with networking. Read-only ops available today: ping, "
            "front_app, note_list, get_note, note_probe, battery, store_info, "
            "pkg_list. "
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
        "name": "create_project",
        "description": (
            "Create a Newton package project by copying the read-only hello "
            "template into runtime/agent-workspace/. The project name is a "
            "single directory name; identity must be fresh for every install."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "directory/package filename stem, e.g. egg-timer-r1"},
                "identity": {"type": "string", "description": "fresh package symbol, e.g. EggTimerR1:jbfly"},
                "title": {"type": "string", "description": "Newton Extras title"},
                "version": {"type": "string", "description": "version text, e.g. 0.1-r1"},
            },
            "required": ["project", "identity", "title", "version"],
        },
        "handler": tool_create_project,
    },
    {
        "name": "write_source",
        "description": (
            "Replace Main.newt in one project directly under "
            "runtime/agent-workspace/. This tool cannot write elsewhere."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "project created by create_project"},
                "source": {"type": "string", "description": "complete Main.newt source"},
            },
            "required": ["project", "source"],
        },
        "handler": tool_write_source,
    },
    {
        "name": "emulator_install",
        "description": (
            "Install a package into an emulator. pkg_path is a path as the "
            "emulator sees it, under /packages/ -- either the read-only "
            "examples mount or the read-only /agent-workspace mount. This is a path, "
            "not an upload. Refused on the shared emulator "
            "without an instance. There is no tool that installs onto or "
            "stages a package for the physical Newton."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pkg_path": {"type": "string", "description": "/packages/<dir>/<name>.pkg or /agent-workspace/<dir>/<name>.pkg"},
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
            "for a direct project under runtime/agent-workspace/. "
            "Agent-workspace builds run in a no-network bubblewrap sandbox "
            "where only that workspace is writable. Publishes a successful build "
            "to runtime/staging/hardware/ under the same filename for the physical "
            "Newton Loader, and returns that filename plus the emulator path."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dir": {"type": "string", "description": "e.g. runtime/agent-workspace/my-app"},
            },
            "required": ["dir"],
        },
        "handler": tool_build_pkg,
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
