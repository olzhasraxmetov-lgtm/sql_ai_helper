from fastapi import FastAPI

from sql_helper.config import Settings
from sql_helper.presentation.api import health


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="SQL helper для книжного магазина")
    app.state.settings = settings
    app.include_router(health.router)
    return app
