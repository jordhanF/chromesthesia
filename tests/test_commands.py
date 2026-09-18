# tests/test_commands.py
import threading

from engine.commands import (CommandQueue, EngineState, LoadPreset,
                             SetBeatSensitivity, Shutdown, StatePublisher)


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


def test_estado_inicial_e_vazio():
    s = StatePublisher().read()
    assert s.preset_name == ""
    assert s.frame == 0
    assert s.audio_connected is False


def test_publicar_e_ler():
    p = StatePublisher()
    p.publish(EngineState(preset_name="tunel", fps=59.7, frame=120))
    s = p.read()
    assert s.preset_name == "tunel"
    assert s.fps == 59.7
    assert s.frame == 120


def test_leitura_devolve_instantaneo_imutavel():
    """Quem le nao pode enxergar um estado meio escrito."""
    p = StatePublisher()
    p.publish(EngineState(preset_name="a", frame=1))
    antes = p.read()
    p.publish(EngineState(preset_name="b", frame=2))
    assert antes.preset_name == "a"
    assert antes.frame == 1


def test_publicacao_concorrente_nunca_mistura_campos():
    p = StatePublisher()
    parar = threading.Event()

    def escritor(nome, n):
        while not parar.is_set():
            p.publish(EngineState(preset_name=nome, frame=n))

    ts = [threading.Thread(target=escritor, args=(nome, n), daemon=True)
          for nome, n in (("a", 1), ("b", 2))]
    for t in ts:
        t.start()
    for _ in range(2000):
        s = p.read()
        # cada publicacao e atomica: nome e frame sempre vem do mesmo par
        assert (s.preset_name, s.frame) in {("", 0), ("a", 1), ("b", 2)}
    parar.set()
    for t in ts:
        t.join(timeout=2)
