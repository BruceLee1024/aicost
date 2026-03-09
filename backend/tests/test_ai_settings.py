"""Tests for AI settings management routes and multi-provider config."""

import os


def test_get_ai_settings_returns_defaults(client, monkeypatch):
    """GET /api/ai/settings should return default disabled state."""
    # Ensure env is clean
    for key in list(os.environ):
        if key.startswith("AI_"):
            monkeypatch.delenv(key, raising=False)

    r = client.get("/api/ai/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "disabled"
    assert body["timeout_seconds"] == 20.0
    assert body["enable_audit_logs"] is False
    # All providers should be present
    for p in ["deepseek", "qwen", "kimi", "glm", "openai"]:
        assert p in body["providers"]
        assert "api_key" in body["providers"][p]
        assert "base_url" in body["providers"][p]
        assert "model" in body["providers"][p]


def test_put_ai_settings_persists_and_returns(client, monkeypatch):
    """PUT /api/ai/settings should persist config and return updated state."""
    for key in list(os.environ):
        if key.startswith("AI_"):
            monkeypatch.delenv(key, raising=False)

    payload = {
        "provider": "deepseek",
        "timeout_seconds": 30,
        "enable_audit_logs": True,
        "providers": {
            "deepseek": {
                "api_key": "sk-test-deepseek",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
            },
            "qwen": {
                "api_key": "sk-test-qwen",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-plus",
            },
            "kimi": {"api_key": "", "base_url": "", "model": ""},
            "glm": {"api_key": "", "base_url": "", "model": ""},
            "openai": {"api_key": "", "base_url": "", "model": ""},
        },
    }
    r = client.put("/api/ai/settings", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "deepseek"
    assert body["timeout_seconds"] == 30.0
    assert body["enable_audit_logs"] is True
    assert body["providers"]["deepseek"]["api_key"] == "sk-test-deepseek"
    assert body["providers"]["qwen"]["api_key"] == "sk-test-qwen"

    # Subsequent GET should reflect persisted state
    r2 = client.get("/api/ai/settings")
    assert r2.json()["provider"] == "deepseek"
    assert r2.json()["providers"]["deepseek"]["api_key"] == "sk-test-deepseek"


def test_put_ai_settings_rejects_invalid_provider(client):
    """PUT with unknown provider should return 400."""
    payload = {
        "provider": "nonexistent",
        "timeout_seconds": 20,
        "enable_audit_logs": False,
        "providers": {
            "deepseek": {"api_key": "", "base_url": "", "model": ""},
            "qwen": {"api_key": "", "base_url": "", "model": ""},
            "kimi": {"api_key": "", "base_url": "", "model": ""},
            "glm": {"api_key": "", "base_url": "", "model": ""},
            "openai": {"api_key": "", "base_url": "", "model": ""},
        },
    }
    r = client.put("/api/ai/settings", json=payload)
    assert r.status_code == 400


def test_put_ai_settings_switch_provider(client, monkeypatch):
    """Switching active provider should reflect in GET."""
    for key in list(os.environ):
        if key.startswith("AI_"):
            monkeypatch.delenv(key, raising=False)

    base = {
        "timeout_seconds": 20,
        "enable_audit_logs": False,
        "providers": {
            "deepseek": {"api_key": "sk-ds", "base_url": "", "model": ""},
            "qwen": {"api_key": "sk-qw", "base_url": "", "model": ""},
            "kimi": {"api_key": "", "base_url": "", "model": ""},
            "glm": {"api_key": "", "base_url": "", "model": ""},
            "openai": {"api_key": "", "base_url": "", "model": ""},
        },
    }

    # Set deepseek first
    client.put("/api/ai/settings", json={**base, "provider": "deepseek"})
    assert client.get("/api/ai/settings").json()["provider"] == "deepseek"

    # Switch to qwen
    client.put("/api/ai/settings", json={**base, "provider": "qwen"})
    assert client.get("/api/ai/settings").json()["provider"] == "qwen"
