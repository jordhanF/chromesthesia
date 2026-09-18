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
