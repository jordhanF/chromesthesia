"""Fontes de sinal de referencia para renderizar previews comparaveis.

Todo preview do corpus precisa reagir ao MESMO estimulo, senao o grid nao
serve para comparar nada. O cache de previews e versionado pelo hash do
sinal, entao trocar de fonte nao corrompe a comparabilidade: comeca um
cache novo.
"""
from __future__ import annotations

import hashlib

import numpy as np

import config


def synthetic_signal(seconds: float = 10.0, bpm: float = 120.0) -> np.ndarray:
    """Gera o sinal sintetico deterministico de referencia.

    Kick grave com envelope percussivo, pad medio sustentado e hi-hat agudo
    no mesmo envelope. Devolve float32 no formato (n, 2).
    """
    n = int(config.SAMPLE_RATE * seconds)
    t = np.arange(n, dtype=np.float64)
    beat = config.SAMPLE_RATE * 60.0 / bpm
    env = np.exp(-((t % beat) / (beat * 0.12)))

    kick = 0.80 * env * np.sin(2 * np.pi * 60.0 * t / config.SAMPLE_RATE)
    pad = 0.25 * np.sin(2 * np.pi * 1500.0 * t / config.SAMPLE_RATE)
    hat = 0.15 * env * np.sin(2 * np.pi * 8000.0 * t / config.SAMPLE_RATE)

    mono = np.clip(kick + pad + hat, -1.0, 1.0).astype(np.float32)
    return np.stack([mono, mono], axis=1)


def signal_hash(signal: np.ndarray) -> str:
    """Identidade curta e estavel do sinal, usada para versionar o cache."""
    return hashlib.sha256(np.ascontiguousarray(signal, dtype=np.float32).tobytes()
                          ).hexdigest()[:12]
