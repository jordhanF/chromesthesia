# server/ws.py
"""WebSocket: o estado do motor sai, comandos entram.

O empurrao periodico de estado e o que mantem a UI do celular viva sem
polling. A frequencia e baixa de proposito - e informacao de status, nao
telemetria de quadro.
"""
from __future__ import annotations

import asyncio
import dataclasses

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from engine.commands import (CommandQueue, LoadPreset, SetBeatSensitivity,
                             SetMeshSize, StatePublisher)

PUSH_INTERVAL = 0.25


def build_ws_router(commands: CommandQueue, state: StatePublisher) -> APIRouter:
    """Monta o roteador do WebSocket."""
    router = APIRouter()

    @router.websocket("/ws")
    async def endpoint(websocket: WebSocket) -> None:
        await websocket.accept()

        async def push_state() -> None:
            while True:
                await websocket.send_json(
                    {"type": "state", **dataclasses.asdict(state.read())})
                await asyncio.sleep(PUSH_INTERVAL)

        pusher = asyncio.create_task(push_state())
        try:
            while True:
                message = await websocket.receive_json()
                kind = message.get("type")
                if kind == "load":
                    commands.send(LoadPreset(path=message["path"],
                                             smooth=message.get("smooth", True)))
                elif kind == "beat_sensitivity":
                    commands.send(SetBeatSensitivity(float(message["value"])))
                elif kind == "mesh_size":
                    commands.send(SetMeshSize(int(message["width"]),
                                              int(message["height"])))
        except WebSocketDisconnect:
            pass
        finally:
            pusher.cancel()

    return router
