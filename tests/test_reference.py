import numpy as np

from indexer.reference import signal_hash, synthetic_signal


def test_formato_do_sinal():
    sig = synthetic_signal(seconds=1.0)
    assert sig.dtype == np.float32
    assert sig.shape == (44100, 2)


def test_amplitude_dentro_da_faixa():
    sig = synthetic_signal(seconds=1.0)
    assert np.abs(sig).max() <= 1.0


def test_e_deterministico():
    a = synthetic_signal(seconds=1.0)
    b = synthetic_signal(seconds=1.0)
    assert np.array_equal(a, b)
    assert signal_hash(a) == signal_hash(b)


def test_bpm_diferente_muda_o_hash():
    a = synthetic_signal(seconds=1.0, bpm=120.0)
    b = synthetic_signal(seconds=1.0, bpm=140.0)
    assert signal_hash(a) != signal_hash(b)


def test_hash_e_curto_e_estavel():
    h = signal_hash(synthetic_signal(seconds=0.5))
    assert len(h) == 12
    assert h == signal_hash(synthetic_signal(seconds=0.5))


import math
import struct
import wave

import pytest

from indexer.reference import UnsupportedAudio, load_signal_file


def _escrever_wav(path, sample_rate=48000, seconds=0.5, channels=1):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = []
        for i in range(int(sample_rate * seconds)):
            v = int(20000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames.append(struct.pack("<h", v) * channels)
        w.writeframes(b"".join(frames))


def test_converte_taxa_e_canais(tmp_path):
    src = tmp_path / "probe.wav"
    _escrever_wav(src, sample_rate=48000, seconds=0.5, channels=1)

    sig = load_signal_file(src)

    assert sig.dtype.name == "float32"
    assert sig.ndim == 2 and sig.shape[1] == 2
    assert abs(sig.shape[0] - int(44100 * 0.5)) < 100


def test_normaliza_o_pico(tmp_path):
    src = tmp_path / "probe.wav"
    _escrever_wav(src, seconds=0.3)

    sig = load_signal_file(src, peak=0.9)

    assert 0.88 < abs(sig).max() <= 0.901


def test_formato_nao_suportado_da_erro_claro(tmp_path):
    src = tmp_path / "musica.m4a"
    src.write_bytes(b"\x00\x00\x00\x20ftypM4A ")

    with pytest.raises(UnsupportedAudio) as exc:
        load_signal_file(src)

    assert "M4A" in str(exc.value) or "m4a" in str(exc.value)
