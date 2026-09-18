"""Captura do audio do sistema e o buffer que a alimenta o render.

O dispositivo de loopback roda na taxa nativa da saida (48 kHz nesta maquina,
nao 44,1). A libprojectM nao assume taxa nenhuma: ela consome amostras e
deriva bass/mid/treb por bandas do espectro. Entao alimentamos como vem.
"""
from __future__ import annotations

import threading

import numpy as np
import pyaudiowpatch as pyaudio


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


class LoopbackUnavailable(Exception):
    """Nao ha dispositivo de loopback utilizavel para a saida padrao."""


def find_loopback_device() -> dict:
    """Acha o dispositivo de loopback que corresponde a saida padrao do Windows."""
    audio = pyaudio.PyAudio()
    try:
        try:
            wasapi = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError as exc:
            raise LoopbackUnavailable(f"WASAPI indisponivel: {exc}") from exc
        speakers = audio.get_device_info_by_index(wasapi["defaultOutputDevice"])
        for device in audio.get_loopback_device_info_generator():
            if speakers["name"] in device["name"]:
                return device
        raise LoopbackUnavailable(
            f"nenhum loopback casou com a saida padrao ({speakers['name']})")
    finally:
        audio.terminate()


class LoopbackCapture:
    """Thread que despeja o audio da saida padrao dentro de um AudioBuffer.

    Se o dispositivo sumir ou falhar em runtime, a thread encerra e `connected`
    passa a False - o motor continua desenhando, so sem reagir ao som.
    """

    CHUNK = 1024

    def __init__(self, buffer: AudioBuffer) -> None:
        self._buffer = buffer
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._running = threading.Event()
        self.sample_rate = 0
        self.channels = 0

    @property
    def connected(self) -> bool:
        """Se a captura esta ativa neste momento."""
        return self._running.is_set()

    def start(self) -> None:
        """Sobe a thread de captura. Nao bloqueia."""
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="audio", daemon=True)
        self._thread.start()

    def wait_until_running(self, timeout: float = 5.0) -> bool:
        """Espera a captura comecar de fato. Util em teste e na subida do app."""
        return self._running.wait(timeout)

    def stop(self) -> None:
        """Pede parada e espera a thread sair."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._running.clear()

    def _run(self) -> None:
        audio = pyaudio.PyAudio()
        stream = None
        try:
            device = find_loopback_device()
            self.sample_rate = int(device["defaultSampleRate"])
            self.channels = int(device["maxInputChannels"])
            stream = audio.open(format=pyaudio.paFloat32, channels=self.channels,
                                rate=self.sample_rate, input=True,
                                input_device_index=device["index"],
                                frames_per_buffer=self.CHUNK)
            self._running.set()
            while not self._stop.is_set():
                raw = stream.read(self.CHUNK, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.float32).reshape(-1, self.channels)
                self._buffer.write(samples)
        except Exception:
            pass  # dispositivo sumiu ou falhou: encerra em silencio, motor segue
        finally:
            self._running.clear()
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            audio.terminate()
