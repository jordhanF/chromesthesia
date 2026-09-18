# server/main.py
"""Monta o FastAPI e o expoe na rede local.

Exposto em 0.0.0.0 de proposito: o controle roda no celular, em outro
aparelho da mesma rede.
"""
from __future__ import annotations

import socket
import threading

import uvicorn
from fastapi import FastAPI

import config
from engine.commands import CommandQueue, StatePublisher
from server.api import build_router
from server.ws import build_ws_router

HOST = "0.0.0.0"
PORT = 8765


def local_ip() -> str:
    """Endereco desta maquina na LAN, para imprimir na subida."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def build_app(commands: CommandQueue, state: StatePublisher) -> FastAPI:
    """Monta a aplicacao com as rotas REST e o WebSocket."""
    app = FastAPI(title="Chromesthesia")
    app.include_router(build_router(config.DB_PATH, config.PREVIEW_DIR, commands, state))
    app.include_router(build_ws_router(commands, state))

    # Montado por ultimo de proposito: montar a raiz antes dos include_router
    # capturaria /api e /ws, e a interface serviria HTML no lugar da API.
    ui_dist = config.PROJECT_ROOT / "ui" / "dist"
    if ui_dist.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app


def serve_in_thread(commands: CommandQueue, state: StatePublisher) -> threading.Thread:
    """Sobe o uvicorn numa thread propria. Nunca toca em OpenGL."""
    server = uvicorn.Server(uvicorn.Config(
        build_app(commands, state), host=HOST, port=PORT, log_level="warning"))
    thread = threading.Thread(target=server.run, name="server", daemon=True)
    thread.start()
    return thread
