from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_health_reports_configuration_without_revealing_secrets(monkeypatch):
    monkeypatch.setenv("COMIC_VINE_API_KEY", "")
    monkeypatch.setenv("AI_API_KEY", "")
    monkeypatch.setenv("AI_MODEL", "")
    get_settings.cache_clear()
    try:
        response = TestClient(app).get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "comic_vine_configured": False, "ai_configured": False}
        assert "api_key" not in response.text.lower()
    finally:
        get_settings.cache_clear()


def test_character_endpoint_returns_clear_setup_error_without_key(monkeypatch):
    monkeypatch.setenv("COMIC_VINE_API_KEY", "")
    get_settings.cache_clear()
    try:
        response = TestClient(app).get("/api/characters")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "comic_vine_not_configured"
    finally:
        get_settings.cache_clear()
