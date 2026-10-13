"""API contract checks for currently implemented endpoints.

The former coverage-only file asserted responses and request bodies that the
application never implemented. These checks exercise real public and
authenticated paths instead of inflating a coverage target.
"""

from fastapi.testclient import TestClient

from lexecon.api.server import app


def test_health_is_public():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_policy_and_evidence_routes_reject_anonymous_callers():
    client = TestClient(app)
    assert client.get("/policies").status_code == 401
    assert client.post("/policies/load", json={"policy": {"relations": []}}).status_code == 401
    assert client.post("/evidence/export", json={}).status_code == 401


def test_article_11_returns_document_for_authorized_user(authenticated_client):
    response = authenticated_client.get("/compliance/eu-ai-act/article-11")
    assert response.status_code == 200
    assert response.json()["format"] == "json"
    assert isinstance(response.json()["content"], dict)


def test_article_12_returns_retention_status(authenticated_client):
    response = authenticated_client.get("/compliance/eu-ai-act/article-12/status")
    assert response.status_code == 200
    assert "total_records" in response.json()


def test_public_key_matches_declared_algorithm(authenticated_client):
    response = authenticated_client.get("/compliance/public-key")
    assert response.status_code == 200
    assert response.json()["algorithm"] == "RSA-PSS-SHA256"
    assert "BEGIN PUBLIC KEY" in response.json()["public_key_pem"]
