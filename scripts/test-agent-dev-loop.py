#!/usr/bin/env python3
"""Drive real server.py authoring turns against fresh isolated emulators."""

from __future__ import annotations

import argparse
import atexit
import concurrent.futures
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server

APPS = {
    "tic-tac-toe": ("Tic Tac Toe", "Build a tiny tic-tac-toe app with a visible 3 by 3 board; tapping a square shows X."),
    "counter": ("Tally Counter", "Build a tiny tally counter app with a visible number and a button that increments it."),
    "hello": ("Hello Newton", "Build a tiny note-style app that visibly says Hello from Newton."),
}
REQUIRED_TOOLS = ["create_project", "write_source", "build_pkg", "emulator_boot",
                  "emulator_install", "emulator_newtonscript", "emulator_screen"]
ACTIVE_PROCS: set[subprocess.Popen] = set()
ACTIVE_INSTANCES: set[str] = set()
ACTIVE_LOCK = threading.Lock()


def say(label: str, message: str) -> None:
    print(f"[{label}] {message}", flush=True)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def read_line(sock: socket.socket, deadline: float) -> bytes:
    data = bytearray()
    while not data.endswith(b"\n"):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("authoring turn deadline expired")
        sock.settimeout(min(remaining, 5))
        try:
            byte = sock.recv(1)
        except socket.timeout:
            continue
        if not byte:
            raise ConnectionError("server disconnected")
        data += byte
    return bytes(data)


def ack_server_frame(sock: socket.socket, raw: bytes, events: list[dict], label: str) -> str:
    seq, op, payload = server.parse_frame(raw)
    sock.sendall(f"ACK {seq:02d}\r\n".encode())
    events.append({"op": op, "payload": payload})
    if op in {"STAT", "TEXT", "PROMPT"}:
        say(label, f"native {op}: {payload}")
    return op


def send_client_frame(sock: socket.socket, seq: int, op: str, payload: str,
                      events: list[dict], deadline: float, label: str) -> None:
    say(label, f"send {op} seq={seq} bytes={len(payload.encode('utf-8'))}")
    sock.sendall(server.frame_line(seq, op, payload))
    while True:
        raw = read_line(sock, deadline)
        if raw == f"ACK {seq:02d}\r\n".encode():
            return
        if raw.startswith(b":"):
            ack_server_frame(sock, raw, events, label)


def drive_turn(port: int, prompt: str, timeout: float, label: str) -> list[dict]:
    deadline = time.monotonic() + timeout
    connect_deadline = min(deadline, time.monotonic() + 30)
    while True:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=2)
            break
        except OSError:
            if time.monotonic() >= connect_deadline:
                raise TimeoutError("server did not accept connections within 30s")
            time.sleep(0.2)
    events: list[dict] = []
    with sock:
        sock.sendall(server.NATIVE_HANDSHAKE + b"\r\n")
        send_client_frame(sock, 0, "HELLO", "NEWTON1", events, deadline, label)
        while True:
            raw = read_line(sock, deadline)
            if raw.startswith(b":") and ack_server_frame(sock, raw, events, label) == "STAT":
                break
        chunks = [prompt[i:i + 180] for i in range(0, len(prompt), 180)]
        for index, chunk in enumerate(chunks, 1):
            payload = chunk if len(chunks) == 1 else f"{index:02d} {len(chunks):02d} {chunk}"
            send_client_frame(sock, index, "MSG" if len(chunks) == 1 else "MSGP",
                              payload, events, deadline, label)
        while True:
            raw = read_line(sock, deadline)
            if raw.startswith(b":") and ack_server_frame(sock, raw, events, label) == "PROMPT":
                return events


def codex_home(path: Path) -> None:
    path.mkdir()
    shutil.copyfile(Path.home() / ".codex" / "auth.json", path / "auth.json")
    (path / "config.toml").write_text(
        'model = "gpt-5.6-sol"\nmodel_reasoning_effort = "high"\n'
        '[mcp_servers.newton]\ncommand = "python3"\n'
        f'args = ["{ROOT / "newton_mcp.py"}"]\n'
        'default_tools_approval_mode = "approve"\n', encoding="utf-8")


def stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def down_instance(instance: str) -> None:
    try:
        subprocess.run([str(ROOT / "scripts" / "emulator-instance.sh"), "down", instance],
                       cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=70, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def cleanup_all() -> None:
    with ACTIVE_LOCK:
        procs, instances = list(ACTIVE_PROCS), list(ACTIVE_INSTANCES)
        ACTIVE_PROCS.clear()
        ACTIVE_INSTANCES.clear()
    for proc in procs:
        stop_process(proc)
    for instance in instances:
        down_instance(instance)


def signal_cleanup(signum, _frame) -> None:
    cleanup_all()
    os._exit(128 + signum)


def pump_server(proc: subprocess.Popen, log_path: Path, label: str) -> None:
    with log_path.open("w", encoding="utf-8") as log:
        assert proc.stdout is not None
        for line in proc.stdout:
            log.write(line)
            log.flush()
            say(label, "server " + line.rstrip())


def completed_tools(path: Path) -> list[str]:
    if not path.exists():
        return []
    result = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(raw)
        if event.get("type") == "item.completed" and event.get("status") == "completed":
            result.append(event.get("tool", ""))
    return result


def contains_in_order(haystack: list[str], needles: list[str]) -> bool:
    position = 0
    for item in haystack:
        if position < len(needles) and item == needles[position]:
            position += 1
    return position == len(needles)


def normalized(text: str) -> str:
    return "".join(char.lower() for char in text if char.isalnum())


def run_one(app: str, run: int, stamp: str, evidence: Path, timeout: float) -> dict:
    title, request = APPS[app]
    short = app.replace("-", "")[:8]
    instance = f"dl-{short}-{stamp[-6:]}-{run}"
    project = f"dl-{short}-{stamp}-{run}"
    identity = f"DL{short.title()}{stamp}{run}:nwtn"
    prompt = (f"EMULATOR ONLY. {request} Use isolated instance {instance}. "
              f"Use project {project}, fresh identity {identity}, and exact visible title {title}. "
              "Do these stages in order: create_project, write_source, build_pkg, emulator_boot, "
              "emulator_install, emulator_newtonscript, emulator_screen. Verify the screenshot. "
              "Do not call hardware_install.")
    label = f"{app}#{run}"
    prefix = evidence / f"{app}-run{run}"
    state = prefix.with_suffix(".state")
    state.mkdir(parents=True, exist_ok=True)
    home = prefix.with_suffix(".codex")
    codex_home(home)
    port = free_port()
    log_path = prefix.with_suffix(".server.log")
    mcp_path = prefix.with_suffix(".mcp.jsonl")
    proc = subprocess.Popen(
        ["python3", str(ROOT / "server.py")], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        env={**os.environ, "CODEX_HOME": str(home), "NEWTON_PORT": str(port),
             "NEWTON_STATE_DIR": str(state), "NEWTON_CODEX_TIMEOUT": str(timeout),
             "NEWTON_MCP_EVENT_LOG": str(mcp_path)}, start_new_session=True)
    with ACTIVE_LOCK:
        ACTIVE_PROCS.add(proc)
        ACTIVE_INSTANCES.add(instance)
    pump = threading.Thread(target=pump_server, args=(proc, log_path, label), daemon=True)
    pump.start()
    started = time.monotonic()
    error = ""
    events: list[dict] = []
    say(label, f"START instance={instance} project={project} timeout={timeout:.0f}s")
    try:
        events = drive_turn(port, prompt, timeout + 15, label)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        say(label, "turn failed: " + error)
    finally:
        stop_process(proc)
        pump.join(timeout=5)
        with ACTIVE_LOCK:
            ACTIVE_PROCS.discard(proc)
    progress = [event["payload"] for event in events if event["op"] in {"STAT", "TEXT"}]
    prefix.with_suffix(".rollout.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    prefix.with_suffix(".progress.txt").write_text("\n".join(progress) + "\n", encoding="utf-8")
    screenshot = prefix.with_suffix(".png")
    ocr = ""
    try:
        subprocess.run(["python3", "-m", "emulator.client", "--instance", instance,
                        "screen", str(screenshot)], cwd=ROOT, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60)
        read = subprocess.run(["tesseract", str(screenshot), "stdout", "--psm", "11"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, timeout=60, check=False)
        ocr = read.stdout.strip()
        prefix.with_suffix(".ocr.txt").write_text(ocr + "\n", encoding="utf-8")
        say(label, "OCR: " + " | ".join(ocr.splitlines()))
    except Exception as exc:
        error = error or f"screenshot: {type(exc).__name__}: {exc}"
    finally:
        down_instance(instance)
        with ACTIVE_LOCK:
            ACTIVE_INSTANCES.discard(instance)
        shutil.rmtree(home, ignore_errors=True)
    tools = completed_tools(mcp_path)
    package = ROOT / "runtime" / "agent-workspace" / project / f"{project}.pkg"
    package_size = package.stat().st_size if package.exists() else 0
    package_sha256 = hashlib.sha256(package.read_bytes()).hexdigest() if package.exists() else ""
    final_error = next((text for text in progress if text.startswith("ERROR ")), "")
    gate = contains_in_order(tools, REQUIRED_TOOLS)
    passed = (not error and not final_error and gate and package_size > 0 and
              normalized(title) in normalized(ocr))
    if not gate and not error:
        error = f"MCP stage gate failed: completed={tools}"
    say(label, f"{'PASS' if passed else 'FAIL'} tools={tools} package={package_size}B seconds={time.monotonic() - started:.1f}")
    return {"app": app, "run": run, "instance": instance, "project": project,
            "passed": passed, "seconds": round(time.monotonic() - started, 1),
            "error": error or final_error, "title": title, "ocr": ocr,
            "completed_tools": tools, "package_bytes": package_size,
            "package_sha256": package_sha256,
            "screenshot": str(screenshot.relative_to(ROOT)),
            "rollout": str(prefix.with_suffix('.rollout.json').relative_to(ROOT)),
            "mcp_events": str(mcp_path.relative_to(ROOT)),
            "server_log": str(log_path.relative_to(ROOT))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--apps", nargs="+", choices=APPS, default=["tic-tac-toe"])
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--output")
    args = parser.parse_args()
    stamp = time.strftime("%m%d%H%M%S")
    evidence = ROOT / (args.output or f"runtime/evidence/devloop-reliability-{stamp}")
    evidence.mkdir(parents=True, exist_ok=True)
    results = []
    for run in range(1, args.runs + 1):
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(args.apps)) as pool:
            futures = [pool.submit(run_one, app, run, stamp, evidence, args.timeout) for app in args.apps]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
    results.sort(key=lambda result: (result["app"], result["run"]))
    (evidence / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    rows = ["| App | Passed | Runs |", "|---|---:|---:|"]
    for app in args.apps:
        app_results = [result for result in results if result["app"] == app]
        rows.append(f"| {app} | {sum(r['passed'] for r in app_results)} | {len(app_results)} |")
    (evidence / "summary.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(evidence.relative_to(ROOT), flush=True)
    raise SystemExit(0 if all(result["passed"] for result in results) else 1)


atexit.register(cleanup_all)
for handled_signal in (signal.SIGINT, signal.SIGTERM):
    signal.signal(handled_signal, signal_cleanup)

if __name__ == "__main__":
    main()
