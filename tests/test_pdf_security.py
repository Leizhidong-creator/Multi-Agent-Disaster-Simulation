from __future__ import annotations

import base64
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.engine.pdf_export import markdown_to_pdf


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_pdf_report_does_not_fetch_resources_from_untrusted_markup() -> None:
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG)))
            self.end_headers()
            self.wfile.write(PNG)

        def log_message(self, *args: object) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        markdown_to_pdf(
            f'<img src="http://127.0.0.1:{port}/probe.png" width="1" height="1"/>'
        )
    finally:
        server.shutdown()
        thread.join()

    assert requests == []
