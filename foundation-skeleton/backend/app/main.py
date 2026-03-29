import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.telemetry import configure_telemetry, instrument_fastapi
from app.db.session import engine

logging.basicConfig(level=logging.INFO)
settings = get_settings()
configure_telemetry(engine=engine)

app = FastAPI(title="Foundation Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
instrument_fastapi(app)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "foundation-backend", "status": "ok"}
