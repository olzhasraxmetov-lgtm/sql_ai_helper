"""Точка сборки: настройки → приложение. Запуск: uvicorn sql_helper.main:app."""

import logging

from sql_helper.config import Settings
from sql_helper.presentation.api.app import create_app

settings = Settings()
logging.basicConfig(level=settings.log_level)
app = create_app(settings)
