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
