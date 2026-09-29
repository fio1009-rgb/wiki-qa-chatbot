from http.server import BaseHTTPRequestHandler
import os
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from app import ERROR_MESSAGE, PAGE_HTML, format_sse, qa_service, stream_answer


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/stream":
            self._stream(parse_qs(parsed.query).get("q", [""])[0])
            return
        self._send_html(PAGE_HTML)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        try:
            import json
            payload = json.loads(self.rfile.read(length) or b"{}")
            question = payload.get("question", "") if isinstance(payload, dict) else ""
            self._send_json(200, qa_service.answer(question))
        except Exception:
            self._send_json(500, {"error": "server_error"})

    def _stream(self, question):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            result = qa_service.answer(question)
            for chunk in str(result.get("answer", "")).split():
                self.wfile.write(format_sse("chunk", {"text": chunk + " "}).encode())
            self.wfile.write(format_sse("sources", {"sources": result.get("sources", [])}).encode())
            self.wfile.write(format_sse("done", {"metrics": result.get("metrics", {})}).encode())
        except Exception:
            self.wfile.write(format_sse("app_error", {"message": ERROR_MESSAGE}).encode())

    def _send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, data):
        import json
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
