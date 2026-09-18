# indexer/capture_reference.py
"""CLI: grava N segundos do loopback WASAPI como WAV de referencia.

Serve para usar musica real como sinal de referencia sem depender de decoder.
Funciona com qualquer fonte, inclusive streaming - e contorna o fato de que o
miniaudio nao le M4A/AAC (ver indexer/reference.py).

O caminho de audio (WASAPI loopback -> float32 -> numpy) foi provado em
tests/smoke_loopback.py; este CLI empacota o mesmo caminho com opcoes de
linha de comando e a checagem de silencio.

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
