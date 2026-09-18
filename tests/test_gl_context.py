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
