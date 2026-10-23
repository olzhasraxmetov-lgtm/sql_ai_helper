from typing import Literal
from urllib.parse import quote

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Имена ролей PostgreSQL (ADR 0004). Пароли — в настройках, имена — константы.
MIGRATOR_ROLE = "migrator"
APP_SERVICE_ROLE = "app_service"
LLM_READONLY_ROLE = "llm_readonly"


class Settings(BaseSettings):
    """Настройки сервиса из переменных окружения с префиксом APP_ (и файла .env)."""

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class DatabaseSettings(BaseSettings):
    """Подключение к PostgreSQL из переменных с префиксом DB_.

    admin — суперпользователь контейнера, нужен только для создания ролей (bootstrap).
    """

    model_config = SettingsConfigDict(env_prefix="DB_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    name: str = "bookstore"
    admin_user: str = "postgres"
    admin_password: SecretStr
    migrator_password: SecretStr
    app_service_password: SecretStr
    llm_readonly_password: SecretStr

    def password_for(self, role: str) -> SecretStr:
        passwords = {
            self.admin_user: self.admin_password,
            MIGRATOR_ROLE: self.migrator_password,
            APP_SERVICE_ROLE: self.app_service_password,
            LLM_READONLY_ROLE: self.llm_readonly_password,
        }
        return passwords[role]

    def dsn(self, role: str, *, driver: str = "postgresql") -> str:
        """DSN для роли; driver="postgresql+asyncpg" — для SQLAlchemy в Alembic."""
        password = quote(self.password_for(role).get_secret_value(), safe="")
        return f"{driver}://{role}:{password}@{self.host}:{self.port}/{self.name}"
