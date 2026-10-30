"""Testes de integração para a interface web integrada, sessão local de navegador e segurança.

Valida:
1. Emissão de sessão e cookie HttpOnly SameSite=Strict em GET /app/session para clientes locais elegíveis.
2. Servir o frontend React compilado em / e assets em /assets/ com 404 estrito em assets ausentes.
3. Rejeição de bootstrap de sessão por clientes remotos, Origin malicioso ou Host adulterado.
4. Autenticação transparente sem chave de API no cliente navegador mesmo com API_SECRET_KEY ativa.
5. Rejeição com 401 quando nem chave externa nem cookie válido forem informados.
6. Rejeição de tokens adulterados ou expirados.
7. Proteção CSRF / mesma origem em requisições mutantes autenticadas via cookie.
"""

import os
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.ui_session import (
    COOKIE_NAME,
    create_session_token,
    verify_session_token,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_integration():
    """Garante ambiente de teste isolado e banco inicializado."""
    from app.main import _setup_integration_test_env
    _setup_integration_test_env()
    from app.db.init_db import init_db
    from app.db.session import get_engine
    await init_db(get_engine())


@pytest.mark.asyncio
async def test_fresh_session_issuance_for_local_client(monkeypatch: pytest.MonkeyPatch):
    """GET /app/session emite cookie HttpOnly SameSite=Strict e retorna preferências padrão."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-externo-forte-1234")

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52341)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.get("/app/session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["mode"] == "local"
        assert "preferences" in data
        assert isinstance(data["preferences"]["n_pontos"], int)
        assert data["preferences"]["n_pontos"] >= 1
        assert isinstance(data["preferences"]["personas"], list)
        assert len(data["preferences"]["personas"]) > 0

        # Verifica cookie de sessão nos headers
        set_cookie = resp.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie
        assert "httponly" in set_cookie.lower()
        assert "samesite=strict" in set_cookie.lower()

        # Valida que o token do cookie é criptograficamente íntegro
        cookie_val = resp.cookies.get(COOKIE_NAME)
        assert cookie_val is not None
        assert verify_session_token(cookie_val) is True


@pytest.mark.asyncio
async def test_spa_root_serves_html_and_sets_cookie_for_local_client():
    """GET / serve o index.html compilado da interface SPA e anexa cookie de sessão."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52342)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        body_text = resp.text.lower()
        assert "<!doctype html" in body_text or "<html" in body_text

        # Cookie de sessão é emitido na raiz para navegador local elegível
        set_cookie = resp.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie


@pytest.mark.asyncio
async def test_static_assets_served_same_origin():
    """Arquivos em /assets/{file_path} são servidos com sucesso a partir de frontend/dist/assets/."""
    assets_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "assets"
    asset_files = list(assets_dir.glob("*.*"))
    assert len(asset_files) > 0, "Deveria haver pelo menos um asset compilado em frontend/dist/assets"

    chosen_asset = asset_files[0].name

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52343)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.get(f"/assets/{chosen_asset}")
        assert resp.status_code == 200
        assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_missing_assets_must_return_404_not_index_html():
    """Asset ausente em /assets/... deve retornar HTTP 404 estrito, NUNCA o HTML da SPA."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52344)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.get("/assets/arquivo-inexistente-123456789.js")
        assert resp.status_code == 404
        content_type = resp.headers.get("content-type", "")
        assert "text/html" not in content_type
        assert "Asset não localizado" in resp.text


@pytest.mark.asyncio
async def test_path_traversal_on_assets_returns_404():
    """Tentativa de path traversal em /assets/ deve ser bloqueada com 404."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52345)),
        base_url="http://localhost:8000",
    ) as client:
        # 1. Path traversal codificado em URL não deve ler arquivos fora de assets
        resp = await client.get("/assets/%2E%2E/%2E%2E/pyproject.toml")
        assert resp.status_code in (404, 400)
        # 2. Requisição a arquivo fora do bundle SPA
        resp2 = await client.get("/pyproject.toml")
        assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_remote_client_cannot_bootstrap_local_session():
    """Cliente remoto (IP não-loopback) não recebe cookie nem autenticação local automática."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("192.168.1.150", 41234)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.get("/app/session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is False
        assert data["mode"] == "remote"
        assert COOKIE_NAME not in resp.cookies
        assert COOKIE_NAME not in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_cross_origin_session_bootstrap_rejected():
    """Tentativa de bootstrap de sessão com Origin externo é rejeitada com 403 Forbidden."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52346)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.get(
            "/app/session",
            headers={"Origin": "https://malicious-attacker.com"},
        )
        assert resp.status_code == 403
        assert COOKIE_NAME not in resp.cookies


@pytest.mark.asyncio
async def test_malicious_host_bootstrap_rejected():
    """Requisição com Host header não local é rejeitada com 403."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52347)),
        base_url="http://malicious-domain.com",
    ) as client:
        resp = await client.get("/app/session")
        assert resp.status_code in (403, 400)
        assert COOKIE_NAME not in resp.cookies


@pytest.mark.asyncio
async def test_browser_session_cookie_grants_access_without_api_key(monkeypatch: pytest.MonkeyPatch):
    """Cliente navegador com cookie válido acessa endpoints protegidos sem header X-API-Key."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-super-restrito-9876")

    token = create_session_token()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52348)),
        base_url="http://localhost:8000",
        cookies={COOKIE_NAME: token},
    ) as client:
        # Acesso a rota protegida GET /api/v1/admin/credentials
        resp = await client.get("/api/v1/admin/credentials")
        assert resp.status_code == 200
        assert "credenciais" in resp.json()


@pytest.mark.asyncio
async def test_client_without_key_or_cookie_gets_401_when_key_configured(monkeypatch: pytest.MonkeyPatch):
    """Requisição sem chave de API e sem cookie válido recebe HTTP 401."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-super-restrito-9876")

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52349)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.get("/api/v1/admin/credentials")
        assert resp.status_code == 401
        assert "Chave de API ausente ou inválida" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_external_api_key_and_bearer_auth_remain_functional(monkeypatch: pytest.MonkeyPatch):
    """Clientes de API externa continuam operacionais via X-API-Key e Authorization: Bearer."""
    secret = "chave-externa-valida-4321"
    monkeypatch.setenv("API_SECRET_KEY", secret)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("10.0.0.5", 52350)),
        base_url="http://10.0.0.1:8000",
    ) as client:
        # 1. Com X-API-Key correta -> 200
        r1 = await client.get("/api/v1/admin/credentials", headers={"X-API-Key": secret})
        assert r1.status_code == 200

        # 2. Com Bearer token correto -> 200
        r2 = await client.get("/api/v1/admin/credentials", headers={"Authorization": f"Bearer {secret}"})
        assert r2.status_code == 200

        # 3. Com chave incorreta -> 401
        r3 = await client.get("/api/v1/admin/credentials", headers={"X-API-Key": "chave-falsa"})
        assert r3.status_code == 401


@pytest.mark.asyncio
async def test_tampered_or_expired_cookie_rejected_with_401(monkeypatch: pytest.MonkeyPatch):
    """Cookie adulterado ou expirado é recusado com HTTP 401 quando API_SECRET_KEY está ativa."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-ativo-1234")

    # 1. Cookie adulterado
    token_valido = create_session_token()
    token_adulterado = token_valido[:-4] + "fake"

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52351)),
        base_url="http://localhost:8000",
        cookies={COOKIE_NAME: token_adulterado},
    ) as client:
        resp = await client.get("/api/v1/admin/credentials")
        assert resp.status_code == 401

    # 2. Cookie expirado (ttl negativo)
    token_expirado = create_session_token(ttl_seconds=-100)
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52352)),
        base_url="http://localhost:8000",
        cookies={COOKIE_NAME: token_expirado},
    ) as client:
        resp2 = await client.get("/api/v1/admin/credentials")
        assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_mutating_cookie_request_cross_origin_rejected_with_403(monkeypatch: pytest.MonkeyPatch):
    """Requisição mutante (POST) autenticada via cookie com Origin externo é barrada com 403."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-ativo-1234")
    token = create_session_token()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52353)),
        base_url="http://localhost:8000",
        cookies={COOKIE_NAME: token},
    ) as client:
        resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Investigação sobre Robótica Educacional"},
            headers={"Origin": "https://site-atacante.xyz"},
        )
        assert resp.status_code == 403
        assert "cross-site" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mutating_cookie_request_same_origin_succeeds(monkeypatch: pytest.MonkeyPatch):
    """Requisição mutante (POST) autenticada via cookie na mesma origem é autorizada."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-ativo-1234")
    token = create_session_token()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52354)),
        base_url="http://localhost:8000",
        cookies={COOKIE_NAME: token},
    ) as client:
        resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Investigação sobre Robótica Educacional"},
            headers={"Origin": "http://localhost:8000"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id_pesquisa" in data
        assert "preferencias" in data


# ==============================================================================
# Casos de Borda e Fronteira de Autenticação / Diagnóstico Pre-integração
# ==============================================================================

@pytest.mark.asyncio
async def test_auth_boundary_case1_different_port_origin_must_reject(monkeypatch: pytest.MonkeyPatch):
    """Caso 1: Requisição mutante com cookie onde Origin possui porta diferente deve ser rejeitada com 403."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-teste-123")
    token = create_session_token()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52360)),
        base_url="http://localhost:8000",
        cookies={COOKIE_NAME: token},
    ) as client:
        # Request para porta 8000 mas com Origin porta 3000
        resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Investigação sobre Segurança Web"},
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 403
        assert "cross-site" in resp.json()["detail"].lower() or "origem" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_boundary_case2_missing_origin_and_referer_must_reject_unsafe_cookie_request(
    monkeypatch: pytest.MonkeyPatch,
):
    """Caso 2: Requisição mutante (POST) autenticada via cookie sem nenhum cabeçalho de origem (Origin/Referer)
    deve ser estritamente rejeitada com 403."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-teste-123")
    token = create_session_token()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52361)),
        base_url="http://localhost:8000",
        cookies={COOKIE_NAME: token},
    ) as client:
        # Sem Origin, sem Referer
        resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Investigação sem Origin ou Referer"},
        )
        assert resp.status_code == 403
        assert "origem" in resp.json()["detail"].lower() or "cross-site" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_boundary_case3_different_scheme_origin_must_reject(monkeypatch: pytest.MonkeyPatch):
    """Caso 3: Requisição mutante com esquema diferente (https vs http) deve ser rejeitada com 403."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-teste-123")
    token = create_session_token()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52362)),
        base_url="http://localhost:8000",
        cookies={COOKIE_NAME: token},
    ) as client:
        # Servidor em http, Origin em https
        resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Investigação sobre Esquemas HTTP"},
            headers={"Origin": "https://localhost:8000"},
        )
        assert resp.status_code == 403
        assert "cross-site" in resp.json()["detail"].lower() or "origem" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_boundary_case4_untrusted_127_prefix_hostname_must_reject_bootstrap():
    """Caso 4: Hostname com prefixo 127 não-IP ('127.evil.invalid') deve ser categoricamente rejeitado."""
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52363)),
        base_url="http://127.evil.invalid:8000",
    ) as client:
        resp = await client.get("/app/session")
        assert resp.status_code == 403
        assert COOKIE_NAME not in resp.cookies


@pytest.mark.asyncio
async def test_auth_boundary_case5_malformed_unicode_cookie_rejected_without_exception(
    monkeypatch: pytest.MonkeyPatch,
):
    """Caso 5: Cookie com caracteres Unicode malformados ('é.signature') deve falhar fechado sem lançar 500."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-ativo-1234")

    # Verificação direta da função verify_session_token (como testado nas observações offline)
    assert verify_session_token("é.signature") is False
    assert verify_session_token("payload.é") is False
    assert verify_session_token("não_é_um_token_válido") is False
    assert verify_session_token("...") is False
    assert verify_session_token("") is False
    assert verify_session_token(None) is False
    assert verify_session_token("part1.part2.part3") is False

    # Verificação via requisição HTTP com cookie percent-encoded (%C3%A9)
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52364)),
        base_url="http://localhost:8000",
        headers={"Cookie": f"{COOKIE_NAME}=%C3%A9.signature"},
    ) as client:
        resp = await client.get("/api/v1/admin/credentials")
        assert resp.status_code == 401
        assert "Chave de API ausente ou inválida" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_boundary_cross_origin_localhost_vs_127_0_0_1_must_reject(monkeypatch: pytest.MonkeyPatch):
    """Não há equivalência entre localhost e 127.0.0.1 entre origens: Host localhost com Origin 127.0.0.1 é rejeitado."""
    monkeypatch.setenv("API_SECRET_KEY", "segredo-ativo-1234")
    token = create_session_token()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52365)),
        base_url="http://localhost:8000",
        cookies={COOKIE_NAME: token},
    ) as client:
        resp = await client.post(
            "/api/v1/plan",
            json={"tema": "Investigação sobre Isolamento de Origens"},
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_missing_bundle_index_html_returns_503(monkeypatch: pytest.MonkeyPatch):
    """Quando o bundle frontend/dist/index.html não existe, GET / deve retornar HTTP 503 claro."""
    from app import main as main_module
    fake_path = Path("/tmp/non_existent_frontend_dist_12345")
    monkeypatch.setattr(main_module, "FRONTEND_DIST_DIR", fake_path)

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52366)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.get("/")
        assert resp.status_code == 503
        assert "Frontend bundle não compilado" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_session_bootstrap_resolves_preferences_from_db_when_env_absent(monkeypatch: pytest.MonkeyPatch):
    """GET /app/session resolve n_pontos e personas do banco de dados quando variáveis ENV estiverem ausentes."""
    # Remove variáveis de ambiente
    monkeypatch.delenv("N_PONTOS", raising=False)
    monkeypatch.delenv("PERSONAS_CONFIG", raising=False)

    from app.config import get_settings
    get_settings.cache_clear()

    # Salva preferências personalizadas no banco cifrado
    from app.db.credentials_repository import CredentialsRepository
    from app.db.session import get_sessionmaker
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        repo = CredentialsRepository(session=session)
        await repo.save_credential("N_PONTOS", "4", "parametro", descricao="Pontos no banco")
        await repo.save_credential("PERSONAS_CONFIG", "visionario,cetico", "parametro", descricao="Personas no banco")
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.1", 52367)),
        base_url="http://localhost:8000",
    ) as client:
        resp = await client.get("/app/session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["preferences"]["n_pontos"] == 4, "Deveria ter resolvido n_pontos=4 do banco cifrado"
        assert data["preferences"]["personas"] == ["visionario", "cetico"], "Deveria ter resolvido personas do banco cifrado"

