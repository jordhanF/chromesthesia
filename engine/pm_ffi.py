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
