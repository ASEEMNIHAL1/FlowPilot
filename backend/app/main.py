from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.db as db_module
from app.api.routes import router
from app.config import get_settings
from app.db import init_db
from app.services.seed import seed_if_empty


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        # Access SessionLocal through the module so that the startup handler
        # always uses the engine set by configure_engine() (important in tests).
        db = db_module.SessionLocal()
        try:
            seed_if_empty(db, get_settings())
        finally:
            db.close()

    return app


app = create_app()
