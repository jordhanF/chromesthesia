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
