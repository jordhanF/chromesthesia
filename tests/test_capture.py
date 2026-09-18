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
