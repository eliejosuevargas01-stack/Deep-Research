"""POST HTTP real do webhook (RF08/RNF01): servidor local com retentativa e erro final.

`enviar_callback` usa httpx com 5 tentativas e espera crescente; este teste sobe um
HTTPServer real em thread efêmera para provar o fio POST JSON, o Content-Type, o
timeout configurável e as retentativas 500→200. Nada de mock de rede.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from webhook import enviar_callback


class _Gravador(BaseHTTPRequestHandler):
    # Configurado por teste via atributos de classe (servidor é efêmero por teste).
    respostas: list[int] = [200]
    pedidos: list[dict] = []

    def log_message(self, format, *args):  # silencia o stderr do servidor
        pass

    def do_POST(self):
        corpo = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        type(self).pedidos.append(
            {
                "path": self.path,
                "content_type": self.headers.get("Content-Type"),
                "body": json.loads(corpo.decode("utf-8")),
            }
        )
        tentativa = len(type(self).pedidos)
        status = type(self).respostas[tentativa - 1] if tentativa <= len(type(self).respostas) else 200
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')


@pytest.fixture
def servidor():
    _Gravador.pedidos = []
    _Gravador.respostas = [200]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Gravador)
    fio = threading.Thread(target=httpd.serve_forever, daemon=True)
    fio.start()
    yield httpd, f"http://127.0.0.1:{httpd.server_address[1]}/cb"
    httpd.shutdown()
    fio.join(timeout=5)
    httpd.server_close()


def _sem_espera(_segundos: float) -> None:
    return None


def test_post_json_com_content_type_e_timeout(servidor):
    _, url = servidor
    payload = {"research_id": "r1", "relatorio_final": "texto"}

    enviar_callback(url, payload, timeout_s=5, espera=_sem_espera)

    assert len(_Gravador.pedidos) == 1
    pedido = _Gravador.pedidos[0]
    assert pedido["content_type"] == "application/json"
    assert pedido["body"] == payload


def test_retenta_apos_500_e_vence_na_segunda(servidor):
    _Gravador.respostas = [500, 200]
    _, url = servidor

    enviar_callback(url, {"research_id": "r2"}, timeout_s=5, espera=_sem_espera)  # não deve levantar

    assert len(_Gravador.pedidos) == 2
    assert _Gravador.pedidos[0]["body"] == _Gravador.pedidos[1]["body"]


def test_retenta_500_500_e_vence_na_terceira(servidor):
    _Gravador.respostas = [500, 500, 200]
    _, url = servidor
    esperas: list[float] = []

    enviar_callback(url, {"research_id": "r4"}, timeout_s=5, espera=esperas.append)

    assert len(_Gravador.pedidos) == 3
    assert esperas == [1, 2]


def test_4xx_nao_repete(servidor):
    _Gravador.respostas = [400]
    _, url = servidor
    esperas: list[float] = []

    with pytest.raises(RuntimeError, match="webhook"):
        enviar_callback(url, {"research_id": "r5"}, timeout_s=5, espera=esperas.append)

    assert len(_Gravador.pedidos) == 1
    assert esperas == []


def test_falha_quando_todas_as_tentativas_falham(servidor):
    _Gravador.respostas = [500, 500, 500, 500, 500]
    _, url = servidor
    esperas: list[float] = []

    with pytest.raises(RuntimeError, match="webhook"):
        enviar_callback(url, {"research_id": "r3"}, timeout_s=5, espera=esperas.append)

    assert len(_Gravador.pedidos) == 5
    assert esperas == [1, 2, 4, 8]
