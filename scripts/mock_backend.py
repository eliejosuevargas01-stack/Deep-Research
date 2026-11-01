#!/usr/bin/env python3
"""Servidor HTTP mock leve para suportar auditoria frontend sem depender de LLMs externas."""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

START_TIME = time.time()

SESSION_DATA = {
    "authenticated": True,
    "mode": "local",
    "preferences": {
        "n_pontos": 3,
        "personas": ["historiador", "visionario", "cetico", "futurista"],
        "execution_mode": "balanceado",
        "recencia": "todos"
    }
}

class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silenciar logs para não poluir terminal
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-api-key')
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        if self.path in ('/health', '/health/'):
            self.wfile.write(json.dumps({"status": "healthy"}).encode('utf-8'))
        elif self.path.startswith('/app/session'):
            self.wfile.write(json.dumps(SESSION_DATA).encode('utf-8'))
        elif '/sources' in self.path:
            self.wfile.write(json.dumps({
                "id_pesquisa": "harness-0001",
                "status": "completo",
                "total_consultadas": 5,
                "total_utilizadas": 3,
                "total_nao_utilizadas": 2,
                "consultadas": [],
                "utilizadas": [],
                "nao_utilizadas": []
            }).encode('utf-8'))
        elif '/status' in self.path:
            elapsed = int(time.time() - START_TIME)
            tokens_total = 12500 + (elapsed % 300) * 850
            prompt = max(1000, tokens_total - 6200)
            completion = tokens_total - prompt
            created_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(START_TIME))
            self.wfile.write(json.dumps({
                "status_pipeline": "buscando",
                "criado_em": created_iso,
                "tokens_prompt": prompt,
                "tokens_completion": completion,
                "tokens_total": tokens_total
            }).encode('utf-8'))
        else:
            self.wfile.write(json.dumps({"ok": True}).encode('utf-8'))

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "id_pesquisa": "harness-0001"}).encode('utf-8'))

def run():
    server = HTTPServer(('127.0.0.1', 8010), MockHandler)
    server.serve_forever()

if __name__ == '__main__':
    run()
