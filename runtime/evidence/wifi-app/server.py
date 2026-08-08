#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone

BODY = b"WIFI ROUND TRIP WORKS"

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def do_GET(self):
        print(f"{datetime.now(timezone.utc).isoformat()} peer={self.client_address[0]}:{self.client_address[1]} request={self.requestline!r}", flush=True)
        if self.path != "/wifi-proof":
            self.send_error(404)
            return
        self.send_response_only(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)
        self.wfile.flush()
        print(f"{datetime.now(timezone.utc).isoformat()} sent={BODY!r}", flush=True)

    def log_message(self, format, *args):
        pass

HTTPServer(("10.42.0.1", 18099), Handler).serve_forever()
