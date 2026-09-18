# engine/commands.py
"""Canal entre a thread do servidor e a thread de render.

A thread de render e a unica dona do contexto OpenGL. Tudo que vem da rede
precisa atravessar esta fila; nenhuma outra thread chama a libprojectM.
"""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class LoadPreset:
    """Troca o preset em exibicao. smooth=False faz corte seco."""
    path: str
    smooth: bool = True


@dataclass(frozen=True)
class SetBeatSensitivity:
    """Reatividade a batida."""
    value: float


@dataclass(frozen=True)
class SetMeshSize:
    """Resolucao da malha de deformacao. Valvula de performance e estetica."""
    width: int
    height: int


@dataclass(frozen=True)
class Shutdown:
    """Pede o encerramento ordenado do loop de render."""


Command = Union[LoadPreset, SetBeatSensitivity, SetMeshSize, Shutdown]


class CommandQueue:
    """Fila de mao unica: servidor escreve, render drena uma vez por quadro."""

    def __init__(self, maxsize: int = 64) -> None:
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)

    def send(self, command: Command) -> bool:
        """Enfileira sem bloquear. Devolve False se a fila estiver cheia.

        Nao bloqueia de proposito: se o loop de render travar, o servidor
        precisa continuar respondendo em vez de pendurar junto.
        """
        try:
            self._queue.put_nowait(command)
            return True
        except queue.Full:
            return False

    def drain(self) -> list[Command]:
        """Remove e devolve tudo que esta pendente, na ordem de chegada."""
        pending: list[Command] = []
        while True:
            try:
                pending.append(self._queue.get_nowait())
            except queue.Empty:
                return pending


@dataclass(frozen=True)
class EngineState:
    """Instantaneo do que o motor esta fazendo. Imutavel de proposito."""
    preset_path: str = ""
    preset_name: str = ""
    fps: float = 0.0
    audio_peak: float = 0.0
    audio_connected: bool = False
    frame: int = 0


class StatePublisher:
    """Publica o estado do motor para leitores de outras threads.

    Como EngineState e congelado, trocar a referencia sob lock basta: quem le
    recebe um instantaneo coerente, nunca um objeto meio atualizado.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = EngineState()

    def publish(self, state: EngineState) -> None:
        """Substitui o estado corrente."""
        with self._lock:
            self._state = state

    def read(self) -> EngineState:
        """Devolve o estado corrente."""
        with self._lock:
            return self._state
