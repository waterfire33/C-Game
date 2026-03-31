import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.telemetry import configure_telemetry, instrument_fastapi
from app.db.session import engine


import contextlib

@contextlib.asynccontextmanager
async def lifespan(app):
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if settings.enable_telemetry:
        configure_telemetry(engine=engine)
        instrument_fastapi(app)
    yield

settings = get_settings()
app = FastAPI(title="Foundation Backend", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "foundation-backend", "status": "ok"}
