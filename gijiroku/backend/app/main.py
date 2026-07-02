"""議事録 AI Agent — FastAPI エントリポイント。"""
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .logging_config import request_id_var, setup_logging
from .routers import auth as auth_router
from .routers import meetings as meetings_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    os.makedirs(get_settings().upload_dir, exist_ok=True)
    logger.info("議事録 AI Agent started")
    yield


app = FastAPI(title="議事録 AI Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    request_id_var.set(rid)
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    return response


app.include_router(auth_router.router)
app.include_router(meetings_router.router)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
