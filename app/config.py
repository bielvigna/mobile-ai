import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_LOCAL_PROPERTIES = Path.home() / "AndroidStudioProjects" / "MarvelBattle" / "local.properties"


class Settings(BaseSettings):
    comic_vine_api_key: str = ""
    ai_provider: str = "openai-compatible"
    ai_model: str = "openai/gpt-oss-120b"
    ai_api_key: str = ""
    ai_base_url: str = "https://api.groq.com/openai/v1"
    marvel_backend_host: str = "0.0.0.0"
    marvel_backend_port: int = 8080

    model_config = SettingsConfigDict(extra="ignore")


def _read_key_value_file(path: Path, separator: str = "=") -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or separator not in line:
            continue
        key, value = line.split(separator, 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _backend_port(ai_host: str) -> int:
    host = ai_host.strip()
    parsed = urlparse(host if "://" in host else f"//{host}")
    return parsed.port or 8080


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Lower-priority files first. Process environment variables always win.
    values: dict[str, str] = {}
    values.update(_read_key_value_file(Path(__file__).resolve().parents[1] / ",env"))
    values.update(_read_key_value_file(Path(__file__).resolve().parents[1] / ".env"))
    local_properties = Path(os.environ.get("ANDROID_LOCAL_PROPERTIES", DEFAULT_LOCAL_PROPERTIES))
    values.update(_read_key_value_file(local_properties))
    values.update(os.environ)

    return Settings(
        comic_vine_api_key=values.get("COMIC_VINE_API_KEY", ""),
        ai_provider=values.get("AI_PROVIDER", "openai-compatible"),
        ai_model=values.get("AI_MODEL", "openai/gpt-oss-120b"),
        ai_api_key=values.get("AI_API_KEY", values.get("GROQ_API_KEY", "")),
        ai_base_url=values.get("AI_BASE_URL", "https://api.groq.com/openai/v1"),
        marvel_backend_host=values.get("MARVEL_BACKEND_HOST", "0.0.0.0"),
        marvel_backend_port=values.get("MARVEL_BACKEND_PORT", _backend_port(values.get("AI_HOST", ""))),
    )
