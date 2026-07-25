#!/usr/bin/env python3
"""Small HTTP control plane for Einstein running on a private X display."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
KEY_RE = re.compile(r"^[A-Za-z0-9_+:-]{1,64}$")


class ControlError(RuntimeError):
    pass


class EinsteinControl:
    def __init__(
        self,
        *,
        display: str | None = None,
        screen_width: int = 320,
        screen_height: int = 480,
        screen_top: int = 78,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        self.display = display or os.environ.get("DISPLAY", ":99")
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.screen_top = screen_top
        self.runner = runner
        self.lock = threading.Lock()

    def _run(self, args: list[str]) -> bytes:
        env = dict(os.environ, DISPLAY=self.display)
        result = self.runner(
            args,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", "replace").strip()
            raise ControlError(message or f"{args[0]} exited {result.returncode}")
        return result.stdout

    def window_id(self, *, topmost: bool = False) -> str:
        output = self._run(
            [
                "xdotool",
                "search",
                "--onlyvisible",
                "--name",
                ".*" if topmost else "^Einstein$",
            ]
        )
        ids = output.decode("ascii", "replace").split()
        if not ids:
            raise ControlError("Einstein window is not ready")
        return ids[-1]

    def window_geometry(self, window_id: str | None = None) -> dict[str, int]:
        window_id = window_id or self.window_id()
        output = self._run(
            ["xdotool", "getwindowgeometry", "--shell", window_id]
        ).decode("ascii", "replace")
        values: dict[str, int] = {}
        for raw in output.splitlines():
            key, separator, value = raw.partition("=")
            if separator and key in {"X", "Y", "WIDTH", "HEIGHT", "SCREEN"}:
                values[key.lower()] = int(value)
        if "width" not in values or "height" not in values:
            raise ControlError("could not read Einstein window geometry")
        return values

    def status(self) -> dict[str, Any]:
        try:
            window_id = self.window_id()
            geometry = self.window_geometry(window_id)
        except ControlError as exc:
            return {"status": "starting", "detail": str(exc)}
        return {
            "status": "ready",
            "window_id": int(window_id),
            "display": self.display,
            "newton_screen": {
                "width": self.screen_width,
                "height": self.screen_height,
                "window_offset": {"x": 0, "y": self.screen_top},
            },
            "window": geometry,
        }

    def screenshot(self, *, newton_only: bool) -> bytes:
        window_id = self.window_id(topmost=not newton_only)
        args = ["import", "-display", self.display, "-window", window_id]
        if newton_only:
            args += [
                "-crop",
                (
                    f"{self.screen_width}x{self.screen_height}"
                    f"+0+{self.screen_top}"
                ),
                "+repage",
            ]
        args.append("png:-")
        output = self._run(args)
        if not output.startswith(PNG_MAGIC):
            raise ControlError("screen capture did not return a PNG")
        return output

    @staticmethod
    def _coordinate(value: Any, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
        return value

    def tap(self, x: Any, y: Any, *, newton_only: bool) -> None:
        x = self._coordinate(x, "x")
        y = self._coordinate(y, "y")
        window_id = self.window_id(topmost=not newton_only)
        if newton_only:
            width = self.screen_width
            height = self.screen_height
            target_y = y + self.screen_top
        else:
            geometry = self.window_geometry(window_id)
            width = geometry["width"]
            height = geometry["height"]
            target_y = y
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError(
                f"tap is outside the {'Newton screen' if newton_only else 'window'}"
            )
        with self.lock:
            self._run(
                [
                    "xdotool",
                    "mousemove",
                    "--window",
                    window_id,
                    str(x),
                    str(target_y),
                    "click",
                    "1",
                ]
            )

    def drag(
        self,
        start_x: Any,
        start_y: Any,
        end_x: Any,
        end_y: Any,
        *,
        duration: Any = 0.5,
        steps: Any = 20,
    ) -> None:
        start_x = self._coordinate(start_x, "start_x")
        start_y = self._coordinate(start_y, "start_y")
        end_x = self._coordinate(end_x, "end_x")
        end_y = self._coordinate(end_y, "end_y")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ValueError("duration must be a number")
        if not 0 <= duration <= 60:
            raise ValueError("duration must be between 0 and 60 seconds")
        if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 1000:
            raise ValueError("steps must be an integer between 1 and 1000")
        for name, x, y in (
            ("start", start_x, start_y),
            ("end", end_x, end_y),
        ):
            if not 0 <= x < self.screen_width or not 0 <= y < self.screen_height:
                raise ValueError(f"drag {name} is outside the Newton screen")

        window_id = self.window_id()
        args = [
            "xdotool",
            "mousemove",
            "--window",
            window_id,
            str(start_x),
            str(start_y + self.screen_top),
            "mousedown",
            "1",
        ]
        for step in range(1, steps + 1):
            x = round(start_x + (end_x - start_x) * step / steps)
            y = round(start_y + (end_y - start_y) * step / steps)
            args += [
                "mousemove",
                "--window",
                window_id,
                str(x),
                str(y + self.screen_top),
            ]
            if duration:
                args += ["sleep", str(duration / steps)]
        args += ["mouseup", "1"]
        with self.lock:
            self._run(args)

    def type_text(self, text: Any) -> None:
        if not isinstance(text, str) or not text or len(text) > 4096:
            raise ValueError("text must contain 1 to 4096 characters")
        window_id = self.window_id(topmost=True)
        with self.lock:
            self._run(
                [
                    "xdotool",
                    "type",
                    "--window",
                    window_id,
                    "--clearmodifiers",
                    "--delay",
                    "20",
                    "--",
                    text,
                ]
            )

    def key(self, key: Any) -> None:
        if not isinstance(key, str) or not KEY_RE.fullmatch(key):
            raise ValueError("key contains unsupported characters")
        window_id = self.window_id(topmost=True)
        with self.lock:
            self._run(
                [
                    "xdotool",
                    "key",
                    "--window",
                    window_id,
                    "--clearmodifiers",
                    key,
                ]
            )


class ControlHandler(BaseHTTPRequestHandler):
    server_version = "newton-emulator-control/1"

    @property
    def control(self) -> EinsteinControl:
        return self.server.control  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[emulator-control] {self.address_string()} {format % args}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_png(self, body: bytes) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length <= 0 or length > 65536:
            raise ValueError("JSON body must contain 1 to 65536 bytes")
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid JSON body") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def do_GET(self) -> None:
        try:
            if self.path == "/health":
                status = self.control.status()
                code = (
                    HTTPStatus.OK
                    if status["status"] == "ready"
                    else HTTPStatus.SERVICE_UNAVAILABLE
                )
                self._send_json(code, status)
            elif self.path == "/screen.png":
                self._send_png(self.control.screenshot(newton_only=True))
            elif self.path == "/window.png":
                self._send_png(self.control.screenshot(newton_only=False))
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except ControlError as exc:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
            if self.path == "/tap":
                self.control.tap(payload.get("x"), payload.get("y"), newton_only=True)
            elif self.path == "/window/tap":
                self.control.tap(payload.get("x"), payload.get("y"), newton_only=False)
            elif self.path == "/drag":
                self.control.drag(
                    payload.get("start_x"),
                    payload.get("start_y"),
                    payload.get("end_x"),
                    payload.get("end_y"),
                    duration=payload.get("duration", 0.5),
                    steps=payload.get("steps", 20),
                )
            elif self.path == "/text":
                self.control.type_text(payload.get("text"))
            elif self.path == "/key":
                self.control.key(payload.get("key"))
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            self._send_json(HTTPStatus.OK, {"ok": True})
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except ControlError as exc:
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    control = EinsteinControl()
    server = ThreadingHTTPServer((args.host, args.port), ControlHandler)
    server.control = control  # type: ignore[attr-defined]
    print(
        f"[emulator-control] listening on {args.host}:{args.port}, "
        f"display {control.display}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
