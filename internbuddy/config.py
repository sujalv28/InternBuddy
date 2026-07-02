import os

from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    """Raised when required configuration is missing."""


def get_google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ConfigError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your Gemini key."
        )
    return key


def get_smtp_config() -> dict:
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise ConfigError(f"Missing SMTP configuration: {', '.join(missing)}")
    return {
        "host": os.getenv("SMTP_HOST"),
        "port": int(os.getenv("SMTP_PORT")),
        "user": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASSWORD"),
        "from_email": os.getenv("FROM_EMAIL"),
    }
