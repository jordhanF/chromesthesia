# engine/app.py
"""Ponto de entrada: monta as tres threads e coordena o encerramento.

A thread principal e a dona do contexto OpenGL, e por isso e ela que roda o
loop de render. Audio e servidor sao daemon: quando o loop retorna, o
processo encerra sem precisar orquestrar parada de ninguem.

Uso:
    python -m engine.app
    python -m engine.app --width 1280 --height 720
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import config
from engine.audio import AudioBuffer, LoopbackCapture
from engine.commands import CommandQueue, StatePublisher
from engine.gl_context import GLContext
from engine.pm_ffi import ProjectM
from engine.render_loop import run_render_loop
from server.main import PORT, local_ip, serve_in_thread


def first_preset_path() -> str | None:
    """Um preset qualquer para abrir com algo na tela."""
    if not config.DB_PATH.exists():
        return None
    con = sqlite3.connect(str(config.DB_PATH))
    try:
        row = con.execute("SELECT path FROM presets ORDER BY RANDOM() LIMIT 1").fetchone()
        return row[0] if row else None
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Motor ao vivo do Chromesthesia.")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()

    commands = CommandQueue()
    state = StatePublisher()
    audio = AudioBuffer()

    capture = LoopbackCapture(audio)
    capture.start()
    if not capture.wait_until_running(timeout=3.0):
        print("AVISO: captura de audio nao iniciou. Os visuais vao rodar sem reagir.")
        print("       Confira a saida de audio padrao do Windows.")

    serve_in_thread(commands, state)
    print(f"controle em:  http://{local_ip()}:{PORT}/docs")
    print(f"              http://127.0.0.1:{PORT}/docs")
    print("Se o celular nao abrir, libere a porta no Firewall do Windows:")
    print(f'  netsh advfirewall firewall add rule name="Chromesthesia" '
          f'dir=in action=allow protocol=TCP localport={PORT}')

    with GLContext(args.width, args.height, visible=True,
                   title="Chromesthesia") as context:
        with ProjectM(args.width, args.height) as projectm:
            inicial = first_preset_path()
            if inicial:
                projectm.load_preset_file(Path(inicial), smooth=False)
            try:
                run_render_loop(context, projectm, audio, capture, commands, state)
            except KeyboardInterrupt:
                pass
    capture.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
