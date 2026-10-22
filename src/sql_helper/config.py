from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса из переменных окружения с префиксом APP_ (и файла .env)."""

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
