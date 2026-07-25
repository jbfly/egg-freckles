#!/usr/bin/env python3

import subprocess
import unittest

from emulator.control import ControlError, EinsteinControl, PNG_MAGIC


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        if args[:2] == ["xdotool", "search"]:
            ids = b"42\n99\n" if args[-1] == ".*" else b"42\n"
            return subprocess.CompletedProcess(args, 0, ids, b"")
        if args[:2] == ["xdotool", "getwindowgeometry"]:
            return subprocess.CompletedProcess(
                args, 0, b"X=0\nY=0\nWIDTH=320\nHEIGHT=558\nSCREEN=0\n", b""
            )
        if args[0] == "import":
            return subprocess.CompletedProcess(args, 0, PNG_MAGIC + b"test", b"")
        return subprocess.CompletedProcess(args, 0, b"", b"")


class EinsteinControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = FakeRunner()
        self.control = EinsteinControl(runner=self.runner)

    def test_status_reports_fixed_newton_geometry(self) -> None:
        status = self.control.status()
        self.assertEqual(status["status"], "ready")
        self.assertEqual(status["newton_screen"]["width"], 320)
        self.assertEqual(status["newton_screen"]["height"], 480)
        self.assertEqual(status["newton_screen"]["window_offset"]["y"], 78)

    def test_newton_tap_adds_toolbar_offset(self) -> None:
        self.control.tap(12, 34, newton_only=True)
        self.assertEqual(
            self.runner.calls[-1],
            [
                "xdotool",
                "mousemove",
                "--window",
                "42",
                "12",
                "112",
                "click",
                "1",
            ],
        )

    def test_newton_tap_rejects_out_of_bounds(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the Newton screen"):
            self.control.tap(320, 0, newton_only=True)

    def test_drag_presses_moves_and_releases_with_toolbar_offset(self) -> None:
        self.control.drag(10, 20, 30, 40, duration=0, steps=2)
        self.assertEqual(
            self.runner.calls[-1],
            [
                "xdotool",
                "mousemove", "--window", "42", "10", "98",
                "mousedown", "1",
                "mousemove", "--window", "42", "20", "108",
                "mousemove", "--window", "42", "30", "118",
                "mouseup", "1",
            ],
        )

    def test_window_tap_uses_uncropped_coordinates(self) -> None:
        self.control.tap(319, 557, newton_only=False)
        self.assertEqual(self.runner.calls[-1][3], "99")
        self.assertEqual(self.runner.calls[-1][4:6], ["319", "557"])

    def test_screenshot_requests_the_newton_crop(self) -> None:
        image = self.control.screenshot(newton_only=True)
        self.assertTrue(image.startswith(PNG_MAGIC))
        self.assertIn("320x480+0+78", self.runner.calls[-1])

    def test_command_failure_is_reported(self) -> None:
        def fail(args, **kwargs):
            return subprocess.CompletedProcess(args, 1, b"", b"not running")

        control = EinsteinControl(runner=fail)
        with self.assertRaisesRegex(ControlError, "not running"):
            control.window_id()


if __name__ == "__main__":
    unittest.main()
