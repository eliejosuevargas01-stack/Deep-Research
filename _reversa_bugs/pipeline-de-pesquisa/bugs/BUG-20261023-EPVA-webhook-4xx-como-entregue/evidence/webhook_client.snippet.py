# Evidencia 1 - trecho literal de app/services/webhook_client.py linhas 137 a 162
# Extraido pelo orquestrador em 2026-10-23 (linhas confirmadas por `grep -n ""`).
# O bloco abaixo PROVA o defeito: apenas 429 e 5xx disparam raise_for_status (retry).
# Qualquer outro status fora de 2xx (ex.: 400, 401, 403, 404, 422) cai direto em
# status_result = "entregue".

        for attempt in range(1, max_attempts + 1):
            try:
                res = await self._client.post(
                    url=url,
                    content=raw_bytes,
                    headers=headers,
                )
                last_status_code = res.status_code

                if res.status_code in (429, 500, 502, 503, 504) or res.is_server_error:
                    res.raise_for_status()

                # Entrega confirmada com sucesso (código 2xx)
                status_result = "entregue"
                await self._update_repo_status(
                    repo=repo,
                    id_pesquisa=id_pesquisa,
                    status=status_result,
                    resposta=res.text,
                )
                return {
                    "status": status_result,
                    "http_status_code": res.status_code,
                    "tentativas": attempt,
                    "resposta": res.text,
                }
