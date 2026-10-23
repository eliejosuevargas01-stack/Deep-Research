"""Reproducao isolada do defeito BUG-20261023-EPVA.

Roda sem banco e sem framework: simula um receptor que responde HTTP 404
(rejeicao do cliente) e verifica o status que o WebhookClient grava.

Uso: python reproduce.py   (a partir da raiz do projeto)
"""
import asyncio
import httpx
from app.services.webhook_client import WebhookClient


class HandlerRejeita(httpx.AsyncBaseTransport):
    """Servidor simulado que SEMPRE rejeita com 404 Not Found."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text='{"erro":"recurso nao encontrado"}')


async def main() -> None:
    async with WebhookClient(
        secret="segredo-de-teste",
        transport=HandlerRejeita(),
    ) as client:
        resultado = await client.send_webhook(
            url="https://receptor.exemplo.invalido/hook",
            payload={"evento": "research.completed", "id_pesquisa": "P-1"},
            id_pesquisa="P-1",
        )

    print("retorno do cliente:", resultado)
    esperado_por_espec = "falha_definitiva"
    observado = resultado["status"]
    print(f"http_status_code observado: {resultado['http_status_code']}")
    print(f"status gravado: {observado}")

    assert resultado["http_status_code"] == 404, "esperava o 404 simulado"
    assert observado == esperado_por_espec, (
        f"DEFEITO CONFIRMADO: receptor respondeu 404 (rejeitou o evento) "
        f"mas o cliente gravou '{observado}' em vez de '{esperado_por_espec}'."
    )
    print("OK: 404 tratado como falha.")


if __name__ == "__main__":
    asyncio.run(main())
