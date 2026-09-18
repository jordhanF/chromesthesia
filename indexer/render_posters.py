# indexer/render_posters.py
"""CLI: renderiza um poster estatico por preset.

Estrategia de duas camadas da spec: poster estatico para todo o corpus
(~150 MB, ~3,5 h), animado so sob demanda na Fase 1b.

O warmup existe por dois motivos. O AGC de bass/mid/treb precisa assentar -
os primeiros 50 frames usam convergencia rapida embutida na lib - e o buffer
de feedback do proprio preset precisa se desenvolver. Sem warmup, o mesmo
preset rende posters diferentes a cada execucao.

Uso:
    python -m indexer.render_posters
    python -m indexer.render_posters --family Hypnotic
    python -m indexer.render_posters --reference data/reference/captura.wav
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

import config
from engine.capture import read_frame
from engine.gl_context import GLContext
from engine.pm_ffi import ProjectM
from indexer.db import connect, init_schema, iter_presets
from indexer.reference import load_signal_file, signal_hash, synthetic_signal

RENDER_W, RENDER_H = 640, 360
POSTER_W, POSTER_H = 320, 180
WARMUP_FRAMES = 150
MOTION_FRAMES = 8


def _chunk(signal: np.ndarray, index: int) -> np.ndarray:
    """Pedaco de PCM para um frame, circulando no sinal de referencia."""
    size = config.PCM_CHUNK
    start = (index * size) % max(len(signal) - size, 1)
    return signal[start:start + size]


def render_one(pm: ProjectM, ctx: GLContext, preset: Path,
               signal: np.ndarray) -> tuple[Image.Image, float, float]:
    """Renderiza um preset e devolve (poster, contraste, movimento).

    contraste e o desvio-padrao do poster; movimento e a diferenca media entre
    frames consecutivos. Os dois separam preset vivo de preset morto.
    """
    pm.load_preset_file(preset, smooth=False)
    frame_index = 0
    for _ in range(WARMUP_FRAMES):
        pm.add_pcm(_chunk(signal, frame_index))
        pm.render_frame()
        ctx.swap()
        frame_index += 1

    captured = []
    for _ in range(MOTION_FRAMES):
        pm.add_pcm(_chunk(signal, frame_index))
        pm.render_frame()
        ctx.swap()
        frame_index += 1
        captured.append(read_frame(RENDER_W, RENDER_H).astype(np.float32))

    stack = np.stack(captured)
    contrast = float(stack[-1].std())
    motion = float(np.abs(np.diff(stack, axis=0)).mean())
    poster = Image.fromarray(captured[-1].astype(np.uint8)).resize(
        (POSTER_W, POSTER_H), Image.LANCZOS)
    return poster, contrast, motion


def main() -> int:
    ap = argparse.ArgumentParser(description="Renderiza posters dos presets.")
    ap.add_argument("--db", type=Path, default=config.DB_PATH)
    ap.add_argument("--family", default=None, help="limita a uma familia")
    ap.add_argument("--limit", type=int, default=0, help="0 = sem limite")
    ap.add_argument("--reference", type=Path, default=None,
                    help="arquivo de audio de referencia; padrao e o sinal sintetico")
    args = ap.parse_args()

    signal = load_signal_file(args.reference) if args.reference else synthetic_signal()
    sig = signal_hash(signal)
    out_dir = config.PREVIEW_DIR / sig
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"sinal de referencia: {args.reference or 'sintetico'}  hash={sig}")

    con = connect(args.db)
    init_schema(con)
    rows = list(iter_presets(con, family=args.family))
    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        print("nenhum preset no indice; rode python -m indexer.build_index",
              file=sys.stderr)
        return 1

    done = skipped = failed = 0
    started = time.time()
    with GLContext(RENDER_W, RENDER_H, visible=False, vsync=False) as ctx:
        for i, row in enumerate(rows, 1):
            dst = out_dir / f"{Path(row['path']).stem}.webp"
            if dst.exists() and row["poster_sig"] == sig:
                skipped += 1
                continue
            try:
                with ProjectM(RENDER_W, RENDER_H) as pm:
                    poster, contrast, motion = render_one(
                        pm, ctx, Path(row["path"]), signal)
                poster.save(dst, format="WEBP", quality=80, method=4)
                con.execute(
                    "UPDATE presets SET contrast=?, motion=?, poster_sig=? WHERE path=?",
                    (contrast, motion, sig, row["path"]))
                done += 1
            except Exception as exc:
                failed += 1
                print(f"  FALHA {row['name']}: {type(exc).__name__}: {exc}",
                      file=sys.stderr)
            if i % 25 == 0:
                con.commit()
                rate = (time.time() - started) / max(done, 1)
                restantes = (len(rows) - i) * rate / 60
                print(f"  {i}/{len(rows)}  {rate:.2f}s/preset  "
                      f"~{restantes:.0f} min restantes", flush=True)
    con.commit()
    con.close()
    print(f"posters: {done} novos, {skipped} pulados, {failed} falhas -> {out_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
