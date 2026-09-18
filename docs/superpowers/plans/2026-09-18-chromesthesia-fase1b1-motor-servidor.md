# Chromesthesia — Fase 1b-1: motor ao vivo + servidor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um processo que abre a janela do visualizador, reage ao áudio que está tocando na máquina, e aceita comandos pela rede local — de forma que o celular possa trocar o preset sem tocar no teclado.

**Architecture:** Processo único, três threads. A thread principal é dona do contexto OpenGL e roda o loop de render a 60 fps, consumindo uma fila de comandos e publicando um instantâneo de estado. Uma thread captura o áudio do loopback WASAPI para um buffer circular. Uma terceira roda FastAPI e WebSocket, escrevendo na fila e lendo o estado — e nunca tocando em OpenGL. A fronteira entre backend e frontend é a API HTTP/WebSocket; a UI React é o plano seguinte (1b-2).

**Tech Stack:** Python 3.11, glfw, PyOpenGL, numpy, PyAudioWPatch, FastAPI, uvicorn, websockets, SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-09-18-chromesthesia-navegador-visual-design.md`

**Depende de (já entregue na Fase 1a, não modificar):** `engine/pm_ffi.py`, `engine/gl_context.py`, `engine/capture.py`, `indexer/db.py`, `indexer/milk_parser.py`, `config.py`, e `data/index.sqlite` populado com 9.795 presets.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `engine/commands.py` | Comandos, fila thread-safe e publicação de estado. **Puro** — sem GL, sem áudio, sem rede. |
| `engine/audio.py` | Buffer circular de áudio (puro) + thread de captura do loopback WASAPI |
| `engine/render_loop.py` | Loop de render: drena comandos, alimenta PCM, desenha, publica estado |
| `engine/app.py` | Monta as três threads e coordena o encerramento |
| `server/similarity.py` | Vizinhos mais próximos no espaço de features. **Puro.** |
| `server/api.py` | Endpoints REST sobre o índice |
| `server/ws.py` | WebSocket: comandos entram, estado sai |
| `server/main.py` | Monta o FastAPI e expõe na LAN |

A lógica testável sem hardware concentra-se em `engine/commands.py`, `engine/audio.py` (buffer) e `server/similarity.py`. O resto é integração, validada executando.

**Nota de ambiente:** o lote de posters da Fase 1a pode estar rodando e disputando a GPU. Se os testes que abrem contexto OpenGL ficarem lentos, confira com `Get-Process python` antes de suspeitar do código.

---

### Task 0: Verificação de ponto de partida

**Files:** nenhum

- [ ] **Step 1: Confirmar o estado herdado**

Run:
```bash
cd /c/Users/Jordh/chromesthesia
python -m pytest tests/ -q
python -c "import config,sqlite3; print('presets:', sqlite3.connect(str(config.DB_PATH)).execute('SELECT COUNT(*) FROM presets').fetchone()[0])"
python -c "import httpx, fastapi, uvicorn, pyaudiowpatch; print('deps ok')"
```
Expected: `42 passed`, `presets: 9795`, `deps ok`

- [ ] **Step 2: Criar o pacote do servidor**

```bash
printf '' > server/__init__.py
git add server/__init__.py && git commit -m "chore: pacote server"
```

---

### Task 1: Comandos e fila

**Files:**
- Create: `engine/commands.py`
- Test: `tests/test_commands.py`

A fila existe para que a thread do servidor nunca toque em OpenGL. Ela é o único canal entre rede e render.

- [ ] **Step 1: Escrever o teste que falha**

```python
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
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_commands.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.commands'`

- [ ] **Step 3: Implementar**

```python
# engine/commands.py
"""Canal entre a thread do servidor e a thread de render.

A thread de render e a unica dona do contexto OpenGL. Tudo que vem da rede
precisa atravessar esta fila; nenhuma outra thread chama a libprojectM.
"""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class LoadPreset:
    """Troca o preset em exibicao. smooth=False faz corte seco."""
    path: str
    smooth: bool = True


@dataclass(frozen=True)
class SetBeatSensitivity:
    """Reatividade a batida."""
    value: float


@dataclass(frozen=True)
class SetMeshSize:
    """Resolucao da malha de deformacao. Valvula de performance e estetica."""
    width: int
    height: int


@dataclass(frozen=True)
class Shutdown:
    """Pede o encerramento ordenado do loop de render."""


Command = Union[LoadPreset, SetBeatSensitivity, SetMeshSize, Shutdown]


class CommandQueue:
    """Fila de mao unica: servidor escreve, render drena uma vez por quadro."""

    def __init__(self, maxsize: int = 64) -> None:
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)

    def send(self, command: Command) -> bool:
        """Enfileira sem bloquear. Devolve False se a fila estiver cheia.

        Nao bloqueia de proposito: se o loop de render travar, o servidor
        precisa continuar respondendo em vez de pendurar junto.
        """
        try:
            self._queue.put_nowait(command)
            return True
        except queue.Full:
            return False

    def drain(self) -> list[Command]:
        """Remove e devolve tudo que esta pendente, na ordem de chegada."""
        pending: list[Command] = []
        while True:
            try:
                pending.append(self._queue.get_nowait())
            except queue.Empty:
                return pending
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_commands.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add engine/commands.py tests/test_commands.py
git commit -m "feat(engine): fila de comandos entre servidor e render"
```

---

### Task 2: Publicação de estado

**Files:**
- Modify: `engine/commands.py`
- Test: `tests/test_commands.py`

O caminho de volta: a thread de render publica o que está acontecendo, o servidor lê.

- [ ] **Step 1: Escrever o teste que falha**

```python
# acrescentar em tests/test_commands.py
import threading

from engine.commands import EngineState, StatePublisher


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
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_commands.py -v`
Expected: FAIL — `ImportError: cannot import name 'EngineState'`

- [ ] **Step 3: Implementar**

```python
# acrescentar em engine/commands.py
@dataclass(frozen=True)
class EngineState:
    """Instantaneo do que o motor esta fazendo. Imutavel de proposito."""
    preset_path: str = ""
    preset_name: str = ""
    fps: float = 0.0
    audio_peak: float = 0.0
    audio_connected: bool = False
    frame: int = 0


class StatePublisher:
    """Publica o estado do motor para leitores de outras threads.

    Como EngineState e congelado, trocar a referencia sob lock basta: quem le
    recebe um instantaneo coerente, nunca um objeto meio atualizado.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = EngineState()

    def publish(self, state: EngineState) -> None:
        """Substitui o estado corrente."""
        with self._lock:
            self._state = state

    def read(self) -> EngineState:
        """Devolve o estado corrente."""
        with self._lock:
            return self._state
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_commands.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add engine/commands.py tests/test_commands.py
git commit -m "feat(engine): publicacao de estado thread-safe por instantaneo imutavel"
```

---

### Task 3: Buffer circular de áudio

**Files:**
- Create: `engine/audio.py`
- Test: `tests/test_audio.py`

Esta parte é pura e não precisa de placa de som — por isso vem antes da captura.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_audio.py
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
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_audio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.audio'`

- [ ] **Step 3: Implementar**

```python
# engine/audio.py
"""Captura do audio do sistema e o buffer que a alimenta o render.

O dispositivo de loopback roda na taxa nativa da saida (48 kHz nesta maquina,
nao 44,1). A libprojectM nao assume taxa nenhuma: ela consome amostras e
deriva bass/mid/treb por bandas do espectro. Entao alimentamos como vem.
"""
from __future__ import annotations

import threading

import numpy as np


class AudioBuffer:
    """Buffer circular: a thread de captura escreve, a de render le o final.

    Nao ha garantia de continuidade entre leituras consecutivas, e nao
    precisa haver: o visualizador quer "o audio recente", nao um fluxo
    perfeitamente emendado.
    """

    def __init__(self, capacity: int = 48000, channels: int = 2) -> None:
        self._capacity = capacity
        self._channels = channels
        self._buffer = np.zeros((capacity, channels), dtype=np.float32)
        self._write_pos = 0
        self._written = 0
        self._lock = threading.Lock()

    def write(self, chunk: np.ndarray) -> None:
        """Escreve um bloco (n, canais). Bloco maior que a capacidade: guarda o final."""
        chunk = np.ascontiguousarray(chunk, dtype=np.float32)
        if chunk.shape[0] > self._capacity:
            chunk = chunk[-self._capacity:]
        n = chunk.shape[0]
        if n == 0:
            return
        with self._lock:
            end = self._write_pos + n
            if end <= self._capacity:
                self._buffer[self._write_pos:end] = chunk
            else:
                head = self._capacity - self._write_pos
                self._buffer[self._write_pos:] = chunk[:head]
                self._buffer[:n - head] = chunk[head:]
            self._write_pos = end % self._capacity
            self._written += n

    def read_latest(self, n: int) -> np.ndarray:
        """Devolve as n amostras mais recentes, em ordem cronologica."""
        n = min(n, self._capacity)
        with self._lock:
            start = (self._write_pos - n) % self._capacity
            if start + n <= self._capacity:
                return self._buffer[start:start + n].copy()
            head = self._capacity - start
            return np.concatenate([self._buffer[start:], self._buffer[:n - head]])

    @property
    def total_written(self) -> int:
        """Quantas amostras ja passaram pelo buffer desde a criacao."""
        with self._lock:
            return self._written
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_audio.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add engine/audio.py tests/test_audio.py
git commit -m "feat(engine): buffer circular de audio, testavel sem placa de som"
```

---

### Task 4: Captura do loopback

**Files:**
- Modify: `engine/audio.py`
- Modify: `indexer/capture_reference.py`
- Test: `tests/test_audio.py`

A descoberta de dispositivo hoje vive em `indexer/capture_reference.py`. Ela é preocupação de motor, não de indexador — mover para cá elimina a duplicação antes que ela exista.

- [ ] **Step 1: Escrever o teste que falha**

```python
# acrescentar em tests/test_audio.py
import pytest

from engine.audio import LoopbackCapture, LoopbackUnavailable, find_loopback_device


def test_encontra_o_dispositivo_de_loopback_da_saida_padrao():
    """Depende da maquina ter saida de audio ativa. Pula se nao tiver."""
    try:
        device = find_loopback_device()
    except LoopbackUnavailable as exc:
        pytest.skip(f"sem loopback nesta maquina: {exc}")
    assert device["maxInputChannels"] >= 1
    assert device["defaultSampleRate"] > 0


def test_captura_preenche_o_buffer():
    from engine.audio import AudioBuffer
    try:
        find_loopback_device()
    except LoopbackUnavailable as exc:
        pytest.skip(f"sem loopback nesta maquina: {exc}")

    buf = AudioBuffer(capacity=96000)
    cap = LoopbackCapture(buf)
    cap.start()
    try:
        assert cap.wait_until_running(timeout=5.0), "captura nao iniciou em 5s"
        assert cap.connected is True
    finally:
        cap.stop()
    assert cap.connected is False
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_audio.py -v`
Expected: FAIL — `ImportError: cannot import name 'LoopbackCapture'`

- [ ] **Step 3: Implementar**

```python
# acrescentar em engine/audio.py
import pyaudiowpatch as pyaudio


class LoopbackUnavailable(Exception):
    """Nao ha dispositivo de loopback utilizavel para a saida padrao."""


def find_loopback_device() -> dict:
    """Acha o dispositivo de loopback que corresponde a saida padrao do Windows."""
    audio = pyaudio.PyAudio()
    try:
        try:
            wasapi = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError as exc:
            raise LoopbackUnavailable(f"WASAPI indisponivel: {exc}") from exc
        speakers = audio.get_device_info_by_index(wasapi["defaultOutputDevice"])
        for device in audio.get_loopback_device_info_generator():
            if speakers["name"] in device["name"]:
                return device
        raise LoopbackUnavailable(
            f"nenhum loopback casou com a saida padrao ({speakers['name']})")
    finally:
        audio.terminate()


class LoopbackCapture:
    """Thread que despeja o audio da saida padrao dentro de um AudioBuffer.

    Se o dispositivo sumir ou falhar em runtime, a thread encerra e `connected`
    passa a False - o motor continua desenhando, so sem reagir ao som.
    """

    CHUNK = 1024

    def __init__(self, buffer: AudioBuffer) -> None:
        self._buffer = buffer
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._running = threading.Event()
        self.sample_rate = 0
        self.channels = 0

    @property
    def connected(self) -> bool:
        """Se a captura esta ativa neste momento."""
        return self._running.is_set()

    def start(self) -> None:
        """Sobe a thread de captura. Nao bloqueia."""
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="audio", daemon=True)
        self._thread.start()

    def wait_until_running(self, timeout: float = 5.0) -> bool:
        """Espera a captura comecar de fato. Util em teste e na subida do app."""
        return self._running.wait(timeout)

    def stop(self) -> None:
        """Pede parada e espera a thread sair."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._running.clear()

    def _run(self) -> None:
        audio = pyaudio.PyAudio()
        stream = None
        try:
            device = find_loopback_device()
            self.sample_rate = int(device["defaultSampleRate"])
            self.channels = int(device["maxInputChannels"])
            stream = audio.open(format=pyaudio.paFloat32, channels=self.channels,
                                rate=self.sample_rate, input=True,
                                input_device_index=device["index"],
                                frames_per_buffer=self.CHUNK)
            self._running.set()
            while not self._stop.is_set():
                raw = stream.read(self.CHUNK, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.float32).reshape(-1, self.channels)
                self._buffer.write(samples)
        except Exception:
            pass  # dispositivo sumiu ou falhou: encerra em silencio, motor segue
        finally:
            self._running.clear()
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            audio.terminate()
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_audio.py -v`
Expected: 9 passed (ou 7 passed 2 skipped, se a máquina não tiver loopback ativo)

- [ ] **Step 5: Remover a duplicação em `indexer/capture_reference.py`**

Substituir a função `find_loopback` local pelo import do motor. Abrir o arquivo e:
1. Apagar a definição de `find_loopback`
2. Acrescentar `from engine.audio import LoopbackUnavailable, find_loopback_device` aos imports
3. Em `record()`, trocar `device = find_loopback(pa)` por `device = find_loopback_device()`
4. Envolver a chamada para dar mensagem clara:

```python
    try:
        device = find_loopback_device()
    except LoopbackUnavailable as exc:
        raise SystemExit(f"sem loopback: {exc}")
```

- [ ] **Step 6: Confirmar que o CLI de referência continua funcionando**

Run: `python -m indexer.capture_reference --seconds 3 --out data/reference/teste_refactor.wav`
Expected: grava o WAV, ou informa silêncio e sai com 1 — em nenhum caso erro de import

- [ ] **Step 7: Commit**

```bash
git add engine/audio.py tests/test_audio.py indexer/capture_reference.py
git commit -m "feat(engine): captura do loopback como thread, deduplicada do indexador"
```

---

### Task 5: Loop de render

**Files:**
- Create: `engine/render_loop.py`

Integração: não tem teste unitário viável, é validado executando na Task 8.

- [ ] **Step 1: Implementar**

```python
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
```

- [ ] **Step 2: Conferir que importa sem erro**

Run: `python -c "import engine.render_loop; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add engine/render_loop.py
git commit -m "feat(engine): loop de render que drena comandos e publica estado"
```

---

### Task 6: Vizinhos no espaço de features

**Files:**
- Create: `server/similarity.py`
- Test: `tests/test_similarity.py`

O "mais assim" da UI. Puro, sem ML: distância euclidiana sobre features normalizadas.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_similarity.py
import numpy as np
import pytest

from server.similarity import nearest_ids, normalize_matrix


def test_normaliza_cada_coluna_para_zero_um():
    m = normalize_matrix(np.array([[0.0, 10.0], [5.0, 20.0], [10.0, 30.0]]))
    assert m[:, 0].tolist() == [0.0, 0.5, 1.0]
    assert m[:, 1].tolist() == [0.0, 0.5, 1.0]


def test_coluna_constante_vira_zero_em_vez_de_nan():
    """Divisao por amplitude zero nao pode virar NaN e contaminar a distancia."""
    m = normalize_matrix(np.array([[7.0, 1.0], [7.0, 2.0]]))
    assert m[:, 0].tolist() == [0.0, 0.0]
    assert not np.isnan(m).any()


def test_vizinhos_vem_do_mais_proximo_para_o_mais_distante():
    m = np.array([[0.0], [0.1], [0.5], [1.0]])
    assert nearest_ids(m, [10, 11, 12, 13], target_id=10, k=2) == [11, 12]


def test_o_proprio_alvo_nao_aparece_entre_os_vizinhos():
    m = np.array([[0.0], [0.1], [0.2]])
    assert 10 not in nearest_ids(m, [10, 11, 12], target_id=10, k=2)


def test_k_maior_que_o_disponivel_devolve_o_que_existe():
    m = np.array([[0.0], [1.0]])
    assert len(nearest_ids(m, [1, 2], target_id=1, k=99)) == 1


def test_id_desconhecido_e_erro():
    with pytest.raises(KeyError):
        nearest_ids(np.array([[0.0]]), [1], target_id=999, k=1)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_similarity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.similarity'`

- [ ] **Step 3: Implementar**

```python
# server/similarity.py
"""Vizinhos mais proximos no espaco de features dos presets.

Distancia euclidiana sobre features normalizadas por coluna. Sem ML e sem
embeddings: o vetor ja e numerico e o corpus cabe em memoria.
"""
from __future__ import annotations

import numpy as np

#: Colunas do indice que compoem o vetor. Ordem fixa: mudar aqui muda a vizinhanca.
FEATURE_COLUMNS = [
    "warp_anim_speed", "zoom", "rot", "warp", "zoom_exponent", "sx", "sy",
    "decay", "echo_alpha", "echo_zoom", "gamma",
    "wave_r", "wave_g", "wave_b", "wave_alpha",
    "n_shapes", "n_waves",
]


def normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    """Leva cada coluna para [0, 1]. Coluna constante vira zero, nunca NaN."""
    matrix = np.asarray(matrix, dtype=np.float64)
    low = matrix.min(axis=0)
    span = matrix.max(axis=0) - low
    safe = np.where(span == 0.0, 1.0, span)
    scaled = (matrix - low) / safe
    return np.where(span == 0.0, 0.0, scaled)


def nearest_ids(matrix: np.ndarray, ids: list[int], target_id: int,
                k: int = 12) -> list[int]:
    """Os k ids mais proximos do alvo, do mais parecido para o menos.

    A matriz deve vir de normalize_matrix; o alvo nunca aparece no resultado.
    """
    try:
        index = ids.index(target_id)
    except ValueError as exc:
        raise KeyError(f"id {target_id} nao esta na matriz") from exc

    distances = np.linalg.norm(matrix - matrix[index], axis=1)
    distances[index] = np.inf
    order = np.argsort(distances)[:k]
    return [ids[i] for i in order if np.isfinite(distances[i])]
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_similarity.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add server/similarity.py tests/test_similarity.py
git commit -m "feat(server): vizinhos por distancia euclidiana no espaco de features"
```

---

### Task 7: Endpoints REST

**Files:**
- Create: `server/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_api.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from engine.commands import CommandQueue, LoadPreset, StatePublisher
from indexer.db import connect, init_schema, upsert_preset
from indexer.milk_parser import PresetFeatures
from server.api import build_router


def _features(name, family="Hypnotic", subfamily="Polar Warp", decay=0.9, n_shapes=1):
    return PresetFeatures(
        path=f"C:/x/{family}/{subfamily}/{name}.milk", name=name, family=family,
        subfamily=subfamily, is_mirror=False, warp_anim_speed=1.0, zoom=1.0, rot=0.0,
        warp=0.2, zoom_exponent=1.0, sx=1.0, sy=1.0, decay=decay, echo_alpha=0.0,
        echo_zoom=1.0, gamma=1.2, brighten=False, darken=False, invert=False,
        solarize=False, darken_center=False, wave_r=0.3, wave_g=0.2, wave_b=0.6,
        wave_alpha=0.01, n_shapes=n_shapes, n_waves=0, has_warp_shader=True,
        has_comp_shader=True, psversion=2,
    )


@pytest.fixture()
def cliente(tmp_path):
    db = tmp_path / "t.sqlite"
    con = connect(db)
    init_schema(con)
    upsert_preset(con, _features("alfa"))
    upsert_preset(con, _features("beta", decay=0.5, n_shapes=4))
    upsert_preset(con, _features("gama", family="Geometric", subfamily="Cube"))
    con.commit()
    con.close()

    fila = CommandQueue()
    estado = StatePublisher()
    app = FastAPI()
    app.include_router(build_router(db, tmp_path / "previews", fila, estado))
    return TestClient(app), fila


def test_lista_familias_com_contagem(cliente):
    c, _ = cliente
    dados = c.get("/api/families").json()
    assert {"family": "Hypnotic", "count": 2} in dados
    assert {"family": "Geometric", "count": 1} in dados


def test_lista_presets_filtrando_por_familia(cliente):
    c, _ = cliente
    dados = c.get("/api/presets", params={"family": "Geometric"}).json()
    assert [p["name"] for p in dados["items"]] == ["gama"]
    assert dados["total"] == 1


def test_lista_pagina(cliente):
    c, _ = cliente
    dados = c.get("/api/presets", params={"limit": 1, "offset": 1}).json()
    assert len(dados["items"]) == 1
    assert dados["total"] == 3


def test_preset_traz_id_utilizavel(cliente):
    c, _ = cliente
    item = c.get("/api/presets").json()["items"][0]
    assert isinstance(item["id"], int) and item["id"] > 0


def test_carregar_preset_enfileira_comando(cliente):
    c, fila = cliente
    pid = c.get("/api/presets").json()["items"][0]["id"]
    assert c.post(f"/api/load/{pid}").status_code == 200
    comandos = fila.drain()
    assert len(comandos) == 1 and isinstance(comandos[0], LoadPreset)


def test_carregar_id_inexistente_da_404(cliente):
    c, _ = cliente
    assert c.post("/api/load/99999").status_code == 404


def test_similares_nao_incluem_o_proprio(cliente):
    c, _ = cliente
    pid = c.get("/api/presets").json()["items"][0]["id"]
    ids = [p["id"] for p in c.get(f"/api/similar/{pid}").json()]
    assert pid not in ids


def test_estado_do_motor(cliente):
    c, _ = cliente
    dados = c.get("/api/state").json()
    assert dados["frame"] == 0
    assert dados["audio_connected"] is False


def test_poster_ausente_da_404(cliente):
    c, _ = cliente
    pid = c.get("/api/presets").json()["items"][0]["id"]
    assert c.get(f"/api/poster/{pid}").status_code == 404
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.api'`

- [ ] **Step 3: Implementar**

```python
# server/api.py
"""Endpoints REST sobre o indice de presets.

O id publico de um preset e o rowid do SQLite: estavel entre reconstrucoes do
indice enquanto o caminho nao mudar, e seguro para URL - ao contrario do nome,
que tem espacos, acentos e pontuacao.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from engine.commands import CommandQueue, LoadPreset, StatePublisher
from server.similarity import FEATURE_COLUMNS, nearest_ids, normalize_matrix


def build_router(db_path: Path, preview_dir: Path, commands: CommandQueue,
                 state: StatePublisher) -> APIRouter:
    """Monta o roteador. Recebe as dependencias para ser testavel isoladamente."""
    router = APIRouter(prefix="/api")

    def _connect() -> sqlite3.Connection:
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        return con

    def _fetch_one(preset_id: int) -> sqlite3.Row:
        con = _connect()
        try:
            row = con.execute(
                "SELECT rowid AS id, * FROM presets WHERE rowid = ?",
                (preset_id,)).fetchone()
        finally:
            con.close()
        if row is None:
            raise HTTPException(status_code=404, detail="preset nao encontrado")
        return row

    @router.get("/families")
    def families() -> list[dict]:
        """Familias com quantidade de presets, da maior para a menor."""
        con = _connect()
        try:
            return [{"family": r["family"], "count": r["n"]} for r in con.execute(
                "SELECT family, COUNT(*) n FROM presets GROUP BY family ORDER BY n DESC")]
        finally:
            con.close()

    @router.get("/subfamilies")
    def subfamilies(family: str) -> list[dict]:
        """Subfamilias de uma familia, com quantidade."""
        con = _connect()
        try:
            return [{"subfamily": r["subfamily"], "count": r["n"]} for r in con.execute(
                "SELECT subfamily, COUNT(*) n FROM presets WHERE family = ? "
                "GROUP BY subfamily ORDER BY subfamily", (family,))]
        finally:
            con.close()

    @router.get("/presets")
    def presets(family: str | None = None, subfamily: str | None = None,
                limit: int = Query(60, ge=1, le=500),
                offset: int = Query(0, ge=0)) -> dict:
        """Pagina de presets, opcionalmente filtrada."""
        where, params = [], []
        if family is not None:
            where.append("family = ?")
            params.append(family)
        if subfamily is not None:
            where.append("subfamily = ?")
            params.append(subfamily)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        con = _connect()
        try:
            total = con.execute(f"SELECT COUNT(*) FROM presets{clause}",
                                params).fetchone()[0]
            rows = con.execute(
                f"SELECT rowid AS id, name, family, subfamily, contrast, motion, "
                f"poster_sig FROM presets{clause} ORDER BY family, subfamily, name "
                f"LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
        finally:
            con.close()
        return {
            "total": total,
            "items": [{"id": r["id"], "name": r["name"], "family": r["family"],
                       "subfamily": r["subfamily"], "contrast": r["contrast"],
                       "motion": r["motion"], "has_poster": r["poster_sig"] is not None}
                      for r in rows],
        }

    @router.get("/poster/{preset_id}")
    def poster(preset_id: int) -> FileResponse:
        """O poster WebP do preset, se ja tiver sido renderizado."""
        row = _fetch_one(preset_id)
        if row["poster_sig"] is None:
            raise HTTPException(status_code=404, detail="poster ainda nao renderizado")
        path = preview_dir / row["poster_sig"] / f"{row['name']}.webp"
        if not path.exists():
            raise HTTPException(status_code=404, detail="arquivo de poster ausente")
        return FileResponse(path, media_type="image/webp")

    @router.get("/similar/{preset_id}")
    def similar(preset_id: int, k: int = Query(12, ge=1, le=60)) -> list[dict]:
        """Presets mais parecidos no espaco de features.

        A matriz e remontada a cada chamada. Para 9.795 presets x 17 colunas
        isso e ~1,3 MB e poucos milissegundos - nao vale cachear antes de
        medir que incomoda.
        """
        _fetch_one(preset_id)
        con = _connect()
        try:
            rows = con.execute(
                f"SELECT rowid AS id, name, family, subfamily, poster_sig, "
                f"{', '.join(FEATURE_COLUMNS)} FROM presets").fetchall()
        finally:
            con.close()
        ids = [r["id"] for r in rows]
        matrix = normalize_matrix(
            np.array([[r[c] for c in FEATURE_COLUMNS] for r in rows], dtype=np.float64))
        chosen = nearest_ids(matrix, ids, preset_id, k)
        by_id = {r["id"]: r for r in rows}
        return [{"id": i, "name": by_id[i]["name"], "family": by_id[i]["family"],
                 "subfamily": by_id[i]["subfamily"],
                 "has_poster": by_id[i]["poster_sig"] is not None} for i in chosen]

    @router.post("/load/{preset_id}")
    def load(preset_id: int, smooth: bool = True) -> dict:
        """Manda o motor trocar para este preset."""
        row = _fetch_one(preset_id)
        accepted = commands.send(LoadPreset(path=row["path"], smooth=smooth))
        return {"accepted": accepted, "name": row["name"]}

    @router.get("/state")
    def engine_state() -> dict:
        """O que o motor esta fazendo agora."""
        return dataclasses.asdict(state.read())

    return router
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest tests/test_api.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add server/api.py tests/test_api.py
git commit -m "feat(server): REST do indice, com id publico no rowid do SQLite"
```

---

### Task 8: WebSocket e montagem do servidor

**Files:**
- Create: `server/ws.py`
- Create: `server/main.py`

- [ ] **Step 1: Implementar o WebSocket**

```python
# server/ws.py
"""WebSocket: o estado do motor sai, comandos entram.

O empurrao periodico de estado e o que mantem a UI do celular viva sem
polling. A frequencia e baixa de proposito - e informacao de status, nao
telemetria de quadro.
"""
from __future__ import annotations

import asyncio
import dataclasses

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from engine.commands import (CommandQueue, LoadPreset, SetBeatSensitivity,
                             SetMeshSize, StatePublisher)

PUSH_INTERVAL = 0.25


def build_ws_router(commands: CommandQueue, state: StatePublisher) -> APIRouter:
    """Monta o roteador do WebSocket."""
    router = APIRouter()

    @router.websocket("/ws")
    async def endpoint(websocket: WebSocket) -> None:
        await websocket.accept()

        async def push_state() -> None:
            while True:
                await websocket.send_json(
                    {"type": "state", **dataclasses.asdict(state.read())})
                await asyncio.sleep(PUSH_INTERVAL)

        pusher = asyncio.create_task(push_state())
        try:
            while True:
                message = await websocket.receive_json()
                kind = message.get("type")
                if kind == "load":
                    commands.send(LoadPreset(path=message["path"],
                                             smooth=message.get("smooth", True)))
                elif kind == "beat_sensitivity":
                    commands.send(SetBeatSensitivity(float(message["value"])))
                elif kind == "mesh_size":
                    commands.send(SetMeshSize(int(message["width"]),
                                              int(message["height"])))
        except WebSocketDisconnect:
            pass
        finally:
            pusher.cancel()

    return router
```

- [ ] **Step 2: Implementar a montagem**

```python
# server/main.py
"""Monta o FastAPI e o expoe na rede local.

Exposto em 0.0.0.0 de proposito: o controle roda no celular, em outro
aparelho da mesma rede.
"""
from __future__ import annotations

import socket
import threading

import uvicorn
from fastapi import FastAPI

import config
from engine.commands import CommandQueue, StatePublisher
from server.api import build_router
from server.ws import build_ws_router

HOST = "0.0.0.0"
PORT = 8765


def local_ip() -> str:
    """Endereco desta maquina na LAN, para imprimir na subida."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def build_app(commands: CommandQueue, state: StatePublisher) -> FastAPI:
    """Monta a aplicacao com as rotas REST e o WebSocket."""
    app = FastAPI(title="Chromesthesia")
    app.include_router(build_router(config.DB_PATH, config.PREVIEW_DIR, commands, state))
    app.include_router(build_ws_router(commands, state))
    return app


def serve_in_thread(commands: CommandQueue, state: StatePublisher) -> threading.Thread:
    """Sobe o uvicorn numa thread propria. Nunca toca em OpenGL."""
    server = uvicorn.Server(uvicorn.Config(
        build_app(commands, state), host=HOST, port=PORT, log_level="warning"))
    thread = threading.Thread(target=server.run, name="server", daemon=True)
    thread.start()
    return thread
```

- [ ] **Step 3: Conferir que importam**

Run: `python -c "import server.ws, server.main; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add server/ws.py server/main.py
git commit -m "feat(server): WebSocket de estado e comandos, exposto na LAN"
```

---

### Task 9: Montagem das três threads

**Files:**
- Create: `engine/app.py`

- [ ] **Step 1: Implementar**

```python
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
                projectm.load_preset_file(inicial, smooth=False)
            try:
                run_render_loop(context, projectm, audio, capture, commands, state)
            except KeyboardInterrupt:
                pass
    capture.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Commit**

```bash
git add engine/app.py
git commit -m "feat(engine): ponto de entrada com as tres threads"
```

---

### Task 10: Validação ponta a ponta

**Files:** nenhum

- [ ] **Step 1: Rodar a suíte completa**

Run: `python -m pytest tests/ -q`
Expected: todos passam (42 herdados + os novos desta fase)

- [ ] **Step 2: Subir o motor com música tocando**

Run: `python -m engine.app`
Expected: janela abre, visuais reagem ao som, e o terminal imprime os dois endereços

- [ ] **Step 3: Conferir a API pela máquina local**

Em outro terminal:
```bash
curl -s http://127.0.0.1:8765/api/families
curl -s "http://127.0.0.1:8765/api/presets?family=Hypnotic&limit=3"
curl -s http://127.0.0.1:8765/api/state
```
Expected: JSON com as famílias e suas contagens, três presets com `id`, e o estado com `fps` perto de 60 e `audio_connected: true`

- [ ] **Step 4: Trocar o preset pela rede e confirmar na tela**

```bash
curl -s -X POST http://127.0.0.1:8765/api/load/1
```
Expected: `{"accepted": true, ...}` e a janela do visualizador troca de preset

- [ ] **Step 5: Conferir o poster pela API**

```bash
curl -s -o /tmp/poster.webp -w "%{http_code} %{content_type}\n" http://127.0.0.1:8765/api/poster/1
```
Expected: `200 image/webp`

- [ ] **Step 6: Alcançar do celular**

Abrir `http://192.168.0.226:8765/docs` no navegador do celular, na mesma rede Wi-Fi.
Expected: a documentação interativa do FastAPI carrega.

Se não carregar, é o Firewall do Windows — rode num PowerShell como administrador:
```
netsh advfirewall firewall add rule name="Chromesthesia" dir=in action=allow protocol=TCP localport=8765
```
**VPN ligada também quebra o alcance da LAN.** Se estiver conectado à VPN, desconecte para testar.

- [ ] **Step 7: Encerrar limpo**

Fechar a janela do visualizador.
Expected: o processo encerra sem travar e sem stack trace

- [ ] **Step 8: Commit final da fase**

```bash
git add -A
git commit -m "chore: Fase 1b-1 concluida - motor ao vivo controlavel pela LAN"
```

---

## Feito quando

- A suíte inteira passa
- `python -m engine.app` abre a janela, reage ao áudio do sistema e imprime o endereço da LAN
- `POST /api/load/{id}` troca o preset na tela
- `GET /api/poster/{id}` devolve a imagem
- O celular na mesma rede abre `/docs`
- Fechar a janela encerra o processo sem erro

## Próximo plano (Fase 1b-2)

UI React + TypeScript (Vite), responsiva de 390px a 1920px: navegação família → subfamília → grid virtualizado, poster estático no grid e animação no hover/toque, clique carrega ao vivo, favoritos, e "mais assim" consumindo `/api/similar`. Consome esta API sem alteração no backend.
