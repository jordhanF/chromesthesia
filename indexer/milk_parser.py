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


# acrescentar em indexer/milk_parser.py
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PresetFeatures:
    """Vetor de features de um preset, extraido apenas do texto do arquivo."""
    path: str
    name: str
    family: str
    subfamily: str
    is_mirror: bool
    # movimento
    warp_anim_speed: float
    zoom: float
    rot: float
    warp: float
    zoom_exponent: float
    sx: float
    sy: float
    # persistencia
    decay: float
    echo_alpha: float
    echo_zoom: float
    # luz
    gamma: float
    brighten: bool
    darken: bool
    invert: bool
    solarize: bool
    darken_center: bool
    # cor
    wave_r: float
    wave_g: float
    wave_b: float
    wave_alpha: float
    # densidade
    n_shapes: int
    n_waves: int
    has_warp_shader: bool
    has_comp_shader: bool
    psversion: int


def _read_preset_text(path: Path) -> str:
    """Le o texto de um preset, tolerando caminhos que passam de MAX_PATH.

    Corrigido durante a Tarefa 5: 1 dos 9.795 presets do corpus real tem um
    nome de arquivo longo o bastante para que o caminho completo ultrapasse
    os 260 caracteres do limite classico do Windows. rglob() ainda encontra
    esse arquivo (a enumeracao de diretorio aceita caminhos longos), mas
    abri-lo pelo caminho normal falha com FileNotFoundError. O prefixo de
    caminho estendido (\\\\?\\) contorna isso sem exigir mudanca de registro
    do Windows (LongPathsEnabled).
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        if os.name != "nt":
            raise
        resolved = str(path.resolve())
        if not resolved.startswith("\\\\?\\"):
            resolved = "\\\\?\\" + resolved
        with open(resolved, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()


def parse_preset_file(path: Path, preset_root: Path) -> PresetFeatures:
    """Le um .milk do disco e devolve seu vetor de features.

    Os padroes sao as medianas do corpus, para que um campo ausente nao
    desloque o preset no espaco de features.
    """
    text = _read_preset_text(path)
    raw = parse_milk_text(text)
    family, subfamily, is_mirror = derive_taxonomy(path, preset_root)
    return PresetFeatures(
        path=str(path),
        name=path.stem,
        family=family,
        subfamily=subfamily,
        is_mirror=is_mirror,
        warp_anim_speed=read_float(raw, "fWarpAnimSpeed", 0.63),
        zoom=read_float(raw, "zoom", 1.0),
        rot=read_float(raw, "rot", 0.0),
        warp=read_float(raw, "warp", 0.0),
        zoom_exponent=read_float(raw, "fZoomExponent", 1.0),
        sx=read_float(raw, "sx", 1.0),
        sy=read_float(raw, "sy", 1.0),
        decay=read_float(raw, "fDecay", 0.96),
        echo_alpha=read_float(raw, "fVideoEchoAlpha", 0.0),
        echo_zoom=read_float(raw, "fVideoEchoZoom", 1.0),
        gamma=read_float(raw, "fGammaAdj", 1.21),
        brighten=read_bool(raw, "bBrighten"),
        darken=read_bool(raw, "bDarken"),
        invert=read_bool(raw, "bInvert"),
        solarize=read_bool(raw, "bSolarize"),
        darken_center=read_bool(raw, "bDarkenCenter"),
        wave_r=read_float(raw, "wave_r", 0.0),
        wave_g=read_float(raw, "wave_g", 0.0),
        wave_b=read_float(raw, "wave_b", 0.0),
        wave_alpha=read_float(raw, "fWaveAlpha", 0.0),
        n_shapes=count_enabled(raw, "shapecode"),
        n_waves=count_enabled(raw, "wavecode"),
        has_warp_shader=has_shader(raw, "warp"),
        has_comp_shader=has_shader(raw, "comp"),
        psversion=read_int(raw, "PSVERSION", 0),
    )
