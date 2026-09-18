# indexer/build_index.py
"""CLI: varre a arvore de presets e popula o indice SQLite.

Uso:
    python -m indexer.build_index
    python -m indexer.build_index --preset-root "C:/outro/presets"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config
from indexer.db import connect, count_presets, init_schema, upsert_preset
from indexer.milk_parser import parse_preset_file


def build(preset_root: Path, db_path: Path) -> tuple[int, int]:
    """Indexa todos os .milk sob preset_root. Devolve (indexados, falhas)."""
    con = connect(db_path)
    init_schema(con)
    paths = sorted(preset_root.rglob("*.milk"))
    total = len(paths)
    ok = failed = 0
    for i, path in enumerate(paths, 1):
        try:
            upsert_preset(con, parse_preset_file(path, preset_root))
            ok += 1
        except Exception as exc:  # um preset corrompido nao derruba a varredura
            failed += 1
            print(f"  FALHA {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
        if i % 500 == 0 or i == total:
            con.commit()
            print(f"  {i}/{total} ...", flush=True)
    con.commit()
    print(f"indice: {count_presets(con)} presets em {db_path}")
    con.close()
    return ok, failed


def main() -> int:
    ap = argparse.ArgumentParser(description="Constroi o indice de presets.")
    ap.add_argument("--preset-root", type=Path, default=config.PRESET_ROOT)
    ap.add_argument("--db", type=Path, default=config.DB_PATH)
    args = ap.parse_args()

    if not args.preset_root.is_dir():
        print(f"raiz de presets nao encontrada: {args.preset_root}", file=sys.stderr)
        return 1

    ok, failed = build(args.preset_root, args.db)
    print(f"indexados: {ok}  falhas: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
