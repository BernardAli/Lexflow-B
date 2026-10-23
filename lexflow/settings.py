"""Configuration. External document AI is disabled unless explicitly enabled."""
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    root = Path(os.getenv("LEXFLOW_DATA_DIR", str(PROJECT_ROOT / "data"))).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return data_dir() / "lexflow.sqlite3"


def allow_external_ai() -> bool:
    return os.getenv("LEXFLOW_ALLOW_EXTERNAL_AI", "0") == "1" and bool(os.getenv("OPENAI_API_KEY"))


def ai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def max_upload_bytes() -> int:
    return int(os.getenv("LEXFLOW_MAX_UPLOAD_MB", "12")) * 1024 * 1024


def seed_demo_enabled() -> bool:
    return os.getenv("LEXFLOW_SEED_DEMO", "1") == "1"


def secure_cookies() -> bool:
    return os.getenv("LEXFLOW_SECURE_COOKIES", "1" if os.getenv("LEXFLOW_SECURITY_PROFILE") == "hardened" else "0") == "1"
