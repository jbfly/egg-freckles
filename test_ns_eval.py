#!/usr/bin/env python3

import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from runtime import ns_eval


class FakePodman:
    def __init__(self) -> None:
        self.token = b"container-id 2026-08-07T12:00:00Z\n"
        self.read_started = threading.Event()
        self.release_read = threading.Event()
        self.block_read = False
        self.result = b"4\n"

    def __call__(self, args, **kwargs):
        if args[1] == "inspect":
            return subprocess.CompletedProcess(args, 0, self.token, b"")
        if args[-2:] == ["cat", ns_eval.RESULT]:
            if self.block_read:
                self.read_started.set()
                self.release_read.wait(2)
            return subprocess.CompletedProcess(args, 0 if self.result else 1, self.result, b"")
        return subprocess.CompletedProcess(args, 0, b"queued\n", b"")


class NsEvalGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.guard_patch = mock.patch.object(ns_eval, "GUARD_ROOT", Path(self.temporary.name))
        self.guard_patch.start()
        self.podman = FakePodman()
        self.run_patch = mock.patch.object(ns_eval.subprocess, "run", self.podman)
        self.run_patch.start()

    def tearDown(self) -> None:
        self.run_patch.stop()
        self.guard_patch.stop()
        self.temporary.cleanup()

    def test_rejects_concurrent_eval(self) -> None:
        self.podman.block_read = True
        result = []
        worker = threading.Thread(
            target=lambda: result.append(ns_eval.run("emulator", "2+2", 1))
        )
        worker.start()
        self.assertTrue(self.podman.read_started.wait(1))

        with self.assertRaisesRegex(SystemExit, "already in flight"):
            ns_eval.run("emulator", "3+3", 1)

        self.podman.release_read.set()
        worker.join(2)
        self.assertEqual(result, ["4"])

    def test_timeout_poison_clears_only_after_restart(self) -> None:
        self.podman.result = b""
        with self.assertRaisesRegex(SystemExit, "now POISONED"):
            ns_eval.run("emulator", "slow()", 0.001)

        with self.assertRaisesRegex(SystemExit, "restart this isolated emulator instance"):
            ns_eval.run("emulator", "2+2", 1)

        self.podman.token = b"container-id 2026-08-07T12:01:00Z\n"
        self.podman.result = b"4\n"
        self.assertEqual(ns_eval.run("emulator", "2+2", 1), "4")


if __name__ == "__main__":
    unittest.main()
