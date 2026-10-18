"""Testes BDD (Behave) — Etapa 1: Autenticação e Controle de Acesso.

Implementação da feature features/001_autenticacao.feature cobrindo:
  * POST /api/auth/login com senha correta/incorreta (cookie dr_session + CSRF)
  * GET /api/auth/me via Bearer, X-API-Key, sem credenciais e com credenciais múltiplas
  * Rejeição do cabeçalho proibido de tenant (x-tenant-id) — HTTP 400
  * Proteção CSRF em mutações com sessão de cookie (403) e logout com CSRF válido (204)
  * Prevenção de vazamento de API_AUTH_SECRET / ADMIN_PASSWORD nas rotas de auth

Isolamento: cada cenário usa um engine SQLite in-memory dedicado (StaticPool) e
substitui `get_db` via `app.dependency_overrides`. O snapshot dos overrides
originais é SEMPRE restaurado ao final de cada requisição, garantindo que a
suíte não interfira no banco real nem nos demais testes.

O engine global do app (app.db.database.engine) e a factory real
(AsyncSessionLocal) são importados apenas como parte do contrato do módulo
BDD e jamais conectados durante os testes.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from http.cookies import SimpleCookie
from uuid import uuid4

import httpx
from behave import given, then, when
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.database import (
    AsyncSessionLocal,  # noqa: F401 — importado conforme contrato do módulo BDD (Etapa 1)
    engine,  # noqa: F401 — importado conforme contrato do módulo BDD (Etapa 1)
    get_db,
)
from app.main import app
from app.models import AdminSession, Base

SESSION_COOKIE = "dr_session"


def run_async(coro):
    return asyncio.run(coro)


# =========================================================================
# Infraestrutura: banco SQLite in-memory isolado + override de get_db
# =========================================================================


async def _init_auth_db(context):
    """Cria engine dedicado (SQLite in-memory) com todo o schema do app."""
    if getattr(context, "session_factory", None) is not None:
        return None
    auth_engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with auth_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    context.engine = auth_engine
    context.session_factory = async_sessionmaker(auth_engine, expire_on_commit=False)
    return context


@asynccontextmanager
async def _api_db_context(context):
    """Instala o override de get_db para o factory isolado e o restaura ao final."""
    await _init_auth_db(context)
    factory = context.session_factory

    async def _override_get_db():
        async with factory() as session:
            yield session

    # Snapshot antes de alterar — sempre restaurado no finally (regra do prompt).
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield factory
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


@asynccontextmanager
async def _api_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _require_admin_password() -> str:
    password = settings.ADMIN_PASSWORD
    assert password, "ADMIN_PASSWORD deve estar configurado no ambiente de teste"
    return password


def _require_api_auth_secret() -> str:
    secret = settings.API_AUTH_SECRET
    assert secret, "API_AUTH_SECRET deve estar configurado no ambiente de teste"
    return secret


def _set_cookie_raw(response: httpx.Response, cookie_name: str) -> str | None:
    for raw in response.headers.get_list("set-cookie"):
        if f"{cookie_name}=" in raw:
            return raw
    return None


def _extract_cookie(response: httpx.Response, cookie_name: str) -> str | None:
    raw = _set_cookie_raw(response, cookie_name)
    if raw is None:
        return None
    jar = SimpleCookie()
    jar.load(raw)
    morsel = jar.get(cookie_name)
    return morsel.value if morsel else None


def _assert_no_secret_leak(response: httpx.Response) -> None:
    header_blob = "\n".join(
        f"{name}: {value}" for name, value in response.headers.items()
    )
    body = response.text + "\n" + header_blob
    for field_name in ("ADMIN_PASSWORD", "API_AUTH_SECRET"):
        secret_value = getattr(settings, field_name)
        if secret_value:
            assert secret_value not in body, (
                f"Vazamento do segredo {field_name} detectado na resposta "
                f"(HTTP {response.status_code}): {body}"
            )


async def _count_admin_sessions(context) -> int:
    async with context.session_factory() as session:
        return len((await session.scalars(select(AdminSession))).all())


async def _perform_login(client: httpx.AsyncClient) -> tuple[httpx.Response, str, str]:
    """Executa o login de admin e retorna (resposta, token do cookie, csrf_token)."""
    response = await client.post(
        "/api/auth/login", json={"password": _require_admin_password()}
    )
    assert response.status_code == 200, (
        f"Login de preparação falhou: HTTP {response.status_code} — {response.text}"
    )
    cookie = _extract_cookie(response, SESSION_COOKIE)
    assert cookie, "Cookie dr_session não definido no login de preparação"
    csrf = (response.json() or {}).get("csrf_token") or ""
    assert csrf, "csrf_token vazio no login de preparação"
    return response, cookie, csrf


# =========================================================================
# Dado: configurações e estados iniciais
# =========================================================================


@given("que o sistema possui a senha de administrador configurada")
def step_admin_password_configured(context):
    _require_admin_password()
    run_async(_init_auth_db(context))
    context.admin_password = settings.ADMIN_PASSWORD


@given('que a API possui o segredo "API_AUTH_SECRET" configurado')
def step_api_auth_secret_configured(context):
    _require_api_auth_secret()
    run_async(_init_auth_db(context))


@given(
    'que o sistema possui a senha de administrador e o segredo "API_AUTH_SECRET" configurados'
)
def step_admin_password_and_api_secret_configured(context):
    _require_admin_password()
    _require_api_auth_secret()
    run_async(_init_auth_db(context))


@given("que o usuário não fornece nenhuma credencial de autenticação")
def step_no_credentials(context):
    run_async(_init_auth_db(context))
    context.headers = {}
    context.session_cookie = None


@given("que o usuário envia simultaneamente Bearer token e X-API-Key")
def step_multiple_credentials(context):
    secret = _require_api_auth_secret()
    run_async(_init_auth_db(context))
    context.headers = {"Authorization": f"Bearer {secret}", "X-API-Key": secret}


@given('que o usuário envia o cabeçalho proibido "x-tenant-id"')
def step_forbidden_tenant_header(context):
    run_async(_init_auth_db(context))
    context.headers = {"x-tenant-id": "tenant-123"}


@given('que o usuário possui uma sessão ativa via cookie "dr_session"')
def step_active_session_cookie(context):
    run_async(_init_auth_db(context))

    async def _login():
        async with _api_db_context(context):
            async with _api_client() as client:
                _, cookie, csrf_token = await _perform_login(client)
                context.session_cookie = cookie
                context.csrf_token = csrf_token

    run_async(_login())
    assert context.session_cookie is not None


@given(
    'que o usuário possui uma sessão ativa via cookie "dr_session" com token CSRF válido'
)
def step_active_session_with_csrf(context):
    step_active_session_cookie(context)
    assert context.csrf_token is not None


# =========================================================================
# Quando: login
# =========================================================================


@when('uma requisição "POST /api/auth/login" é enviada com a senha correta')
def step_post_login_correct(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                context.response = await client.post(
                    "/api/auth/login", json={"password": _require_admin_password()}
                )
                context.login_response = context.response
                context.set_cookie_raw = _set_cookie_raw(context.response, SESSION_COOKIE)
                context.session_cookie = _extract_cookie(context.response, SESSION_COOKIE)
                context.admin_session_count = await _count_admin_sessions(context)

    run_async(_call())


@when('uma requisição "POST /api/auth/login" é enviada com senha incorreta')
def step_post_login_incorrect(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                wrong_password = f"senha_completamente_errada_{uuid4().hex}"
                context.response = await client.post(
                    "/api/auth/login", json={"password": wrong_password}
                )
                context.set_cookie_raw = _set_cookie_raw(context.response, SESSION_COOKIE)
                context.session_cookie = _extract_cookie(context.response, SESSION_COOKIE)
                context.admin_session_count = await _count_admin_sessions(context)

    run_async(_call())


# =========================================================================
# Quando: GET /api/auth/me (todas as variantes de credencial)
# =========================================================================


@when(
    'uma requisição "GET /api/auth/me" é enviada com cabeçalho '
    '"Authorization: Bearer <API_AUTH_SECRET>"'
)
def step_get_me_bearer(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                context.response = await client.get(
                    "/api/auth/me",
                    headers={"Authorization": f"Bearer {_require_api_auth_secret()}"},
                )
                context.me_response = context.response

    run_async(_call())


@when(
    'uma requisição "GET /api/auth/me" é enviada com cabeçalho "X-API-Key: <API_AUTH_SECRET>"'
)
def step_get_me_apikey(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                context.response = await client.get(
                    "/api/auth/me", headers={"X-API-Key": _require_api_auth_secret()}
                )
                context.me_response = context.response

    run_async(_call())


@when('uma requisição "GET /api/auth/me" é enviada sem cabeçalhos ou cookies')
def step_get_me_no_credentials(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                context.response = await client.get("/api/auth/me")
                context.me_response = context.response

    run_async(_call())


@when('uma requisição "GET /api/auth/me" é enviada com ambas as credenciais')
def step_get_me_ambiguous(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                context.response = await client.get("/api/auth/me", headers=context.headers)
                context.me_response = context.response

    run_async(_call())


@when('uma requisição "GET /api/auth/me" é enviada com o cabeçalho "x-tenant-id"')
def step_get_me_tenant(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                context.response = await client.get("/api/auth/me", headers=context.headers)
                context.me_response = context.response

    run_async(_call())


# =========================================================================
# Quando: mutações protegidas por CSRF (POST /api/auth/logout)
# =========================================================================


@when(
    'uma requisição de mutação "POST /api/auth/logout" é enviada sem cabeçalho "X-CSRF-Token"'
)
def step_post_logout_without_csrf(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                context.response = await client.post(
                    "/api/auth/logout", cookies={SESSION_COOKIE: context.session_cookie}
                )

    run_async(_call())


@when(
    'uma requisição de mutação "POST /api/auth/logout" é enviada com o cabeçalho "X-CSRF-Token"'
)
def step_post_logout_with_csrf(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                context.response = await client.post(
                    "/api/auth/logout",
                    cookies={SESSION_COOKIE: context.session_cookie},
                    headers={"X-CSRF-Token": context.csrf_token},
                )

    run_async(_call())


# =========================================================================
# Quando: guardião anti-vazamento de segredos nas rotas de auth
# =========================================================================


@when(
    'o login é realizado e as rotas "/api/auth/me" e "/api/auth/csrf" são consultadas em sequência'
)
def step_login_and_query_auth_routes(context):
    async def _call():
        async with _api_db_context(context):
            async with _api_client() as client:
                login, cookie, _csrf = await _perform_login(client)
                context.login_response = login
            # Clientes separados por perfil de credencial: o cookie jar de um
            # client contaminado poderia adicionar um segundo tipo de credencial.
            async with _api_client() as client:
                context.me_response = await client.get(
                    "/api/auth/me",
                    headers={"Authorization": f"Bearer {_require_api_auth_secret()}"},
                )
            async with _api_client() as client:
                context.csrf_response = await client.get(
                    "/api/auth/csrf", cookies={SESSION_COOKIE: cookie}
                )

    run_async(_call())


# =========================================================================
# Então: status HTTP exato, cookies, corpo e persistência
# =========================================================================


@then("a resposta da API deve ter status HTTP {status_code:d}")
def step_assert_status_code(context, status_code):
    assert context.response.status_code == status_code, (
        f"Esperado status HTTP {status_code}, obtido {context.response.status_code}: "
        f"{context.response.text}"
    )


@then('o corpo da resposta deve indicar "authenticated": true e role "admin"')
def step_assert_authenticated_and_role(context):
    data = context.response.json()
    assert data.get("authenticated") is True, f"Esperado authenticated=True, obtido {data}"
    assert data.get("role") == "admin", f"Esperado role='admin', obtido {data}"


@then('a resposta deve conter "authenticated": true e um token "csrf_token"')
def step_assert_authenticated_and_csrf(context):
    data = context.response.json()
    assert data.get("authenticated") is True, f"Esperado authenticated=True, obtido {data}"
    csrf = data.get("csrf_token")
    assert isinstance(csrf, str) and csrf.strip(), f"Token csrf ausente ou vazio: {data}"


@then('o cookie "dr_session" deve ser configurado na resposta')
def step_assert_cookie_present(context):
    cookie = context.response.cookies.get(SESSION_COOKIE)
    assert cookie is not None, "Cookie dr_session não foi configurado na resposta"
    assert context.session_cookie is not None, "Valor do cookie dr_session capturado está vazio"


@then('o cookie "dr_session" deve ser definido como httpOnly com "Path=/" e "SameSite=lax"')
def step_assert_cookie_flags(context):
    raw = (context.set_cookie_raw or "").lower()
    assert raw, "Nenhum header Set-Cookie com dr_session na resposta"
    assert "httponly" in raw, f"Cookie dr_session não é httpOnly: {raw}"
    assert "path=/" in raw, f"Cookie dr_session sem Path=/: {raw}"
    assert "samesite=lax" in raw, f"Cookie dr_session sem SameSite=lax: {raw}"


@then('nenhum cookie "dr_session" deve ser configurado')
def step_assert_no_cookie(context):
    cookie = context.response.cookies.get(SESSION_COOKIE)
    assert cookie is None, f"Cookie dr_session não deveria ter sido definido: {cookie}"
    assert _set_cookie_raw(context.response, SESSION_COOKIE) is None


@then("a sessão de administrador correspondente deve ser persistida no banco de dados")
def step_assert_admin_session_persisted(context):
    count = context.admin_session_count
    assert count == 1, f"Esperado exatamente 1 AdminSession persistida, encontradas {count}"


@then("nenhuma sessão de administrador deve ser persistida no banco de dados")
def step_assert_no_admin_session_persisted(context):
    count = context.admin_session_count
    assert count == 0, f"Nenhuma AdminSession deveria ser persistida, encontradas {count}"


@then('a resposta deve conter detalhe "{expected_detail}"')
def step_assert_detail(context, expected_detail):
    data = context.response.json()
    detail = data.get("detail", "")
    assert expected_detail in str(detail), f"Esperado detalhe '{expected_detail}' em {detail}"


@then('o cookie "dr_session" deve ser removido na resposta')
def step_assert_cookie_removed(context):
    set_cookie_headers = context.response.headers.get_list("set-cookie")
    removed = False
    for header in set_cookie_headers:
        lowered = header.lower()
        if SESSION_COOKIE in header and (
            "max-age=0" in lowered or "expires=" in lowered or '""' in header
        ):
            removed = True
            break
    cookie_in_jar = context.response.cookies.get(SESSION_COOKIE)
    assert removed or cookie_in_jar is None or cookie_in_jar == "", (
        f"Cookie dr_session não foi removido adequadamente. Headers: {set_cookie_headers}"
    )


@then('a resposta não deve conter a senha do administrador nem o segredo da API')
def step_assert_login_response_no_leak(context):
    _assert_no_secret_leak(context.response)


@then('a resposta do login não deve conter a senha do administrador nem o segredo da API')
def step_assert_login_no_leak(context):
    assert context.login_response is not None, "Resposta de login ausente"
    _assert_no_secret_leak(context.login_response)


@then('a resposta de "/api/auth/me" não deve conter a senha do administrador nem o segredo da API')
def step_assert_me_no_leak(context):
    response = context.me_response
    assert response is not None, "Resposta de /api/auth/me ausente"
    assert response.status_code == 200, (
        f"GET /api/auth/me deveria responder 200, obtido {response.status_code}: {response.text}"
    )
    _assert_no_secret_leak(response)


@then(
    'a resposta de "/api/auth/csrf" não deve conter a senha do administrador nem o segredo da API'
)
def step_assert_csrf_no_leak(context):
    response = context.csrf_response
    assert response is not None, "Resposta de /api/auth/csrf ausente"
    assert response.status_code == 200, (
        f"GET /api/auth/csrf deveria responder 200, obtido {response.status_code}: {response.text}"
    )
    _assert_no_secret_leak(response)
