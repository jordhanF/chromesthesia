"""Captura do audio do sistema e o buffer que a alimenta o render.

O dispositivo de loopback roda na taxa nativa da saida (48 kHz nesta maquina,
nao 44,1). A libprojectM nao assume taxa nenhuma: ela consome amostras e
deriva bass/mid/treb por bandas do espectro. Entao alimentamos como vem.
"""
from __future__ import annotations

import threading

import numpy as np


class AudioBuffer:
    """Buffer circular: a thread de captura escreve, a de render le o final.

    Nao ha garantia de continuidade entre leituras consecutivas, e nao
    precisa haver: o visualizador quer "o audio recente", nao um fluxo
    perfeitamente emendado.
    """

    def __init__(self, capacity: int = 48000, channels: int = 2) -> None:
        self._capacity = capacity
        self._channels = channels
        self._buffer = np.zeros((capacity, channels), dtype=np.float32)
        self._write_pos = 0
        self._written = 0
        self._lock = threading.Lock()

    def write(self, chunk: np.ndarray) -> None:
        """Escreve um bloco (n, canais). Bloco maior que a capacidade: guarda o final."""
        chunk = np.ascontiguousarray(chunk, dtype=np.float32)
        if chunk.shape[0] > self._capacity:
            chunk = chunk[-self._capacity:]
        n = chunk.shape[0]
        if n == 0:
            return
        with self._lock:
            end = self._write_pos + n
            if end <= self._capacity:
                self._buffer[self._write_pos:end] = chunk
            else:
                head = self._capacity - self._write_pos
                self._buffer[self._write_pos:] = chunk[:head]
                self._buffer[:n - head] = chunk[head:]
            self._write_pos = end % self._capacity
            self._written += n

    def read_latest(self, n: int) -> np.ndarray:
        """Devolve as n amostras mais recentes, em ordem cronologica."""
        n = min(n, self._capacity)
        with self._lock:
            start = (self._write_pos - n) % self._capacity
            if start + n <= self._capacity:
                return self._buffer[start:start + n].copy()
            head = self._capacity - start
            return np.concatenate([self._buffer[start:], self._buffer[:n - head]])

    @property
    def total_written(self) -> int:
        """Quantas amostras ja passaram pelo buffer desde a criacao."""
        with self._lock:
            return self._written
