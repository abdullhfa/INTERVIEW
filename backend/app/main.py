"""
AI Interview Coach - FastAPI Application Entry Point

Registers all routes, middleware, WebSocket endpoints, and lifecycle events.
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

def _configure_windows_asyncio() -> None:
    """Prefer SelectorEventLoop on Windows for subprocess/audio compatibility."""
    if sys.platform != "win32":
        return

    if sys.version_info >= (3, 14):
        asyncio.EventLoop = asyncio.SelectorEventLoop
        return

    set_event_loop_policy = getattr(asyncio, "set_event_loop_policy", None)
    policy_cls = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if set_event_loop_policy is not None and policy_cls is not None:
        set_event_loop_policy(policy_cls())


_configure_windows_asyncio()

# Keep the live pipeline stages visible in the server log. Uvicorn's default
# logging configuration otherwise hides application INFO diagnostics.
_app_logger = logging.getLogger("app")
_app_logger.setLevel(logging.INFO)
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    _app_logger.addHandler(_handler)
_app_logger.propagate = True

from app.config import settings
from app.db.database import init_db, close_db
from app.db.repository import repository
from app.services.candidate_profile import candidate_profile_service
from app.services.session_manager import session_manager
from app.services.gemini_gateway import gemini
from app.audio.whisper_stt import warm_whisper_model, active_stt_info
from app.services.question_bank import question_bank
from app.services.warm_start import warm_system, system_warm_state, is_system_warm


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown."""
    # Startup
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.chroma_dir, exist_ok=True)
    profiles = await repository.load_all_profiles()
    candidate_profile_service._profiles = profiles
    sessions = await repository.load_all_sessions()
    session_manager._sessions = sessions

    async def _warm_backends() -> None:
        # Phase 11 warm start: models, indexes, and one real decode/embedding so
        # the first live interview question never pays initialisation cost.
        results = await asyncio.gather(
            gemini.warm_connection(),
            warm_system(),
            return_exceptions=True,
        )
        for name, result in zip(("llm", "system"), results):
            if isinstance(result, Exception):
                logging.getLogger("app").warning("Background warm-up failed (%s): %s", name, result)

    # Do not block HTTP startup — blocking here caused Vite proxy 502 Bad Gateway.
    asyncio.create_task(_warm_backends(), name="backend-warmup")
    
    yield
    # Shutdown
    await session_manager.drain_persistence()
    await close_db()


app = FastAPI(
    title="AI Interview Coach",
    description="Intelligent interview preparation and real-time coaching system",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route Registration ──────────────────────────────────────────
from app.api.routes_candidate import router as candidate_router
from app.api.routes_interview import router as interview_router
from app.api.routes_analytics import router as analytics_router
from app.api.routes_audio import router as audio_router
from app.api.ws_interview import router as ws_router
from app.api.routes_question_bank import router as question_bank_router

app.include_router(candidate_router, prefix="/api/candidates", tags=["Candidates"])
app.include_router(interview_router, prefix="/api/interviews", tags=["Interviews"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(audio_router, prefix="/api/audio", tags=["Audio"])
app.include_router(ws_router, prefix="/ws", tags=["WebSocket"])
app.include_router(question_bank_router, prefix="/api/question-bank", tags=["Question Bank"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a readable error instead of a bare Internal Server Error."""
    if isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)

    logging.getLogger("app").exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    detail = str(exc).strip() or exc.__class__.__name__
    return JSONResponse(
        status_code=500,
        content={"detail": f"خطأ في الخادم: {detail}"},
    )


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "pipeline": "stt-whisper-v4-no-think",
        "stt_timeout_seconds": settings.stt_timeout_seconds,
        "stt_retry_timeout_seconds": settings.stt_retry_timeout_seconds,
        "stt_languages": settings.stt_languages,
        "whisper_stt_enabled": settings.whisper_stt_enabled,
        "whisper_model_size": settings.whisper_model_size,
        "whisper_active": active_stt_info(),
        "whisper_language": settings.whisper_language,
        "question_bank_enabled": settings.question_bank_enabled,
        "question_bank_entries": len(question_bank.entries),
        "deepseek_model": settings.deepseek_model,
        "SYSTEM_WARM": is_system_warm(),
    }


@app.get("/api/health/warm")
async def warm_state():
    """Warm-start detail: which stage is ready and how long each one took."""
    return system_warm_state()
