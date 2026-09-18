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


# acrescentar em indexer/milk_parser.py
def read_float(raw: dict[str, str], key: str, default: float = 0.0) -> float:
    """Le um campo como float, caindo no padrao se ausente ou malformado."""
    try:
        return float(raw[key].strip())
    except (KeyError, ValueError, AttributeError):
        return default


def read_int(raw: dict[str, str], key: str, default: int = 0) -> int:
    """Le um campo como int. Valores como '2.000' sao truncados."""
    return int(read_float(raw, key, float(default)))


def read_bool(raw: dict[str, str], key: str, default: bool = False) -> bool:
    """Le um campo booleano do Milkdrop (0/1) como bool."""
    return read_float(raw, key, 1.0 if default else 0.0) >= 0.5
