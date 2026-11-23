"""Serve the GUI in a web browser (no pywebview needed).

Useful for front-end development, for machines without a desktop, or over
SSH with port forwarding::

    ssh -L 8765:127.0.0.1:8765 pi      # on the Mac
    python -m myfancyqr.gui --browser --no-open   # on the remote machine

Only binds to 127.0.0.1. The JavaScript calls ``POST /api/<method>`` with a
JSON array of arguments; only the methods listed in :mod:`.api` are allowed.
"""

from __future__ import annotations

import json
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .api import Api, callable_from_js

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_BODY = 20 * 1024 * 1024  # logos are uploaded as data URLs


class _Handler(SimpleHTTPRequestHandler):
    api: Api

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):  # noqa: N802 - http.server naming
        if self.path in ("/", "/index.html"):
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/index.html?mode=browser")
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):  # noqa: N802 - http.server naming
        if not self.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        name = self.path[len("/api/"):].split("?", 1)[0]
        if not callable_from_js(name):
            self.send_error(HTTPStatus.NOT_FOUND, "unknown API method")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            args = json.loads(self.rfile.read(length) or b"[]")
            if not isinstance(args, list):
                raise ValueError("arguments must be a JSON array")
            result = getattr(self.api, name)(*args)
        except Exception as exc:  # noqa: BLE001
            result = {"ok": False, "error": str(exc)}
        body = json.dumps(result).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(port: int = 8765, api: Api | None = None) -> ThreadingHTTPServer:
    handler = partial(type("Handler", (_Handler,), {"api": api or Api(browser_mode=True)}),
                      directory=str(STATIC_DIR))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve(port: int = 8765, open_browser: bool = True) -> int:
    server = make_server(port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"MyFancyQR GUI running at {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
