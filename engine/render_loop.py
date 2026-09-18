# engine/render_loop.py
"""Loop de render. Roda na thread principal, dona do contexto OpenGL.

Uma volta do loop: drena comandos, empurra audio recente para a libprojectM,
desenha um quadro, publica o estado. Nenhuma outra thread chama a lib.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

import config
from engine.audio import AudioBuffer, LoopbackCapture
from engine.commands import (CommandQueue, EngineState, LoadPreset, SetBeatSensitivity,
                             SetMeshSize, Shutdown, StatePublisher)
from engine.gl_context import GLContext
from engine.pm_ffi import ProjectM


def run_render_loop(context: GLContext, projectm: ProjectM, audio: AudioBuffer,
                    capture: LoopbackCapture | None, commands: CommandQueue,
                    state: StatePublisher) -> None:
    """Desenha ate receber Shutdown ou a janela ser fechada."""
    frame = 0
    preset_path = ""
    preset_name = ""
    last_report = time.perf_counter()
    frames_since_report = 0
    fps = 0.0

    while not context.should_close():
        for command in commands.drain():
            if isinstance(command, Shutdown):
                return
            if isinstance(command, LoadPreset):
                projectm.load_preset_file(Path(command.path), smooth=command.smooth)
                preset_path = command.path
                preset_name = Path(command.path).stem
            elif isinstance(command, SetBeatSensitivity):
                projectm.set_beat_sensitivity(command.value)
            elif isinstance(command, SetMeshSize):
                projectm.set_mesh_size(command.width, command.height)

        chunk = audio.read_latest(config.PCM_CHUNK)
        projectm.add_pcm(chunk)
        projectm.render_frame()
        context.swap()

        frame += 1
        frames_since_report += 1
        now = time.perf_counter()
        if now - last_report >= 0.5:
            fps = frames_since_report / (now - last_report)
            last_report = now
            frames_since_report = 0
            state.publish(EngineState(
                preset_path=preset_path,
                preset_name=preset_name,
                fps=round(fps, 1),
                audio_peak=float(np.abs(chunk).max()),
                audio_connected=bool(capture.connected) if capture else False,
                frame=frame,
            ))
