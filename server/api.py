# server/api.py
"""Endpoints REST sobre o indice de presets.

O id publico de um preset e o rowid do SQLite: estavel entre reconstrucoes do
indice enquanto o caminho nao mudar, e seguro para URL - ao contrario do nome,
que tem espacos, acentos e pontuacao.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from engine.commands import CommandQueue, LoadPreset, StatePublisher
from server.similarity import FEATURE_COLUMNS, nearest_ids, normalize_matrix


def build_router(db_path: Path, preview_dir: Path, commands: CommandQueue,
                 state: StatePublisher) -> APIRouter:
    """Monta o roteador. Recebe as dependencias para ser testavel isoladamente."""
    router = APIRouter(prefix="/api")

    def _connect() -> sqlite3.Connection:
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        return con

    def _fetch_one(preset_id: int) -> sqlite3.Row:
        con = _connect()
        try:
            row = con.execute(
                "SELECT rowid AS id, * FROM presets WHERE rowid = ?",
                (preset_id,)).fetchone()
        finally:
            con.close()
        if row is None:
            raise HTTPException(status_code=404, detail="preset nao encontrado")
        return row

    @router.get("/families")
    def families() -> list[dict]:
        """Familias com quantidade de presets, da maior para a menor."""
        con = _connect()
        try:
            return [{"family": r["family"], "count": r["n"]} for r in con.execute(
                "SELECT family, COUNT(*) n FROM presets GROUP BY family ORDER BY n DESC")]
        finally:
            con.close()

    @router.get("/subfamilies")
    def subfamilies(family: str) -> list[dict]:
        """Subfamilias de uma familia, com quantidade."""
        con = _connect()
        try:
            return [{"subfamily": r["subfamily"], "count": r["n"]} for r in con.execute(
                "SELECT subfamily, COUNT(*) n FROM presets WHERE family = ? "
                "GROUP BY subfamily ORDER BY subfamily", (family,))]
        finally:
            con.close()

    @router.get("/presets")
    def presets(family: str | None = None, subfamily: str | None = None,
                limit: int = Query(60, ge=1, le=500),
                offset: int = Query(0, ge=0)) -> dict:
        """Pagina de presets, opcionalmente filtrada."""
        where, params = [], []
        if family is not None:
            where.append("family = ?")
            params.append(family)
        if subfamily is not None:
            where.append("subfamily = ?")
            params.append(subfamily)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        con = _connect()
        try:
            total = con.execute(f"SELECT COUNT(*) FROM presets{clause}",
                                params).fetchone()[0]
            rows = con.execute(
                f"SELECT rowid AS id, name, family, subfamily, contrast, motion, "
                f"poster_sig FROM presets{clause} ORDER BY family, subfamily, name "
                f"LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
        finally:
            con.close()
        return {
            "total": total,
            "items": [{"id": r["id"], "name": r["name"], "family": r["family"],
                       "subfamily": r["subfamily"], "contrast": r["contrast"],
                       "motion": r["motion"], "has_poster": r["poster_sig"] is not None}
                      for r in rows],
        }

    @router.get("/poster/{preset_id}")
    def poster(preset_id: int) -> FileResponse:
        """O poster WebP do preset, se ja tiver sido renderizado."""
        row = _fetch_one(preset_id)
        if row["poster_sig"] is None:
            raise HTTPException(status_code=404, detail="poster ainda nao renderizado")
        path = preview_dir / row["poster_sig"] / f"{row['name']}.webp"
        if not path.exists():
            raise HTTPException(status_code=404, detail="arquivo de poster ausente")
        return FileResponse(path, media_type="image/webp")

    @router.get("/similar/{preset_id}")
    def similar(preset_id: int, k: int = Query(12, ge=1, le=60)) -> list[dict]:
        """Presets mais parecidos no espaco de features.

        A matriz e remontada a cada chamada. Para 9.795 presets x 17 colunas
        isso e ~1,3 MB e poucos milissegundos - nao vale cachear antes de
        medir que incomoda.
        """
        _fetch_one(preset_id)
        con = _connect()
        try:
            rows = con.execute(
                f"SELECT rowid AS id, name, family, subfamily, poster_sig, "
                f"{', '.join(FEATURE_COLUMNS)} FROM presets").fetchall()
        finally:
            con.close()
        ids = [r["id"] for r in rows]
        matrix = normalize_matrix(
            np.array([[r[c] for c in FEATURE_COLUMNS] for r in rows], dtype=np.float64))
        chosen = nearest_ids(matrix, ids, preset_id, k)
        by_id = {r["id"]: r for r in rows}
        return [{"id": i, "name": by_id[i]["name"], "family": by_id[i]["family"],
                 "subfamily": by_id[i]["subfamily"],
                 "has_poster": by_id[i]["poster_sig"] is not None} for i in chosen]

    @router.post("/load/{preset_id}")
    def load(preset_id: int, smooth: bool = True) -> dict:
        """Manda o motor trocar para este preset."""
        row = _fetch_one(preset_id)
        accepted = commands.send(LoadPreset(path=row["path"], smooth=smooth))
        return {"accepted": accepted, "name": row["name"]}

    @router.get("/state")
    def engine_state() -> dict:
        """O que o motor esta fazendo agora."""
        return dataclasses.asdict(state.read())

    return router
