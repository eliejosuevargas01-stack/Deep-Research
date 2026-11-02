#!/usr/bin/env python3
"""Painel visual (estilo board) das capturas de chamadas LLM.

Serve uma página única + API JSON sobre o diretório de captura:

    python scripts/capture_board.py --dir data/llm-capture --port 8011

Rotas:
    /                     board (HTML/JS/CSS inline)
    /api/index            metadados de todas as chamadas (leve)
    /api/call/<arquivo>   JSON completo daquela chamada
"""

from __future__ import annotations

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote


class Handler(BaseHTTPRequestHandler):
    capture_dir = "."

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(self.path.split("?")[0])
        if path == "/":
            html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture_board.html")
            with open(html_path, "rb") as fh:
                self._send(200, fh.read(), "text/html; charset=utf-8")
            return
        if path == "/api/index":
            self._send(200, json.dumps(self._index()).encode("utf-8"), "application/json")
            return
        if path.startswith("/api/call/"):
            name = os.path.basename(path[len("/api/call/"):])
            full = os.path.join(self.capture_dir, name)
            if not name or not os.path.isfile(full):
                self._send(404, b'{"error":"not found"}', "application/json")
                return
            with open(full, "rb") as fh:
                self._send(200, fh.read(), "application/json")
            return
        self._send(404, b'{"error":"not found"}', "application/json")

    def _index(self):
        out = []
        for name in sorted(os.listdir(self.capture_dir)):
            if not name.endswith(".json") or name.startswith("."):
                continue
            try:
                with open(os.path.join(self.capture_dir, name), encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                continue
            req = data.get("request") or {}
            resp = data.get("response") or {}
            usage = resp.get("usage") or {}
            msgs = req.get("messages") or []
            system = " ".join(
                str(m.get("content")) for m in msgs if isinstance(m, dict) and m.get("role") == "system"
            )
            out.append(
                {
                    "file": name,
                    "captured_at": data.get("captured_at"),
                    "status": data.get("status"),
                    "model": req.get("model"),
                    "prompt_id": req.get("prompt_id"),
                    "system": system[:400],
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "preview": (resp.get("content_final") or "")[:700],
                    "error": data.get("error"),
                }
            )
        return out

    def log_message(self, fmt, *args):  # silencia log por request
        return


def main() -> int:
    ap = argparse.ArgumentParser(description="Board visual das capturas LLM.")
    ap.add_argument("--dir", default=os.environ.get("DR_LLM_CAPTURE_DIR") or "data/llm-capture")
    ap.add_argument("--port", type=int, default=8011)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    Handler.capture_dir = os.path.abspath(args.dir)
    if not os.path.isdir(Handler.capture_dir):
        raise SystemExit(f"diretório inexistente: {Handler.capture_dir}")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"board em http://{args.host}:{args.port}  (dir={Handler.capture_dir})")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
