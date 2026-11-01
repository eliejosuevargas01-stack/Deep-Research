"""Testes de regressão unitários para os componentes isolados das Ondas 3 e 4.

Cobre a elegibilidade de sessão local (is_local_eligible) em app/ui_session.py
com suporte a loopback, faixas de IP privadas/Docker e flags de ambiente.
"""

import pytest
from starlette.requests import Request

from app.ui_session import is_local_eligible, _is_private_or_loopback_ip, _is_trusted_network_active


def _build_request(
    client_ip: str | None = "127.0.0.1",
    client_port: int = 50000,
    host: str = "localhost:8000",
    origin: str | None = None,
    referer: str | None = None,
    sec_fetch_site: str | None = None,
) -> Request:
    """Auxiliar para sintetizar um starlette.requests.Request com escopo HTTP."""
    headers = [(b"host", host.encode("latin-1"))]
    if origin is not None:
        headers.append((b"origin", origin.encode("latin-1")))
    if referer is not None:
        headers.append((b"referer", referer.encode("latin-1")))
    if sec_fetch_site is not None:
        headers.append((b"sec-fetch-site", sec_fetch_site.encode("latin-1")))

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/app/session",
        "headers": headers,
        "client": (client_ip, client_port) if client_ip is not None else None,
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
    }
    return Request(scope)


class TestIsLocalEligible:
    """Valida permissões de rede de is_local_eligible para loopback, Docker e LAN."""

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "127.0.0.2",
            "127.10.20.30",
            "::1",
        ],
    )
    def test_loopback_ips_are_eligible(self, ip: str):
        """Endereços loopback IPv4 e IPv6 devem ser aceitos."""
        req = _build_request(client_ip=ip, host="localhost:8000")
        assert is_local_eligible(req) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "172.17.0.1",       # Bridge Docker padrão (gateway)
            "172.17.0.2",       # Container Docker na bridge padrão
        ],
    )
    def test_docker_bridge_ips_are_eligible_by_default(self, ip: str, monkeypatch: pytest.MonkeyPatch):
        """IPs da bridge padrão Docker (172.17.0.0/16) devem ser elegíveis por padrão."""
        monkeypatch.delenv("TRUST_LOCAL_NETWORK", raising=False)
        monkeypatch.delenv("DOCKER_CONTAINER", raising=False)
        req = _build_request(client_ip=ip, host="localhost:8000")
        assert is_local_eligible(req) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "172.18.0.5",       # Rede Docker personalizada (172.18.0.0/16)
            "172.16.0.1",       # Início da faixa 172.16.0.0/12
            "172.31.255.254",   # Fim da faixa 172.16.0.0/12
            "10.0.0.1",         # LAN privada 10.0.0.0/8
            "10.200.1.50",      # LAN privada 10.0.0.0/8
            "192.168.0.1",      # LAN doméstica/roteador 192.168.0.0/16
            "192.168.1.100",    # LAN privada 192.168.0.0/16
        ],
    )
    def test_other_private_ips_require_trusted_network(self, ip: str, monkeypatch: pytest.MonkeyPatch):
        """Outras faixas privadas (10/8, 192.168/16, restante de 172.16/12) DEVEM exigir flag de confiança (B-19)."""
        monkeypatch.delenv("TRUST_LOCAL_NETWORK", raising=False)
        monkeypatch.delenv("DOCKER_CONTAINER", raising=False)
        req = _build_request(client_ip=ip, host="localhost:8000")
        assert is_local_eligible(req) is False

        monkeypatch.setenv("TRUST_LOCAL_NETWORK", "1")
        assert is_local_eligible(req) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",
            "1.1.1.1",
            "93.184.216.34",
            "142.250.190.46",
        ],
    )
    def test_public_ips_are_rejected_by_default(self, ip: str, monkeypatch: pytest.MonkeyPatch):
        """IPs públicos devem ser rejeitados quando nenhuma variável de confiança estiver ativa."""
        monkeypatch.delenv("TRUST_LOCAL_NETWORK", raising=False)
        monkeypatch.delenv("DOCKER_CONTAINER", raising=False)

        req = _build_request(client_ip=ip, host="localhost:8000")
        assert is_local_eligible(req) is False

    @pytest.mark.parametrize("env_var", ["TRUST_LOCAL_NETWORK", "DOCKER_CONTAINER"])
    @pytest.mark.parametrize("env_val", ["1", "true", "True", "yes", "on"])
    def test_public_ips_allowed_with_trusted_env(
        self, env_var: str, env_val: str, monkeypatch: pytest.MonkeyPatch
    ):
        """IPs públicos ou atrás de proxy reverso passam quando TRUST_LOCAL_NETWORK / DOCKER_CONTAINER ativa."""
        monkeypatch.setenv(env_var, env_val)
        req = _build_request(client_ip="8.8.8.8", host="localhost:8000")
        assert is_local_eligible(req) is True

    def test_docker_host_and_private_host_headers_allowed(self, monkeypatch: pytest.MonkeyPatch):
        """Cabeçalhos Host com IPs de rede privada ou Docker são aceitos."""
        monkeypatch.delenv("TRUST_LOCAL_NETWORK", raising=False)
        monkeypatch.delenv("DOCKER_CONTAINER", raising=False)

        req_docker_ip = _build_request(client_ip="172.17.0.2", host="172.17.0.2:8000")
        assert is_local_eligible(req_docker_ip) is True

        req_docker_named = _build_request(client_ip="172.17.0.2", host="host.docker.internal:8000")
        assert is_local_eligible(req_docker_named) is True

        monkeypatch.setenv("TRUST_LOCAL_NETWORK", "1")
        req_lan = _build_request(client_ip="192.168.1.50", host="192.168.1.50:8000")
        assert is_local_eligible(req_lan) is True

    def test_origin_mismatch_is_rejected(self):
        """Origin cross-site com hostname diferente deve ser rejeitada mesmo em IP local."""
        req = _build_request(
            client_ip="127.0.0.1",
            host="localhost:8000",
            origin="http://evil-attacker.com",
        )
        assert is_local_eligible(req) is False

    def test_referer_mismatch_is_rejected(self):
        """Referer divergente de origem não local deve ser rejeitado."""
        req = _build_request(
            client_ip="172.17.0.2",
            host="localhost:8000",
            referer="http://malicious-site.org/phish",
        )
        assert is_local_eligible(req) is False

    def test_matching_origin_and_referer_allowed(self):
        """Origin e Referer coincidentes com a origem esperada devem ser aprovados."""
        req = _build_request(
            client_ip="172.17.0.2",
            host="localhost:8000",
            origin="http://localhost:8000",
            referer="http://localhost:8000/app",
        )
        assert is_local_eligible(req) is True

    def test_none_client_rejected_unless_trusted_env(self, monkeypatch: pytest.MonkeyPatch):
        """Requisição sem cliente definido é recusada sem env, e aceita com env de confiança."""
        monkeypatch.delenv("TRUST_LOCAL_NETWORK", raising=False)
        monkeypatch.delenv("DOCKER_CONTAINER", raising=False)
        req_no_client = _build_request(client_ip=None, host="localhost:8000")
        assert is_local_eligible(req_no_client) is False

        monkeypatch.setenv("TRUST_LOCAL_NETWORK", "1")
        assert is_local_eligible(req_no_client) is True
