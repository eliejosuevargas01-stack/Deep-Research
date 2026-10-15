import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_cors_preflight_x_api_key_allowed_origin():
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    allow_headers = response.headers.get("access-control-allow-headers", "")
    headers_list = [h.strip().lower() for h in allow_headers.split(",")]
    assert "x-api-key" in headers_list


def test_cors_preflight_x_api_key_unauthorized_origin():
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://unauthorized-origin.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None
