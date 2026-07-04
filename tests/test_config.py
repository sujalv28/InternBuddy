import pytest
import config


def test_get_google_api_key_present(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "abc123")
    assert config.get_google_api_key() == "abc123"


def test_get_google_api_key_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(config.ConfigError):
        config.get_google_api_key()


def test_get_smtp_config_present(monkeypatch):
    for k, v in {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "u@example.com",
        "SMTP_PASSWORD": "pw",
        "FROM_EMAIL": "u@example.com",
    }.items():
        monkeypatch.setenv(k, v)
    cfg = config.get_smtp_config()
    assert cfg["host"] == "smtp.example.com"
    assert cfg["port"] == 587
    assert cfg["from_email"] == "u@example.com"


def test_get_smtp_config_missing(monkeypatch):
    for k in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"]:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(config.ConfigError):
        config.get_smtp_config()
