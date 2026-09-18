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
                 title: str = "Chromesthesia", vsync: bool = True) -> None:
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
