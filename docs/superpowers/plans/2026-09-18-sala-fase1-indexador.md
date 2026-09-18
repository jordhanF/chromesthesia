# Sala — Fase 1a: núcleo + indexador de presets

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar os 9.795 arquivos `.milk` num índice SQLite consultável com posters visuais, para que a Fase 1b possa construir o navegador em cima.

**Architecture:** Dois pacotes. `engine/` contém o núcleo compartilhado com a Fase 1b — binding ctypes para `projectM-4.dll`, criação de contexto OpenGL e captura de frame. `indexer/` contém a pipeline offline — parser puro do formato `.milk`, fontes de sinal de referência, esquema SQLite e dois CLIs (construir índice, renderizar posters). Todo código que toca OpenGL fica atrás de `engine/`; o parser é função pura e concentra os testes.

**Tech Stack:** Python 3.11, ctypes, glfw, PyOpenGL, numpy, Pillow, miniaudio, PyAudioWPatch, SQLite (stdlib), pytest.

**Spec:** `docs/superpowers/specs/2026-09-18-sala-navegador-visual-design.md`

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `config.py` | Caminhos do projeto. Único lugar que conhece o layout do disco. |
| `engine/pm_ffi.py` | Binding ctypes para `projectM-4.dll`. Sem lógica de negócio. |
| `engine/gl_context.py` | Contexto OpenGL via glfw + `glewInit()`. Visível ou headless. |
| `engine/capture.py` | `glReadPixels` → `numpy.ndarray` já desvirado. |
| `indexer/milk_parser.py` | `.milk` → `PresetFeatures`. **Função pura**, sem GL, sem I/O de rede. |
| `indexer/reference.py` | Sinal de referência: sintético determinístico ou arquivo de áudio. |
| `indexer/db.py` | Esquema SQLite, upsert e consulta. |
| `indexer/build_index.py` | CLI: varre `presets/` → popula o banco. |
| `indexer/render_posters.py` | CLI: banco → posters WebP estáticos. |
| `indexer/capture_reference.py` | CLI: grava N segundos do loopback WASAPI como WAV. |

---

### Task 0: Esqueleto do projeto e configuração

**Files:**
- Create: `config.py`
- Create: `engine/__init__.py`, `indexer/__init__.py`, `tests/__init__.py`
- Create: `requirements.txt`

- [ ] **Step 1: Instalar pytest**

```bash
pip install pytest
```

- [ ] **Step 2: Criar os pacotes vazios**

```bash
cd C:/Users/Jordh/projectM
printf '' > engine/__init__.py
printf '' > indexer/__init__.py
printf '' > tests/__init__.py
```

- [ ] **Step 3: Criar `config.py`**

```python
"""Caminhos do projeto. Unico modulo que conhece o layout do disco."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

APP_DIR = Path(os.environ.get(
    "SALA_APP_DIR", PROJECT_ROOT / "app" / "projectMSDL-2.0.0-win64"))
DLL_PATH = APP_DIR / "projectM-4.dll"
GLEW_PATH = APP_DIR / "glew32.dll"
PRESET_ROOT = APP_DIR / "presets"
TEXTURE_DIR = APP_DIR / "textures"

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "index.sqlite"
PREVIEW_DIR = DATA_DIR / "previews"
REFERENCE_DIR = DATA_DIR / "reference"

SAMPLE_RATE = 44100
PCM_CHUNK = 576  # AudioBufferSamples da libprojectM
```

- [ ] **Step 4: Criar `requirements.txt`**

```
glfw
PyOpenGL
numpy
Pillow
miniaudio
PyAudioWPatch
fastapi
uvicorn
websockets
pytest
```

- [ ] **Step 5: Verificar que os caminhos existem**

Run: `python -c "import config; print(config.DLL_PATH.exists(), config.PRESET_ROOT.exists())"`
Expected: `True True`

- [ ] **Step 6: Commit**

```bash
git add config.py requirements.txt engine/__init__.py indexer/__init__.py tests/__init__.py
git commit -m "chore: esqueleto dos pacotes e configuracao de caminhos"
```

---

### Task 1: Parser — leitura bruta de chave=valor

**Files:**
- Create: `indexer/milk_parser.py`
- Test: `tests/test_milk_parser.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_milk_parser.py
from indexer.milk_parser import parse_milk_text


def test_le_pares_chave_valor():
    texto = "MILKDROP_PRESET_VERSION=201\nfDecay=0.980\nzoom=1.01191\n"
    assert parse_milk_text(texto) == {
        "MILKDROP_PRESET_VERSION": "201",
        "fDecay": "0.980",
        "zoom": "1.01191",
    }


def test_ignora_cabecalho_de_secao_e_linhas_vazias():
    texto = "[preset00]\n\nfDecay=0.5\n"
    assert parse_milk_text(texto) == {"fDecay": "0.5"}


def test_preserva_espacos_do_valor_em_linhas_de_shader():
    texto = "warp_3=`    ret = tex2D( sampler_main, uv ).xyz*.5;\n"
    assert parse_milk_text(texto)["warp_3"] == "`    ret = tex2D( sampler_main, uv ).xyz*.5;"


def test_linha_sem_igual_e_ignorada():
    assert parse_milk_text("lixo sem igual\nfDecay=0.5\n") == {"fDecay": "0.5"}
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'indexer.milk_parser'`

- [ ] **Step 3: Implementar o mínimo**

```python
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
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add indexer/milk_parser.py tests/test_milk_parser.py
git commit -m "feat(indexer): leitura bruta de chave=valor do formato .milk"
```

---

### Task 2: Parser — coerção de tipos com valores ausentes

**Files:**
- Modify: `indexer/milk_parser.py`
- Test: `tests/test_milk_parser.py`

Presets reais omitem campos. Toda leitura precisa de valor padrão explícito.

- [ ] **Step 1: Escrever o teste que falha**

```python
# acrescentar em tests/test_milk_parser.py
from indexer.milk_parser import read_bool, read_float, read_int


def test_read_float_usa_padrao_quando_ausente():
    assert read_float({}, "fDecay", 0.96) == 0.96


def test_read_float_usa_padrao_quando_invalido():
    assert read_float({"fDecay": "abc"}, "fDecay", 0.96) == 0.96


def test_read_float_aceita_espacos():
    assert read_float({"zoom": "  1.5 "}, "zoom", 0.0) == 1.5


def test_read_bool_trata_zero_e_um():
    assert read_bool({"bInvert": "1"}, "bInvert") is True
    assert read_bool({"bInvert": "0"}, "bInvert") is False
    assert read_bool({}, "bInvert") is False


def test_read_int_trunca_float():
    assert read_int({"PSVERSION": "2.000"}, "PSVERSION", 0) == 2
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'read_bool'`

- [ ] **Step 3: Implementar**

```python
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
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add indexer/milk_parser.py tests/test_milk_parser.py
git commit -m "feat(indexer): coercao de tipos com padroes para campos ausentes"
```

---

### Task 3: Parser — contagem de densidade

**Files:**
- Modify: `indexer/milk_parser.py`
- Test: `tests/test_milk_parser.py`

Densidade é o terceiro eixo do pad de emoção da Fase 2. Vem de quantas formas e ondas customizadas estão ligadas e se o preset traz shaders HLSL próprios.

- [ ] **Step 1: Escrever o teste que falha**

```python
# acrescentar em tests/test_milk_parser.py
from indexer.milk_parser import count_enabled, has_shader


def test_count_enabled_conta_so_os_ligados():
    raw = {
        "shapecode_0_enabled": "1",
        "shapecode_1_enabled": "0",
        "shapecode_2_enabled": "1",
        "shapecode_2_sides": "4",
    }
    assert count_enabled(raw, "shapecode") == 2


def test_count_enabled_zero_quando_nenhum():
    assert count_enabled({"fDecay": "0.5"}, "shapecode") == 0


def test_count_enabled_nao_confunde_prefixos():
    raw = {"wavecode_0_enabled": "1", "shapecode_0_enabled": "1"}
    assert count_enabled(raw, "wavecode") == 1


def test_has_shader_detecta_primeira_linha():
    assert has_shader({"warp_1": "`shader_body"}, "warp") is True
    assert has_shader({"comp_1": "`shader_body"}, "warp") is False
    assert has_shader({}, "comp") is False
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'count_enabled'`

- [ ] **Step 3: Implementar**

```python
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
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add indexer/milk_parser.py tests/test_milk_parser.py
git commit -m "feat(indexer): contagem de formas, ondas e shaders para o eixo densidade"
```

---

### Task 4: Parser — taxonomia derivada do caminho

**Files:**
- Modify: `indexer/milk_parser.py`
- Test: `tests/test_milk_parser.py`

O pacote *cream-of-the-crop* já vem organizado em `<pack>/<Familia>/<Subfamilia>/arquivo.milk`.
Alguns presets ficam direto na família, sem subfamília.

- [ ] **Step 1: Escrever o teste que falha**

```python
# acrescentar em tests/test_milk_parser.py
from pathlib import Path

from indexer.milk_parser import derive_taxonomy


def test_taxonomia_com_subfamilia():
    root = Path("C:/x/presets")
    p = root / "presets-cream-of-the-crop" / "Hypnotic" / "Polar Warp" / "foo.milk"
    assert derive_taxonomy(p, root) == ("Hypnotic", "Polar Warp", False)


def test_taxonomia_sem_subfamilia():
    root = Path("C:/x/presets")
    p = root / "presets-cream-of-the-crop" / "! Transition" / "bar.milk"
    assert derive_taxonomy(p, root) == ("! Transition", "", False)


def test_taxonomia_marca_espelhado():
    root = Path("C:/x/presets")
    p = root / "presets-cream-of-the-crop" / "Dancer" / "Whirl Mirror" / "baz.milk"
    assert derive_taxonomy(p, root) == ("Dancer", "Whirl Mirror", True)


def test_taxonomia_fora_da_raiz_vira_desconhecido():
    assert derive_taxonomy(Path("C:/outro/foo.milk"), Path("C:/x/presets")) == ("", "", False)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'derive_taxonomy'`

- [ ] **Step 3: Implementar**

```python
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
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add indexer/milk_parser.py tests/test_milk_parser.py
git commit -m "feat(indexer): taxonomia familia/subfamilia derivada do caminho"
```

---

### Task 5: Parser — montagem do registro completo

**Files:**
- Modify: `indexer/milk_parser.py`
- Test: `tests/test_milk_parser.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# acrescentar em tests/test_milk_parser.py
from indexer.milk_parser import PresetFeatures, parse_preset_file


MINIMO = """MILKDROP_PRESET_VERSION=201
PSVERSION=2
[preset00]
fDecay=0.980
fGammaAdj=1.900
fVideoEchoAlpha=0.250
fVideoEchoZoom=1.169
fWarpAnimSpeed=1.500
fZoomExponent=1.00000
zoom=1.01191
rot=0.02000
warp=0.26300
sx=1.00000
sy=1.00000
bInvert=1
bBrighten=0
bDarken=0
bSolarize=0
bDarkenCenter=1
wave_r=0.300
wave_g=0.250
wave_b=0.600
fWaveAlpha=0.001
shapecode_0_enabled=1
shapecode_1_enabled=0
wavecode_0_enabled=1
wavecode_1_enabled=1
warp_1=`shader_body
comp_1=`shader_body
"""


def test_parse_preset_file_monta_registro(tmp_path):
    root = tmp_path / "presets"
    d = root / "pack" / "Hypnotic" / "Polar Warp"
    d.mkdir(parents=True)
    f = d / "exemplo.milk"
    f.write_text(MINIMO, encoding="utf-8")

    feat = parse_preset_file(f, root)

    assert isinstance(feat, PresetFeatures)
    assert feat.name == "exemplo"
    assert feat.family == "Hypnotic"
    assert feat.subfamily == "Polar Warp"
    assert feat.is_mirror is False
    assert feat.decay == 0.980
    assert feat.gamma == 1.900
    assert feat.warp_anim_speed == 1.500
    assert feat.invert is True
    assert feat.darken_center is True
    assert feat.brighten is False
    assert feat.n_shapes == 1
    assert feat.n_waves == 2
    assert feat.has_warp_shader is True
    assert feat.has_comp_shader is True
    assert feat.psversion == 2


def test_parse_preset_file_tolera_campos_ausentes(tmp_path):
    root = tmp_path / "presets"
    d = root / "pack" / "Geometric" / "Cube"
    d.mkdir(parents=True)
    f = d / "pelado.milk"
    f.write_text("MILKDROP_PRESET_VERSION=201\n[preset00]\n", encoding="utf-8")

    feat = parse_preset_file(f, root)

    assert feat.decay == 0.96
    assert feat.zoom == 1.0
    assert feat.n_shapes == 0
    assert feat.has_warp_shader is False


def test_parse_preset_file_aceita_bytes_invalidos(tmp_path):
    """Varios presets do corpus tem bytes que nao sao UTF-8 validos."""
    root = tmp_path / "presets"
    d = root / "pack" / "Drawing" / "Liquid"
    d.mkdir(parents=True)
    f = d / "sujo.milk"
    f.write_bytes(b"[preset00]\nfDecay=0.5\n// coment\xe1rio latin1\n")

    feat = parse_preset_file(f, root)

    assert feat.decay == 0.5
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'PresetFeatures'`

- [ ] **Step 3: Implementar**

```python
# acrescentar em indexer/milk_parser.py
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


def parse_preset_file(path: Path, preset_root: Path) -> PresetFeatures:
    """Le um .milk do disco e devolve seu vetor de features.

    Os padroes sao as medianas do corpus, para que um campo ausente nao
    desloque o preset no espaco de features.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
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
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_milk_parser.py -v`
Expected: 20 passed

- [ ] **Step 5: Validar contra o corpus real**

Run:
```bash
python -c "
import config
from pathlib import Path
from indexer.milk_parser import parse_preset_file
ps = list(config.PRESET_ROOT.rglob('*.milk'))
print('encontrados:', len(ps))
ok = err = 0
for p in ps:
    try:
        parse_preset_file(p, config.PRESET_ROOT); ok += 1
    except Exception as e:
        err += 1
        if err <= 3: print('ERRO', p.name, type(e).__name__, e)
print('ok:', ok, 'erros:', err)
"
```
Expected: `encontrados: 9795` e `erros: 0`

- [ ] **Step 6: Commit**

```bash
git add indexer/milk_parser.py tests/test_milk_parser.py
git commit -m "feat(indexer): montagem do registro completo de features do preset"
```

---

### Task 6: Sinal de referência sintético

**Files:**
- Create: `indexer/reference.py`
- Test: `tests/test_reference.py`

O mesmo estímulo para todos os previews é o que torna o grid comparável.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_reference.py
import numpy as np

from indexer.reference import signal_hash, synthetic_signal


def test_formato_do_sinal():
    sig = synthetic_signal(seconds=1.0)
    assert sig.dtype == np.float32
    assert sig.shape == (44100, 2)


def test_amplitude_dentro_da_faixa():
    sig = synthetic_signal(seconds=1.0)
    assert np.abs(sig).max() <= 1.0


def test_e_deterministico():
    a = synthetic_signal(seconds=1.0)
    b = synthetic_signal(seconds=1.0)
    assert np.array_equal(a, b)
    assert signal_hash(a) == signal_hash(b)


def test_bpm_diferente_muda_o_hash():
    a = synthetic_signal(seconds=1.0, bpm=120.0)
    b = synthetic_signal(seconds=1.0, bpm=140.0)
    assert signal_hash(a) != signal_hash(b)


def test_hash_e_curto_e_estavel():
    h = signal_hash(synthetic_signal(seconds=0.5))
    assert len(h) == 12
    assert h == signal_hash(synthetic_signal(seconds=0.5))
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_reference.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'indexer.reference'`

- [ ] **Step 3: Implementar**

```python
# indexer/reference.py
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
    """Gera o sinal sintetico determinístico de referencia.

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
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_reference.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add indexer/reference.py tests/test_reference.py
git commit -m "feat(indexer): sinal de referencia sintetico deterministico"
```

---

### Task 7: Sinal de referência a partir de arquivo de áudio

**Files:**
- Modify: `indexer/reference.py`
- Test: `tests/test_reference.py`

`miniaudio` decodifica FLAC, MP3, VORBIS e WAV. **Não decodifica M4A/AAC** — o erro
precisa ser claro em vez de estourar um `DecodeError` cru.

- [ ] **Step 1: Escrever o teste que falha**

```python
# acrescentar em tests/test_reference.py
import math
import struct
import wave

import pytest

from indexer.reference import UnsupportedAudio, load_signal_file


def _escrever_wav(path, sample_rate=48000, seconds=0.5, channels=1):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = []
        for i in range(int(sample_rate * seconds)):
            v = int(20000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames.append(struct.pack("<h", v) * channels)
        w.writeframes(b"".join(frames))


def test_converte_taxa_e_canais(tmp_path):
    src = tmp_path / "probe.wav"
    _escrever_wav(src, sample_rate=48000, seconds=0.5, channels=1)

    sig = load_signal_file(src)

    assert sig.dtype.name == "float32"
    assert sig.ndim == 2 and sig.shape[1] == 2
    assert abs(sig.shape[0] - int(44100 * 0.5)) < 100


def test_normaliza_o_pico(tmp_path):
    src = tmp_path / "probe.wav"
    _escrever_wav(src, seconds=0.3)

    sig = load_signal_file(src, peak=0.9)

    assert 0.88 < abs(sig).max() <= 0.901


def test_formato_nao_suportado_da_erro_claro(tmp_path):
    src = tmp_path / "musica.m4a"
    src.write_bytes(b"\x00\x00\x00\x20ftypM4A ")

    with pytest.raises(UnsupportedAudio) as exc:
        load_signal_file(src)

    assert "M4A" in str(exc.value) or "m4a" in str(exc.value)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_reference.py -v`
Expected: FAIL — `ImportError: cannot import name 'UnsupportedAudio'`

- [ ] **Step 3: Implementar**

```python
# acrescentar em indexer/reference.py
from pathlib import Path

import miniaudio

SUPPORTED_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg"}


class UnsupportedAudio(Exception):
    """Formato que o miniaudio nao decodifica."""


def load_signal_file(path: Path, peak: float = 0.9) -> np.ndarray:
    """Decodifica um arquivo de audio para o formato de referencia.

    Devolve float32 (n, 2) a 44100 Hz, normalizado para o pico informado.
    Levanta UnsupportedAudio para formatos que o miniaudio nao le - notavelmente
    M4A/AAC, que e comum e falha com uma mensagem inutil se deixado passar.
    """
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise UnsupportedAudio(
            f"{path.suffix} nao e suportado (M4A/AAC inclusive). "
            f"Formatos aceitos: {', '.join(sorted(SUPPORTED_SUFFIXES))}. "
            f"Alternativa: use indexer/capture_reference.py para gravar do loopback."
        )
    try:
        decoded = miniaudio.decode_file(
            str(path),
            output_format=miniaudio.SampleFormat.FLOAT32,
            nchannels=2,
            sample_rate=config.SAMPLE_RATE,
        )
    except miniaudio.DecodeError as exc:
        raise UnsupportedAudio(f"miniaudio nao decodificou {path.name}: {exc}") from exc

    samples = np.asarray(decoded.samples, dtype=np.float32).reshape(-1, 2)
    largest = float(np.abs(samples).max())
    if largest > 1e-6:
        samples = samples / largest * peak
    return np.ascontiguousarray(samples, dtype=np.float32)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_reference.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add indexer/reference.py tests/test_reference.py
git commit -m "feat(indexer): sinal de referencia a partir de arquivo com erro claro para M4A"
```

---

### Task 8: Esquema e acesso ao banco

**Files:**
- Create: `indexer/db.py`
- Test: `tests/test_db.py`

SQLite, não JSON: a Fase 2 consulta por faixa de valores sobre as features.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_db.py
from pathlib import Path

from indexer.db import connect, count_presets, init_schema, iter_presets, upsert_preset
from indexer.milk_parser import PresetFeatures


def _features(name="a", family="Hypnotic", subfamily="Polar Warp", decay=0.9, n_shapes=1):
    return PresetFeatures(
        path=f"C:/x/{family}/{subfamily}/{name}.milk", name=name, family=family,
        subfamily=subfamily, is_mirror=False, warp_anim_speed=1.0, zoom=1.0, rot=0.0,
        warp=0.2, zoom_exponent=1.0, sx=1.0, sy=1.0, decay=decay, echo_alpha=0.0,
        echo_zoom=1.0, gamma=1.2, brighten=False, darken=False, invert=False,
        solarize=False, darken_center=False, wave_r=0.3, wave_g=0.2, wave_b=0.6,
        wave_alpha=0.01, n_shapes=n_shapes, n_waves=0, has_warp_shader=True,
        has_comp_shader=True, psversion=2,
    )


def test_insere_e_recupera(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    upsert_preset(con, _features())
    con.commit()

    linhas = list(iter_presets(con))
    assert len(linhas) == 1
    assert linhas[0]["name"] == "a"
    assert linhas[0]["family"] == "Hypnotic"
    assert linhas[0]["has_warp_shader"] == 1


def test_upsert_e_idempotente(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    upsert_preset(con, _features(decay=0.9))
    upsert_preset(con, _features(decay=0.5))
    con.commit()

    assert count_presets(con) == 1
    assert list(iter_presets(con))[0]["decay"] == 0.5


def test_filtra_por_familia(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    upsert_preset(con, _features(name="a", family="Hypnotic"))
    upsert_preset(con, _features(name="b", family="Geometric"))
    con.commit()

    nomes = [r["name"] for r in iter_presets(con, family="Geometric")]
    assert nomes == ["b"]


def test_consulta_por_faixa_de_features(tmp_path):
    """A Fase 2 depende disso: e o motivo de ser SQLite e nao JSON."""
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    upsert_preset(con, _features(name="lento", decay=0.99, n_shapes=0))
    upsert_preset(con, _features(name="denso", decay=0.50, n_shapes=4))
    con.commit()

    cur = con.execute("SELECT name FROM presets WHERE decay < 0.8 AND n_shapes > 2")
    assert [r[0] for r in cur] == ["denso"]


def test_init_schema_e_reentrante(tmp_path):
    con = connect(tmp_path / "t.sqlite")
    init_schema(con)
    init_schema(con)
    assert count_presets(con) == 0
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'indexer.db'`

- [ ] **Step 3: Implementar**

```python
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
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_db.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add indexer/db.py tests/test_db.py
git commit -m "feat(indexer): esquema SQLite e acesso ao indice de presets"
```

---

### Task 9: CLI de construção do índice

**Files:**
- Create: `indexer/build_index.py`

- [ ] **Step 1: Escrever o CLI**

```python
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
```

- [ ] **Step 2: Rodar contra o corpus real**

Run: `python -m indexer.build_index`
Expected: termina com `indice: 9795 presets em ...` e `falhas: 0`

- [ ] **Step 3: Conferir a distribuição por família**

Run:
```bash
python -c "
import config, sqlite3
con = sqlite3.connect(str(config.DB_PATH))
for fam, n in con.execute('SELECT family, COUNT(*) c FROM presets GROUP BY family ORDER BY c DESC'):
    print(f'{n:6d}  {fam}')
"
```
Expected: bate com a contagem da spec — Reaction 1791, Fractal 1354, Dancer 1351, Waveform 1279, Drawing 1143, Geometric 1027, Sparkle 797, Particles 389, Supernova 380, Hypnotic 280

- [ ] **Step 4: Commit**

```bash
git add indexer/build_index.py
git commit -m "feat(indexer): CLI que constroi o indice a partir da arvore de presets"
```

---

### Task 10: Binding ctypes da libprojectM

**Files:**
- Create: `engine/pm_ffi.py`
- Test: `tests/test_pm_ffi.py`

Binding mecânico, sem lógica. Compartilhado com a Fase 1b.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_pm_ffi.py
"""Testa so o que nao exige contexto OpenGL.

Criar uma instancia de projectM exige contexto GL corrente - isso e coberto
pelos smoke tests de engine/gl_context.py, nao aqui.
"""
from engine.pm_ffi import PROJECTM_STEREO, load_library


def test_carrega_biblioteca_e_le_versao():
    lib = load_library()
    versao = lib.projectm_get_version_string().decode()
    assert versao.startswith("4.")


def test_constante_de_canais():
    assert PROJECTM_STEREO == 2
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_pm_ffi.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.pm_ffi'`

- [ ] **Step 3: Implementar**

```python
# engine/pm_ffi.py
"""Binding ctypes para projectM-4.dll. Mecanico: nenhuma logica aqui.

Duas armadilhas ja resolvidas e verificadas contra a 4.1.4:

1. glewInit() TEM que rodar antes de projectm_create(), senao da access
   violation escrevendo em 0x0 (ponteiros de funcao GL nulos). Isso e
   responsabilidade de engine/gl_context.py.
2. projectm_write_debug_image_on_next_frame() e no-op na 4.1.4
   (ProjectMCWrapper.cpp:374 = "// UNIMPLEMENTED"). Nao usar; a captura de
   frame e feita com glReadPixels em engine/capture.py.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

import numpy as np

import config

PROJECTM_MONO = 1
PROJECTM_STEREO = 2

_lib: ctypes.CDLL | None = None


def load_library() -> ctypes.CDLL:
    """Carrega projectM-4.dll com as assinaturas declaradas. Idempotente.

    add_dll_directory e obrigatorio: o Python da Microsoft Store nao procura
    DLLs dependentes (glew32, SDL2...) no diretorio do modulo carregado.
    """
    global _lib
    if _lib is not None:
        return _lib

    os.add_dll_directory(str(config.APP_DIR))
    lib = ctypes.CDLL(str(config.DLL_PATH))

    lib.projectm_create.restype = ctypes.c_void_p
    lib.projectm_create.argtypes = []
    lib.projectm_destroy.argtypes = [ctypes.c_void_p]
    lib.projectm_get_version_string.restype = ctypes.c_char_p
    lib.projectm_set_window_size.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                             ctypes.c_size_t]
    lib.projectm_set_mesh_size.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.c_size_t]
    lib.projectm_set_beat_sensitivity.argtypes = [ctypes.c_void_p, ctypes.c_float]
    lib.projectm_load_preset_file.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                              ctypes.c_bool]
    lib.projectm_load_preset_data.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                              ctypes.c_bool]
    lib.projectm_opengl_render_frame.argtypes = [ctypes.c_void_p]
    lib.projectm_pcm_add_float.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_float),
                                           ctypes.c_uint, ctypes.c_int]
    lib.projectm_set_texture_search_paths.argtypes = [ctypes.c_void_p,
                                                      ctypes.POINTER(ctypes.c_char_p),
                                                      ctypes.c_size_t]
    _lib = lib
    return lib


class ProjectM:
    """Uma instancia de projectM. Exige contexto OpenGL corrente na thread."""

    def __init__(self, width: int, height: int,
                 texture_dir: Path | None = None) -> None:
        self._lib = load_library()
        handle = self._lib.projectm_create()
        if not handle:
            raise RuntimeError(
                "projectm_create() devolveu NULL. Contexto OpenGL corrente e "
                "glewInit() executado?")
        self._handle = ctypes.c_void_p(handle)
        self._lib.projectm_set_window_size(self._handle, width, height)
        directory = texture_dir or config.TEXTURE_DIR
        paths = (ctypes.c_char_p * 1)(str(directory).encode("utf-8"))
        self._lib.projectm_set_texture_search_paths(self._handle, paths, 1)

    def load_preset_file(self, path: Path, smooth: bool = False) -> None:
        """Carrega um preset do disco. smooth=False faz corte seco."""
        self._lib.projectm_load_preset_file(
            self._handle, str(path).encode("utf-8"), smooth)

    def load_preset_data(self, text: str, smooth: bool = False) -> None:
        """Carrega um preset a partir de texto em memoria."""
        self._lib.projectm_load_preset_data(
            self._handle, text.encode("utf-8"), smooth)

    def add_pcm(self, samples: np.ndarray) -> None:
        """Alimenta audio. samples e float32 no formato (n, 2), intercalado."""
        flat = np.ascontiguousarray(samples, dtype=np.float32).reshape(-1)
        buf = flat.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        self._lib.projectm_pcm_add_float(
            self._handle, buf, len(flat) // 2, PROJECTM_STEREO)

    def render_frame(self) -> None:
        """Desenha um quadro no framebuffer atualmente ligado."""
        self._lib.projectm_opengl_render_frame(self._handle)

    def set_mesh_size(self, width: int, height: int) -> None:
        """Resolucao da malha de deformacao. Valvula de performance e estetica."""
        self._lib.projectm_set_mesh_size(self._handle, width, height)

    def set_beat_sensitivity(self, value: float) -> None:
        """Reatividade a batida."""
        self._lib.projectm_set_beat_sensitivity(self._handle, value)

    def close(self) -> None:
        """Libera a instancia. Seguro chamar duas vezes."""
        if self._handle is not None:
            self._lib.projectm_destroy(self._handle)
            self._handle = None

    def __enter__(self) -> "ProjectM":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_pm_ffi.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add engine/pm_ffi.py tests/test_pm_ffi.py
git commit -m "feat(engine): binding ctypes da libprojectM com as assinaturas declaradas"
```

---

### Task 11: Contexto OpenGL com glewInit

**Files:**
- Create: `engine/gl_context.py`
- Test: `tests/test_gl_context.py`

Este é o módulo que resolve a armadilha nº1 do projeto.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_gl_context.py
from engine.gl_context import GLContext
from engine.pm_ffi import ProjectM


def test_contexto_headless_permite_criar_projectm():
    """Regressao da armadilha nº1: sem glewInit() isso da access violation."""
    with GLContext(320, 180, visible=False) as ctx:
        assert ctx.width == 320
        with ProjectM(320, 180) as pm:
            pm.render_frame()
            ctx.swap()


def test_contexto_pode_ser_reaberto():
    """glfw.init/terminate repetidos nao podem quebrar."""
    for _ in range(2):
        with GLContext(160, 90, visible=False):
            pass
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_gl_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.gl_context'`

- [ ] **Step 3: Implementar**

```python
# engine/gl_context.py
"""Contexto OpenGL via glfw, com o glewInit() que a libprojectM exige.

ARMADILHA CENTRAL DO PROJETO: projectm_create() chama funcoes OpenGL cujos
ponteiros vivem dentro do glew32.dll. Enquanto glewInit() nao rodar, esses
ponteiros sao NULL e a chamada morre com "access violation writing 0x0".
O frontend oficial faz a mesma coisa em SDLRenderingWindow.cpp:276.

O contexto tem afinidade de thread: quem cria tem que ser quem renderiza.
"""
from __future__ import annotations

import ctypes

import glfw

import config


def _init_glew() -> None:
    """Inicializa o GLEW no contexto corrente.

    glewExperimental=1 e necessario em perfil core, senao parte das extensoes
    fica sem ponteiro.
    """
    glew = ctypes.CDLL(str(config.GLEW_PATH))
    try:
        ctypes.c_ubyte.in_dll(glew, "glewExperimental").value = 1
    except ValueError:
        pass  # build de GLEW sem o simbolo exportado
    glew.glewInit.restype = ctypes.c_uint
    error = glew.glewInit()
    if error != 0:
        raise RuntimeError(f"glewInit() falhou com codigo {error}")


class GLContext:
    """Janela glfw + contexto OpenGL 3.3 core + GLEW inicializado."""

    def __init__(self, width: int, height: int, visible: bool = True,
                 title: str = "Sala", vsync: bool = True) -> None:
        self.width = width
        self.height = height
        if not glfw.init():
            raise RuntimeError("glfw.init() falhou")
        glfw.window_hint(glfw.VISIBLE, glfw.TRUE if visible else glfw.FALSE)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        self._window = glfw.create_window(width, height, title, None, None)
        if not self._window:
            glfw.terminate()
            raise RuntimeError("glfw.create_window() falhou")
        glfw.make_context_current(self._window)
        glfw.swap_interval(1 if vsync else 0)
        _init_glew()

    def swap(self) -> None:
        """Troca os buffers e processa eventos da janela."""
        glfw.swap_buffers(self._window)
        glfw.poll_events()

    def should_close(self) -> bool:
        """Diz se o usuario pediu para fechar a janela."""
        return bool(glfw.window_should_close(self._window))

    def close(self) -> None:
        """Destroi a janela e encerra o glfw. Seguro chamar duas vezes."""
        if self._window is not None:
            glfw.destroy_window(self._window)
            self._window = None
            glfw.terminate()

    def __enter__(self) -> "GLContext":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_gl_context.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add engine/gl_context.py tests/test_gl_context.py
git commit -m "feat(engine): contexto OpenGL com glewInit, a armadilha nº1 resolvida"
```

---

### Task 12: Captura de frame

**Files:**
- Create: `engine/capture.py`
- Test: `tests/test_capture.py`

`projectm_write_debug_image_on_next_frame()` é no-op na 4.1.4. A captura é nossa.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_capture.py
import numpy as np
from OpenGL.GL import GL_COLOR_BUFFER_BIT, glClear, glClearColor

from engine.capture import read_frame
from engine.gl_context import GLContext


def test_le_o_framebuffer_no_formato_certo():
    with GLContext(64, 32, visible=False) as ctx:
        glClearColor(1.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        frame = read_frame(ctx.width, ctx.height)

    assert frame.shape == (32, 64, 3)
    assert frame.dtype == np.uint8


def test_desvira_a_imagem():
    """OpenGL entrega bottom-up; a imagem tem que sair top-down.

    Pinta so a metade INFERIOR do viewport em GL; depois de desvirar, essa
    faixa tem que aparecer nas ULTIMAS linhas do array.
    """
    from OpenGL.GL import GL_SCISSOR_TEST, glDisable, glEnable, glScissor

    with GLContext(16, 16, visible=False) as ctx:
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        glEnable(GL_SCISSOR_TEST)
        glScissor(0, 0, 16, 8)          # metade de baixo em GL
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        glDisable(GL_SCISSOR_TEST)
        frame = read_frame(ctx.width, ctx.height)

    assert frame[0].mean() < 10        # topo escuro
    assert frame[-1].mean() > 245      # base clara
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_capture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.capture'`

- [ ] **Step 3: Implementar**

```python
# engine/capture.py
"""Captura do framebuffer corrente para numpy.

projectm_write_debug_image_on_next_frame() existe no header e e exportada
pela DLL, mas na 4.1.4 o corpo e literalmente "// UNIMPLEMENTED"
(ProjectMCWrapper.cpp:374). Entao a captura e feita aqui.
"""
from __future__ import annotations

import numpy as np
from OpenGL.GL import (GL_PACK_ALIGNMENT, GL_RGB, GL_UNSIGNED_BYTE, glPixelStorei,
                       glReadPixels)


def read_frame(width: int, height: int) -> np.ndarray:
    """Le o framebuffer corrente como RGB uint8 no formato (altura, largura, 3).

    A origem do OpenGL fica embaixo a esquerda; a imagem devolvida ja vem
    desvirada, pronta para o Pillow.
    """
    glPixelStorei(GL_PACK_ALIGNMENT, 1)
    raw = glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE)
    flipped = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)[::-1]
    return np.ascontiguousarray(flipped)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_capture.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add engine/capture.py tests/test_capture.py
git commit -m "feat(engine): captura de frame com glReadPixels, ja desvirada"
```

---

### Task 13: Renderizador de posters

**Files:**
- Create: `indexer/render_posters.py`

Camada 1 da estratégia de previews: um poster estático para cada um dos 9.795,
~15 KB cada. O animado fica sob demanda, na Fase 1b.

- [ ] **Step 1: Escrever o CLI**

```python
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
```

- [ ] **Step 2: Rodar numa amostra pequena**

Run: `python -m indexer.render_posters --family Hypnotic --limit 10`
Expected: `posters: 10 novos, 0 pulados, 0 falhas` e cerca de 1,3 s por preset

- [ ] **Step 3: Conferir que o cache é idempotente**

Run: `python -m indexer.render_posters --family Hypnotic --limit 10`
Expected: `posters: 0 novos, 10 pulados, 0 falhas`

- [ ] **Step 4: Abrir os posters e conferir visualmente**

Run: `explorer.exe "$(cygpath -w "$(python -c "import config;print(config.PREVIEW_DIR)")")"`
Expected: pasta com um subdiretório de hash contendo 10 arquivos `.webp` legíveis — imagens com conteúdo, não retângulos pretos

- [ ] **Step 5: Conferir que contraste e movimento foram gravados**

Run:
```bash
python -c "
import config, sqlite3
con = sqlite3.connect(str(config.DB_PATH))
for n, c, m in con.execute('SELECT name, contrast, motion FROM presets WHERE poster_sig IS NOT NULL LIMIT 10'):
    print(f'{c:7.1f} {m:7.2f}  {n[:50]}')
"
```
Expected: dez linhas com contraste e movimento não nulos

- [ ] **Step 6: Commit**

```bash
git add indexer/render_posters.py
git commit -m "feat(indexer): renderizador de posters com warmup do AGC e metricas de vivacidade"
```

---

### Task 14: Captura de referência do loopback

**Files:**
- Create: `indexer/capture_reference.py`

Resolve o caso M4A/AAC sem decoder: grava direto do que está tocando.

- [ ] **Step 1: Escrever o CLI**

```python
# indexer/capture_reference.py
"""CLI: grava N segundos do loopback WASAPI como WAV de referencia.

Serve para usar musica real como sinal de referencia sem depender de decoder.
Funciona com qualquer fonte, inclusive streaming - e contorna o fato de que o
miniaudio nao le M4A/AAC.

Uso:
    python -m indexer.capture_reference --seconds 10 --out data/reference/minha.wav
"""
from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio

import config


def find_loopback(pa: pyaudio.PyAudio) -> dict:
    """Acha o dispositivo de loopback que corresponde a saida padrao."""
    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    speakers = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
    for device in pa.get_loopback_device_info_generator():
        if speakers["name"] in device["name"]:
            return device
    raise RuntimeError(f"nenhum loopback casou com a saida padrao ({speakers['name']})")


def record(seconds: float) -> tuple[np.ndarray, int]:
    """Grava do loopback. Devolve (amostras float32 (n, canais), taxa)."""
    pa = pyaudio.PyAudio()
    try:
        device = find_loopback(pa)
        rate = int(device["defaultSampleRate"])
        channels = int(device["maxInputChannels"])
        print(f"gravando de: {device['name']}  ({rate} Hz, {channels} ch)")
        stream = pa.open(format=pyaudio.paFloat32, channels=channels, rate=rate,
                         input=True, input_device_index=device["index"],
                         frames_per_buffer=1024)
        chunks = []
        started = time.time()
        while time.time() - started < seconds:
            chunks.append(stream.read(1024, exception_on_overflow=False))
        stream.close()
    finally:
        pa.terminate()
    samples = np.frombuffer(b"".join(chunks), dtype=np.float32).reshape(-1, channels)
    return samples, rate


def main() -> int:
    ap = argparse.ArgumentParser(description="Grava referencia do loopback WASAPI.")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--out", type=Path,
                    default=config.REFERENCE_DIR / "captura.wav")
    args = ap.parse_args()

    samples, rate = record(args.seconds)
    peak = float(np.abs(samples).max())
    print(f"capturado: {len(samples) / rate:.1f}s  pico={peak:.4f}")
    if peak < 1e-4:
        print("SILENCIO - toque alguma coisa e grave de novo.", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    pcm16 = (np.clip(samples / peak * 0.9, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(args.out), "wb") as w:
        w.setnchannels(samples.shape[1])
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm16.tobytes())
    print(f"gravado em {args.out} ({args.out.stat().st_size / 1024:.0f} KB)")
    print(f"usar com: python -m indexer.render_posters --reference \"{args.out}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Testar com música tocando**

Toque alguma coisa e rode: `python -m indexer.capture_reference --seconds 10`
Expected: `capturado: 10.0s pico=<maior que 0.01>` e o caminho do WAV gravado

- [ ] **Step 3: Verificar que o WAV alimenta o renderizador**

Run: `python -m indexer.render_posters --family Hypnotic --limit 3 --reference data/reference/captura.wav`
Expected: novo diretório de hash em `data/previews/` — diferente do hash do sintético, provando o versionamento do cache

- [ ] **Step 4: Commit**

```bash
git add indexer/capture_reference.py
git commit -m "feat(indexer): captura de referencia do loopback, contorna a falta de decoder AAC"
```

---

### Task 15: Suíte completa e lote do corpus

**Files:**
- Nenhum arquivo novo

- [ ] **Step 1: Rodar a suíte inteira**

Run: `python -m pytest tests/ -v`
Expected: todos passam, nenhum erro

- [ ] **Step 2: Reconstruir o índice do zero**

Run:
```bash
python -c "import config, os; p=config.DB_PATH; os.remove(p) if p.exists() else None"
python -m indexer.build_index
```
Expected: `indice: 9795 presets` e `falhas: 0`

- [ ] **Step 3: Gerar posters das três famílias pequenas**

Run:
```bash
python -m indexer.render_posters --family Hypnotic
python -m indexer.render_posters --family Supernova
python -m indexer.render_posters --family Particles
```
Expected: 1.049 posters no total, sem falhas — cerca de 25 minutos

- [ ] **Step 4: Conferir o tamanho em disco**

Run:
```bash
python -c "
import config
d = config.PREVIEW_DIR
arquivos = list(d.rglob('*.webp'))
total = sum(f.stat().st_size for f in arquivos)
print(f'{len(arquivos)} posters, {total/1024/1024:.1f} MB, media {total/len(arquivos)/1024:.1f} KB')
"
```
Expected: média em torno de 15 KB por poster — extrapolando, ~150 MB para o corpus inteiro, batendo com a spec

- [ ] **Step 5: Rodar o lote completo em segundo plano**

Run: `python -m indexer.render_posters`
Expected: roda por volta de 3,5 h e termina com `falhas: 0`. Deixar de madrugada.

- [ ] **Step 6: Commit final da fase**

```bash
git add -A
git commit -m "chore: Fase 1a concluida - indice com 9795 presets e posters gerados"
```

---

## Feito quando

- `python -m pytest tests/ -v` passa inteiro
- `data/index.sqlite` tem 9.795 linhas com features e taxonomia
- `data/previews/<hash>/` tem um poster por preset, ~150 MB
- Trocar o sinal de referência cria um diretório de hash novo sem invalidar o antigo
- `contrast` e `motion` preenchidos para todo preset com poster

## Próximo plano (Fase 1b)

Motor ao vivo (janela + captura de áudio + fila de comandos em três threads), servidor
FastAPI/WebSocket e UI React responsiva. Consome `data/index.sqlite` e
`data/previews/`, e reaproveita `engine/pm_ffi.py`, `engine/gl_context.py` e
`engine/capture.py` sem alteração.
