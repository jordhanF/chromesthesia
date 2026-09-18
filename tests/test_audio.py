import numpy as np

from engine.audio import AudioBuffer


def _rampa(n, canais=2):
    """Bloco em que cada amostra tem valor igual ao seu indice."""
    return np.tile(np.arange(n, dtype=np.float32).reshape(-1, 1), (1, canais))


def test_le_o_que_escreveu():
    b = AudioBuffer(capacity=100)
    b.write(_rampa(10))
    assert np.array_equal(b.read_latest(10), _rampa(10))


def test_devolve_as_mais_recentes_em_ordem_cronologica():
    b = AudioBuffer(capacity=100)
    b.write(_rampa(50))
    ultimas = b.read_latest(5)
    assert np.array_equal(ultimas[:, 0], np.array([45, 46, 47, 48, 49], dtype=np.float32))


def test_da_a_volta_sem_embaralhar():
    """O ponto onde o buffer circula nao pode aparecer no meio da leitura."""
    b = AudioBuffer(capacity=10)
    b.write(_rampa(8))
    b.write(_rampa(8) + 100)      # passa do fim e volta ao inicio
    # as 8 mais recentes sao exatamente o segundo bloco, em ordem
    assert b.read_latest(8)[:, 0].tolist() == list(range(100, 108))
    # e as 2 anteriores sao o final do primeiro bloco que ainda sobreviveu
    assert b.read_latest(10)[:2, 0].tolist() == [6.0, 7.0]


def test_bloco_maior_que_a_capacidade_mantem_o_final():
    b = AudioBuffer(capacity=4)
    b.write(_rampa(10))
    assert b.read_latest(4)[:, 0].tolist() == [6.0, 7.0, 8.0, 9.0]


def test_ler_mais_que_a_capacidade_nao_estoura():
    b = AudioBuffer(capacity=8)
    b.write(_rampa(8))
    assert b.read_latest(999).shape == (8, 2)


def test_buffer_novo_devolve_silencio():
    b = AudioBuffer(capacity=16)
    assert float(np.abs(b.read_latest(16)).max()) == 0.0


def test_conta_o_total_escrito():
    b = AudioBuffer(capacity=8)
    b.write(_rampa(5))
    b.write(_rampa(5))
    assert b.total_written == 10
