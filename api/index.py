from http.server import BaseHTTPRequestHandler
import os
import sys
import json
import urllib.request
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from app import ERROR_MESSAGE, PAGE_HTML, format_sse, qa_service, stream_answer


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/stream" or parse_qs(parsed.query).get("path") == ["stream"]:
            self._stream(parse_qs(parsed.query).get("q", [""])[0])
            return
        self._send_html(PAGE_HTML)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/feedback" or parse_qs(parsed.query).get("path") == ["feedback"]:
            self._save_feedback()
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            import json
            payload = json.loads(self.rfile.read(length) or b"{}")
            question = payload.get("question", "") if isinstance(payload, dict) else ""
            self._send_json(200, qa_service.answer(question))
        except Exception:
            self._send_json(500, {"error": "server_error"})

    def _save_feedback(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        base = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not base or not key or payload.get("rating") not in ("good", "bad"):
            self._send_json(503, {"error": "feedback_storage_not_configured"})
            return
        data = json.dumps({
            "question": str(payload.get("question", "")),
            "answer": str(payload.get("answer", "")),
            "rating": payload["rating"],
            "source": str(payload.get("source", "")),
        }).encode("utf-8")
        request = urllib.request.Request(
            base + "/rest/v1/feedback",
            data=data,
            headers={"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json", "Prefer": "return=minimal"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=10).close()
            self._send_json(201, {"ok": True})
        except Exception:
            self._send_json(502, {"error": "feedback_storage_failed"})

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
