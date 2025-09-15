#!/usr/bin/env python
# -*- coding: utf-8 -*-

from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core import openai
from app.utils.reload_config import RELOAD_CONFIG
from app.utils.logger import setup_logger
from app.utils.token_pool import initialize_token_pool

from granian import Granian


# Setup logger
logger = setup_logger(log_dir="logs", debug_mode=settings.DEBUG_LOGGING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    token_list = settings.auth_token_list
    if token_list:
        token_pool = initialize_token_pool(
            tokens=token_list,
            failure_threshold=settings.TOKEN_FAILURE_THRESHOLD,
            recovery_timeout=settings.TOKEN_RECOVERY_TIMEOUT
        )

    yield

    logger.info("🔄 应用正在关闭...")


# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Include API routers
app.include_router(openai.router)


@app.options("/")
async def handle_options():
    """Handle OPTIONS requests"""
    return Response(status_code=200)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "OpenAI Compatible API Server"}


def run_server():
    Granian(
        "main:app",
        interface="asgi",
        address="0.0.0.0",
        port=settings.LISTEN_PORT,
        reload=False,  # 生产环境请关闭热重载
        **RELOAD_CONFIG,
    ).serve()


if __name__ == "__main__":
    run_server()
