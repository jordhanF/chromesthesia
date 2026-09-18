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
