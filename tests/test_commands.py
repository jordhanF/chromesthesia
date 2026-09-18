# tests/test_commands.py
from engine.commands import CommandQueue, LoadPreset, SetBeatSensitivity, Shutdown


def test_comandos_saem_na_ordem_em_que_entraram():
    q = CommandQueue()
    q.send(LoadPreset("a.milk"))
    q.send(SetBeatSensitivity(1.5))
    assert q.drain() == [LoadPreset("a.milk"), SetBeatSensitivity(1.5)]


def test_drain_esvazia_a_fila():
    q = CommandQueue()
    q.send(Shutdown())
    q.drain()
    assert q.drain() == []


def test_drain_em_fila_vazia_devolve_lista_vazia():
    assert CommandQueue().drain() == []


def test_send_nao_bloqueia_quando_cheia():
    """O servidor nao pode travar se o loop de render parar de drenar."""
    q = CommandQueue(maxsize=2)
    assert q.send(Shutdown()) is True
    assert q.send(Shutdown()) is True
    assert q.send(Shutdown()) is False


def test_load_preset_tem_transicao_suave_por_padrao():
    assert LoadPreset("a.milk").smooth is True
