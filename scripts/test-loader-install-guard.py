#!/usr/bin/env python3
"""Require duplicate ZC40 completion callbacks to schedule one install."""
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTAINER = os.environ.get("NEWTON_CONTAINER", "newton-harness_emulator_1")
SYMBOL = "|-HarnessLoaderZC40:jbfly|"


def ns(source):
    return subprocess.run(
        [str(ROOT / "runtime/ns_eval.py"), source, "--container", CONTAINER],
        text=True, capture_output=True, check=True,
    ).stdout.strip()


subprocess.run(
    [str(ROOT / "scripts/install-and-launch.sh"),
     "/packages/harness-loader/harness-loader.pkg", "-HarnessLoaderZC40:jbfly"],
    check=True,
)
output = ns(
    f"begin local v:=GetRoot().{SYMBOL}; "
    "v.installQueued:=nil; v.installCalls:=0; "
    "v.InstallBinaryLater:=func(binary) self.installCalls:=self.installCalls+1; "
    "v:InputReceived(); v:InputReceived(); v.installCalls; end"
)
result = output.splitlines()[-1]
if result != "1":
    raise SystemExit(f"FAIL: duplicate InputReceived scheduled {result} installs")
print("PASS: duplicate InputReceived scheduled one install")
