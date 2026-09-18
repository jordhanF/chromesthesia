# indexer/db.py
"""Esquema e acesso ao indice SQLite dos presets.

SQLite e nao JSON porque a Fase 2 (pad de emocao) consulta por faixa de
valores sobre as features - WHERE decay BETWEEN ? AND ? AND n_shapes > ?.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Iterator

from indexer.milk_parser import PresetFeatures

SCHEMA = """
CREATE TABLE IF NOT EXISTS presets (
    path             TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    family           TEXT NOT NULL,
    subfamily        TEXT NOT NULL,
    is_mirror        INTEGER NOT NULL,
    warp_anim_speed  REAL NOT NULL,
    zoom             REAL NOT NULL,
    rot              REAL NOT NULL,
    warp             REAL NOT NULL,
    zoom_exponent    REAL NOT NULL,
    sx               REAL NOT NULL,
    sy               REAL NOT NULL,
    decay            REAL NOT NULL,
    echo_alpha       REAL NOT NULL,
    echo_zoom        REAL NOT NULL,
    gamma            REAL NOT NULL,
    brighten         INTEGER NOT NULL,
    darken           INTEGER NOT NULL,
    invert           INTEGER NOT NULL,
    solarize         INTEGER NOT NULL,
    darken_center    INTEGER NOT NULL,
    wave_r           REAL NOT NULL,
    wave_g           REAL NOT NULL,
    wave_b           REAL NOT NULL,
    wave_alpha       REAL NOT NULL,
    n_shapes         INTEGER NOT NULL,
    n_waves          INTEGER NOT NULL,
    has_warp_shader  INTEGER NOT NULL,
    has_comp_shader  INTEGER NOT NULL,
    psversion        INTEGER NOT NULL,
    contrast         REAL,
    motion           REAL,
    poster_sig       TEXT
);
CREATE INDEX IF NOT EXISTS ix_presets_family ON presets(family, subfamily);
CREATE INDEX IF NOT EXISTS ix_presets_poster ON presets(poster_sig);
"""

_COLUMNS = [
    "path", "name", "family", "subfamily", "is_mirror", "warp_anim_speed", "zoom",
    "rot", "warp", "zoom_exponent", "sx", "sy", "decay", "echo_alpha", "echo_zoom",
    "gamma", "brighten", "darken", "invert", "solarize", "darken_center", "wave_r",
    "wave_g", "wave_b", "wave_alpha", "n_shapes", "n_waves", "has_warp_shader",
    "has_comp_shader", "psversion",
]


def connect(db_path: Path) -> sqlite3.Connection:
    """Abre o banco criando o diretorio se preciso. Linhas viram sqlite3.Row."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def init_schema(con: sqlite3.Connection) -> None:
    """Cria tabelas e indices. Reentrante."""
    con.executescript(SCHEMA)
    con.commit()


def upsert_preset(con: sqlite3.Connection, features: PresetFeatures) -> None:
    """Insere ou atualiza um preset. A chave e o caminho do arquivo.

    Nao mexe em contrast/motion/poster_sig: quem escreve isso e o gerador
    de posters.
    """
    data = asdict(features)
    values = [data[c] for c in _COLUMNS]
    placeholders = ", ".join("?" for _ in _COLUMNS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in _COLUMNS if c != "path")
    con.execute(
        f"INSERT INTO presets ({', '.join(_COLUMNS)}) VALUES ({placeholders}) "
        f"ON CONFLICT(path) DO UPDATE SET {updates}",
        values,
    )


def count_presets(con: sqlite3.Connection) -> int:
    """Quantidade de presets no indice."""
    return int(con.execute("SELECT COUNT(*) FROM presets").fetchone()[0])


def iter_presets(con: sqlite3.Connection, family: str | None = None,
                 subfamily: str | None = None) -> Iterator[sqlite3.Row]:
    """Percorre presets, opcionalmente filtrando por familia/subfamilia."""
    sql = "SELECT * FROM presets"
    where, params = [], []
    if family is not None:
        where.append("family = ?")
        params.append(family)
    if subfamily is not None:
        where.append("subfamily = ?")
        params.append(subfamily)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY family, subfamily, name"
    yield from con.execute(sql, params)
