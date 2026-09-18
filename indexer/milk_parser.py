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


# acrescentar em indexer/milk_parser.py
import re

_ENABLED_RE = "^{prefix}_(\\d+)_enabled$"


def count_enabled(raw: dict[str, str], prefix: str) -> int:
    """Conta quantos blocos indexados do prefixo estao com enabled=1.

    prefix e 'shapecode' ou 'wavecode'.
    """
    pattern = re.compile(_ENABLED_RE.format(prefix=re.escape(prefix)))
    return sum(1 for key, value in raw.items()
               if pattern.match(key) and read_float({"v": value}, "v", 0.0) >= 0.5)


def has_shader(raw: dict[str, str], kind: str) -> bool:
    """Diz se o preset traz um shader HLSL proprio. kind e 'warp' ou 'comp'."""
    return f"{kind}_1" in raw


# acrescentar em indexer/milk_parser.py
from pathlib import Path


def derive_taxonomy(path: Path, preset_root: Path) -> tuple[str, str, bool]:
    """Extrai (familia, subfamilia, espelhado) do caminho do preset.

    O layout esperado e <preset_root>/<pack>/<Familia>/<Subfamilia>/arquivo.milk.
    Presets direto na familia devolvem subfamilia vazia. Caminhos fora da raiz
    devolvem ('', '', False).
    """
    try:
        parts = path.relative_to(preset_root).parts
    except ValueError:
        return ("", "", False)
    if len(parts) < 3:
        return ("", "", False)
    family = parts[1]
    subfamily = parts[2] if len(parts) >= 4 else ""
    is_mirror = subfamily.endswith(" Mirror")
    return (family, subfamily, is_mirror)
