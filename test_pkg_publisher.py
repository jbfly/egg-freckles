#!/usr/bin/env python3
"""Small self-check for pkg_publisher.py."""

from __future__ import annotations

import http.client
import tempfile
import threading
import unittest
from pathlib import Path

import pkg_publisher


class PublisherTest(unittest.TestCase):
    def test_page_package_headers_and_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "examples" / "harness-client" / "harness-client.pkg"
            package_path.parent.mkdir(parents=True)
            package_path.write_bytes(b"first package")

            with pkg_publisher.make_server("127.0.0.1", 0, package_path) as server:
                port = server.server_address[1]
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    status, headers, body, version = self.fetch(port, "/")
                    self.assertEqual(status, 200)
                    self.assertEqual(version, 10)
                    self.assertEqual(body, pkg_publisher.PAGE_BODY)
                    self.assertEqual(headers["Content-Length"], str(len(body)))
                    self.assertEqual(headers["Connection"], "close")
                    self.assertIn("text/html", headers["Content-Type"])

                    status, headers, body, version = self.fetch(port, "/status")
                    self.assertEqual(status, 200)
                    self.assertEqual(version, 10)
                    self.assertEqual(body, pkg_publisher.STATUS_BODY)
                    self.assertEqual(headers["Content-Length"], str(len(body)))
                    self.assertEqual(headers["Connection"], "close")
                    self.assertEqual(headers["Content-Type"], "text/plain; charset=us-ascii")

                    status, headers, body, _ = self.fetch(port, "/harness-client.pkg")
                    self.assertEqual(status, 200)
                    self.assertEqual(body, b"first package")
                    self.assertEqual(headers["Content-Length"], str(len(body)))
                    self.assertEqual(
                        headers["Content-Type"],
                        "application/x-newton-compatible-pkg",
                    )

                    package_path.write_bytes(b"second package")
                    status, headers, body, _ = self.fetch(port, "/harness-client.pkg")
                    self.assertEqual(status, 200)
                    self.assertEqual(body, b"second package")
                    self.assertEqual(headers["Content-Length"], str(len(body)))

                    status, headers, body, _ = self.fetch(port, "/../../etc/passwd")
                    self.assertEqual(status, 404)
                    self.assertEqual(body, b"not found\n")
                    self.assertEqual(headers["Content-Length"], str(len(body)))
                finally:
                    server.shutdown()
                    thread.join()

    def test_ink_counts(self) -> None:
        with pkg_publisher.make_server("127.0.0.1", 0) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                body = b"NSI1 288 320 2\r\nS 3 10 20 1 2 -1 -2\r\nS 1 30 40\r\n"
                status, headers, response, version = self.fetch(port, "/ink", "POST", body)
                self.assertEqual((status, version, response), (200, 10, b"Strokes: 2 Points: 4\r\n"))
                self.assertEqual(headers["Content-Type"], "text/plain; charset=us-ascii")
            finally:
                server.shutdown()
                thread.join()

    @staticmethod
    def fetch(
        port: int, path: str, method: str = "GET", body: bytes | None = None
    ) -> tuple[int, http.client.HTTPMessage, bytes, int]:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            conn.request(method, path, body=body)
            response = conn.getresponse()
            body = response.read()
            return response.status, response.headers, body, response.version
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
