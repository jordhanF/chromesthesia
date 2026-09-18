# indexer/milk_parser.py
"""Parser do formato .milk (Milkdrop). Funcao pura: nao toca GL nem rede."""
from __future__ import annotations


def parse_milk_text(text: str) -> dict[str, str]:
    """Le um preset .milk como pares chave=valor brutos.

    Cabecalhos de secao ([preset00]) e linhas sem '=' sao ignorados.
    O valor nao e normalizado: linhas de shader dependem do espacamento.
    Chave repetida: a ultima vence.
    """
    raw: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("["):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        raw[key.strip()] = value.rstrip("\r\n")
    return raw
