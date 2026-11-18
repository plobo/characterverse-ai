from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import assets, auth, characters, media, mixes, projects
from app.core.config import Settings, get_settings
from app.core.container import Container, build_container
from app.core.errors import install_error_handlers
from app.schemas.api import ErrorResponse

API_VERSION = "1.0.0"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app.workers.queue import InlineQueue, ThreadQueue, cleanup_expired_temp, start_sweeper, sweep_render_jobs

        stop_sweeper = None
        if not isinstance(container.queue, InlineQueue):
            sweep_render_jobs(container)
            cleanup_expired_temp(container)
            stop_sweeper = start_sweeper(container)
        yield
        if stop_sweeper:
            stop_sweeper.set()
        if isinstance(container.queue, ThreadQueue):
            container.queue.stop()

    app = FastAPI(
        title="CharacterVerse AI API",
        version=API_VERSION,
        description="Original-character 3D animation studio. All endpoints require a Bearer session except "
        "/healthz, /v1/auth/session, the public catalogue and signed media URLs.",
        lifespan=lifespan,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    app.state.container = container
    install_error_handlers(app)
    for module in (auth, assets, characters, mixes, projects, media):
        app.include_router(module.router)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict:
        return {"status": "ok", "apiVersion": API_VERSION, "manifestVersion": container.catalog.manifest_version}

    return app


def app_factory() -> FastAPI:  # uvicorn --factory app.main:app_factory
    return create_app()
