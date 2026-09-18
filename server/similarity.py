# server/similarity.py
"""Vizinhos mais proximos no espaco de features dos presets.

Distancia euclidiana sobre features normalizadas por coluna. Sem ML e sem
embeddings: o vetor ja e numerico e o corpus cabe em memoria.
"""
from __future__ import annotations

import numpy as np

#: Colunas do indice que compoem o vetor. Ordem fixa: mudar aqui muda a vizinhanca.
FEATURE_COLUMNS = [
    "warp_anim_speed", "zoom", "rot", "warp", "zoom_exponent", "sx", "sy",
    "decay", "echo_alpha", "echo_zoom", "gamma",
    "wave_r", "wave_g", "wave_b", "wave_alpha",
    "n_shapes", "n_waves",
]


def normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    """Leva cada coluna para [0, 1]. Coluna constante vira zero, nunca NaN."""
    matrix = np.asarray(matrix, dtype=np.float64)
    low = matrix.min(axis=0)
    span = matrix.max(axis=0) - low
    safe = np.where(span == 0.0, 1.0, span)
    scaled = (matrix - low) / safe
    return np.where(span == 0.0, 0.0, scaled)


def nearest_ids(matrix: np.ndarray, ids: list[int], target_id: int,
                k: int = 12) -> list[int]:
    """Os k ids mais proximos do alvo, do mais parecido para o menos.

    A matriz deve vir de normalize_matrix; o alvo nunca aparece no resultado.
    """
    try:
        index = ids.index(target_id)
    except ValueError as exc:
        raise KeyError(f"id {target_id} nao esta na matriz") from exc

    distances = np.linalg.norm(matrix - matrix[index], axis=1)
    distances[index] = np.inf
    order = np.argsort(distances)[:k]
    return [ids[i] for i in order if np.isfinite(distances[i])]
