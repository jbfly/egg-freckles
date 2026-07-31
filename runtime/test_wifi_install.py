#!/usr/bin/env python3
"""End-to-end loader proof against the running Einstein emulator."""

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = os.environ.get("NEWTON_CONTAINER", "newton-harness_emulator_1")
LOADER_ID = "-HarnessLoaderZC37:jbfly"
LOADER_SYMBOL = "|-HarnessLoaderZC37:jbfly|"


def run(*args, input=None, check=True):
    return subprocess.run(args, input=input, text=True, capture_output=True, check=check)


def ns(source, timeout=10):
    result = run(
        str(ROOT / "runtime/ns_eval.py"), source,
        "--container", CONTAINER, "--timeout", str(timeout),
    )
    return result.stdout.strip()


def build_large_proof(directory, identity):
    chunks = ",\n        ".join('"' + "x" * 8000 + '"' for _ in range(20))
    (directory / "Main.newt").write_text(f'''kAppSymbol := '|{identity}|;
kAppTitle := "{identity}";
mainView := {{
    _proto: protoFloatNGo,
    viewBounds: {{left: 24, top: 120, right: 296, bottom: 210}},
    title: kAppTitle,
    appSymbol: kAppSymbol,
    padding: [
        {chunks}
    ],
    Proof: func() "wifi-install-ok",
    stepChildren: [{{_proto: protoStaticText, viewBounds: {{left: 16, top: 16, right: 250, bottom: 48}}, text: "Large WiFi install proved", viewFont: ROM_fontSystem12Bold}}],
}};
{{app: kAppSymbol, text: kAppTitle, theForm: mainView}}
''')
    (directory / "proof.nprj").write_text(
        f'{{parts: [{{main: "Main.newt", files: []}}], name: "{identity}", platform: "Newton 2.1"}}\n'
    )
    env = os.environ | {"LD_LIBRARY_PATH": f"{Path.home()}/newton-dev/prefix/lib:" + os.environ.get("LD_LIBRARY_PATH", "")}
    subprocess.run(
        [str(Path.home() / "newton-dev/prefix/bin/tntk"),
         "-P", str(Path.home() / "newton-dev/ntk-platform-files"),
         "-c", "proof.nprj"],
        cwd=directory, env=env, check=True, stdout=subprocess.DEVNULL,
    )
    package = directory / "proof.pkg"
    if package.stat().st_size < 318_276 or package.stat().st_size > 524_288:
        raise RuntimeError(f"proof package size {package.stat().st_size} is outside the large-loader test range")
    return package


def install_loader():
    if ns(f'begin local p:=GetPkgRef("{LOADER_ID}",GetDefaultStore()); if p then true else nil; end') == "TRUE":
        return
    subprocess.run(["make", "-C", str(ROOT / "examples/harness-loader"), "all"], check=True)
    mounts = json.loads(run("podman", "inspect", CONTAINER, "--format", "{{json .Mounts}}").stdout)
    package_root = next(Path(m["Source"]) for m in mounts if m["Destination"] == "/packages")
    mounted = package_root / "harness-loader/harness-loader.pkg"
    backup = mounted.read_bytes()
    try:
        mounted.write_bytes((ROOT / "examples/harness-loader/harness-loader.pkg").read_bytes())
        command = b"install /packages/harness-loader/harness-loader.pkg\n"
        sender = "import socket,sys;s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect('/state/einstein-control.sock');s.sendall(sys.stdin.buffer.read());print(s.recv(4096).decode().strip())"
        reply = subprocess.run(
            ["podman", "exec", "-i", CONTAINER, "python3", "-c", sender],
            input=command, capture_output=True, check=True,
        ).stdout.decode().strip()
        if reply != "queued":
            raise RuntimeError(f"loader install was not queued: {reply}")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if ns(f'begin local p:=GetPkgRef("{LOADER_ID}",GetDefaultStore()); if p then true else nil; end') == "TRUE":
                return
            time.sleep(0.5)
        raise RuntimeError("loader package did not appear within 30 seconds")
    finally:
        mounted.write_bytes(backup)


def main():
    addresses = run("ip", "-o", "addr", "show").stdout
    if "10.42.0.1/24" not in addresses:
        raise SystemExit("10.42.0.1 is missing; run: sudo ap/emulator-only.sh")

    install_loader()
    ns(f'begin GetRoot().{LOADER_SYMBOL}:Open(); "opened"; end')

    identity = f"WifiProof{uuid.uuid4().hex[:12]}:jbfly"
    filename = f"proof-{uuid.uuid4().hex[:8]}.pkg"
    staging = ROOT / "runtime/staging/hardware"
    staging.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temporary:
        package = build_large_proof(Path(temporary), identity)
        staged = staging / filename
        shutil.copy2(package, staged)
        server = subprocess.Popen(
            ["python3", str(ROOT / "runtime/dual_send.py")],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            time.sleep(0.5)
            if server.poll() is not None:
                raise RuntimeError(server.stdout.read())
            ns(
                f'begin local v:=GetRoot().{LOADER_SYMBOL}; v.packageName:="{filename}"; '
                'v.attempt:=1; v:TryFetch(); "started"; end'
            )
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                installed = ns(
                    f'begin local p:=GetPkgRef("{identity}",GetDefaultStore()); if p then GetPkgRefInfo(p).size else nil; end'
                )
                if installed != "NIL":
                    break
                status = ns(f'GetRoot().{LOADER_SYMBOL}.lastStatus')
                if "failed" in status.lower() or status.startswith('"X'):
                    raise RuntimeError(f"loader failed: {status}")
                time.sleep(1)
            else:
                raise RuntimeError("loader did not install the proof package within 120 seconds")

            result = ns(f'begin GetRoot().|{identity}|:Open(); GetRoot().|{identity}|:Proof(); end')
            if result != '"wifi-install-ok"':
                raise RuntimeError(f"installed package did not run: {result}")
            print(f"PASS: installed and ran {filename} ({package.stat().st_size} bytes, identity {identity})")
        finally:
            server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
            staged.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
