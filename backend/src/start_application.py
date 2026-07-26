from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from __init__ import __app_name__, __version__
from api import ROUTES
from api.analysis_controller import load_runs_from_db
from utils.config import Config
from utils.api_logger import get_logger, setup_logging

setup_logging()
log = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = Config.get()
    log.info("Starting %s v%s", cfg.app.name, cfg.app.version)
    upload_dir = Path(cfg.data.upload_dir)
    data_dir = Path(cfg.data.dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    log.info("Upload dir: %s", upload_dir)
    log.info("Database:    %s", cfg.data.db_path)
    log.info("Engine:      %s", cfg.engine.iseql_path)
    log.info("Available VLM providers: %s", Config.get_available_providers())
    
    # Load previous runs from database
    restored = load_runs_from_db()
    if restored > 0:
        log.info("Restored %d previous analysis run(s)", restored)
    
    yield
    log.info("Shutting down %s", cfg.app.name)

def create_app() -> FastAPI:
    cfg = Config.get()
    app = FastAPI(
        title=cfg.app.name,
        version=cfg.app.version,
        description=(
            "Three-condition ablation study for WATCHOUT ISEQL. "
            "A = visual only (VIS MODE baseline), "
            "B = PANNs CNN14 sound only, "
            "C = full multimodal (VLM + PANNs + ISEQL)."
        ),
        lifespan=lifespan,
    )

    cors_origins = cfg.server.cors_origins
    cors_origin_list = [o.strip() for o in cors_origins.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for path, controller in ROUTES.items():
        prefix = cfg.server.servlet.context_path
        full_path = prefix + path
        
        if hasattr(controller, 'on_get'):
            app.add_api_route(full_path, controller.on_get, methods=["GET"])
        if hasattr(controller, 'on_post'):
            app.add_api_route(full_path, controller.on_post, methods=["POST"])

    @app.get(cfg.server.servlet.context_path + "/health")
    async def health() -> dict:
        return {
            "app": cfg.app.name,
            "version": cfg.app.version,
            "status": "ok",
            "conditions": ["A", "B", "C"],
            "available_providers": Config.get_available_providers(),
        }

    return app

StartApplication = create_app()

if __name__ == '__main__':
    cfg = Config.get()
    HOST = cfg.server.host
    PORT = cfg.server.port
    uvicorn.run("start_application:StartApplication", host=HOST, port=PORT, reload=True)
