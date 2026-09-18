# Sala — Fases 0 e 1: motor Python + navegador visual de presets

**Data:** 2026-09-18
**Status:** aprovado pelo usuário (ver "Decisões" abaixo)

## Contexto e objetivo

Projeto pessoal para o quarto de música: curtir visuais do projectM ouvindo música, com
seleção de presets que hoje é inutilizável (9.795 arquivos, nomes centrados no autor,
zero preview).

Este documento cobre **apenas as Fases 0 e 1**. O pad de emoção (Fase 2) e a geração por
LLM (Fase 3) têm specs próprias e dependem do índice construído aqui.

**Critério de sucesso da Fase 1:** conseguir encontrar um preset que combine com o que
está tocando em menos de 30 segundos, olhando para imagens em vez de nomes.

## Achados de investigação que moldam o design

Verificados empiricamente contra o binário e o código-fonte da 4.1.4:

1. **`glewInit()` é obrigatório antes de `projectm_create()`.** Sem ele: access violation
   escrevendo em `0x0` (ponteiros de função GL nulos). O frontend SDL faz isso em
   `SDLRenderingWindow.cpp:276`. Provado: com `glewInit()`, o tubo ctypes→GL→projectM roda
   a 119 fps na Intel Iris Xe.
2. **`projectm_write_debug_image_on_next_frame()` é um no-op.** `ProjectMCWrapper.cpp:374`
   tem literalmente `// UNIMPLEMENTED`. A função existe no header e é exportada pela DLL,
   mas não faz nada. Captura de frame deve usar `glReadPixels` do lado do Python.
3. **`bass`/`mid`/`treb` são valores com AGC**, não energia absoluta
   (`Loudness.cpp:48`: `m_currentRelative = m_current / m_longAverage`). A média longa usa
   relógio real (`TimeKeeper.cpp:19`, `std::chrono`), mas os primeiros 50 frames usam taxa
   de convergência rápida (`frame < 50 ? 0.9 : 0.992`), então assenta em < 0,5 s a 119 fps.
4. **`fRating` é inútil como sinal de qualidade:** 9.790 dos 9.795 valem exatamente
   `5.000000`.
5. **A taxonomia já existe.** O pacote *cream-of-the-crop* vem curado em 10 famílias de
   topo (Reaction 1791, Fractal 1354, Dancer 1351, Waveform 1279, Drawing 1143,
   Geometric 1027, Sparkle 797, Particles 389, Supernova 380, Hypnotic 280) e ~200
   subfamílias. Não é preciso classificar do zero — é preciso deixar ver.
6. **Custo real de preview medido:** 2,8–3,6 s e ~830 KB por preset animado (40 frames,
   320×180, WebP q72). Extrapolado: 8,3 h e 8 GB para o corpus inteiro. Inaceitável como
   está — ver "Estratégia de previews".
7. **ffmpeg não é necessário.** Pillow 11.3 grava WebP animado nativamente.

## Arquitetura

Processo único, três threads. A regra estrutural que domina tudo: **contexto OpenGL não
atravessa thread.**

```
Processo Python
├── Thread MAIN ..... contexto GL (glfw) + loop de render a 60 fps
│                     consome CommandQueue; é a ÚNICA que toca em GL
├── Thread AUDIO .... WASAPI loopback (PyAudioWPatch) → ring buffer float32
└── Thread SERVER ... FastAPI + uvicorn + WebSocket
                      só escreve na CommandQueue e lê StateSnapshot
```

O servidor nunca executa chamadas GL. Violar isso produz crash silencioso.

### Módulos

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `engine/pm_ffi.py` | Binding ctypes para `projectM-4.dll`. Sem lógica. | ctypes |
| `engine/audio.py` | Captura loopback → ring buffer | PyAudioWPatch |
| `engine/renderer.py` | Janela glfw, contexto, `glewInit()`, loop de render | glfw, PyOpenGL |
| `engine/commands.py` | Fila thread-safe e snapshot de estado | stdlib |
| `engine/main.py` | Monta as três threads | todos acima |
| `indexer/milk_parser.py` | `.milk` → dict de features. **Função pura**, sem GL, sem rede. | stdlib |
| `indexer/reference.py` | Fonte do sinal de referência (sintético ou arquivo) | numpy |
| `indexer/build_index.py` | Varre presets → SQLite | milk_parser |
| `indexer/render_previews.py` | projectM headless → glReadPixels → WebP | renderer, reference, Pillow |
| `server/api.py` | REST: listagem filtrada, previews | FastAPI |
| `server/ws.py` | WebSocket: comandos ↔ estado | websockets |
| `ui/` | React + TS (Vite), responsivo 390px→1920px | — |

`milk_parser.py` concentra a maior parte da lógica e é função pura — é onde ficam os testes.

## Sinal de referência

Todos os previews precisam reagir ao **mesmo** estímulo, senão o grid não serve para
comparar nada.

`indexer/reference.py` expõe duas implementações intercambiáveis por configuração:

- **`synthetic`** (padrão): 10 s determinísticos — kick a 120 BPM na banda grave, pad
  sustentado na média, hi-hat na aguda, com build-up no final. Reproduzível bit-a-bit,
  sem copyright, e projetado para exercitar as três bandas num padrão conhecido.
- **`file`**: trecho de um arquivo de áudio apontado na config (decodificado para
  float32 estéreo a 44,1 kHz). Previews mais representativos do que o usuário
  realmente escuta.

  **Dependência de decodificação:** o Python padrão só lê WAV. Para aceitar MP3/FLAC/OGG
  usar `miniaudio` (`pip install miniaudio`) — wheel autocontido, sem binário externo.
  Deliberadamente **não** usar `pydub`, que depende de ffmpeg — e o ffmpeg falhou ao
  instalar nesta máquina.

**Regra invariante:** o cache de previews é versionado pelo hash do sinal de referência —
`data/previews/<sig_hash>/<preset_id>.webp`. Trocar de sinal não corrompe a
comparabilidade; apenas começa um cache novo.

**Warmup:** 150 frames renderizados antes de capturar, para o AGC assentar e para o
buffer de feedback do preset se desenvolver. Frames 0–49 usam a convergência rápida
embutida da lib; 150 dá margem confortável sem desperdiçar tempo.

## Estratégia de previews (resolve os 8 GB / 8,3 h)

Duas camadas:

1. **Poster estático** — todos os 9.795. Warmup de 150 frames + um `glReadPixels`.
   ~1,3 s e ~15 KB cada → **~3,5 h e ~150 MB** para o corpus inteiro. Roda de madrugada.
2. **Preview animado** — sob demanda, quando o usuário passa o mouse (monitor) ou toca
   (celular). 24 frames a 20 fps (1,2 s de loop), 256×144, WebP q50 (~190 KB estimado).
   Gerado uma vez e cacheado.

Geração priorizada por famílias pequenas primeiro (Hypnotic 280 → Supernova 380 →
Particles 389), para haver o que navegar em ~30 min. Cache idempotente: arquivo existe,
pula.

## Índice de features

SQLite (`data/index.sqlite`), não JSON — a Fase 2 fará consultas por faixa
(`WHERE fDecay BETWEEN ? AND ? AND n_shapes > ?`) e não vale reescrever depois.

| Grupo | Campos |
|---|---|
| Identidade | `path`, `family`, `subfamily`, `name`, `is_mirror` |
| Movimento | `fWarpAnimSpeed`, `zoom`, `rot`, `warp`, `fZoomExponent`, `sx`, `sy` |
| Persistência | `fDecay`, `fVideoEchoAlpha`, `fVideoEchoZoom` |
| Luz | `fGammaAdj`, `bBrighten`, `bDarken`, `bInvert`, `bSolarize`, `bDarkenCenter` |
| Cor | `wave_r`, `wave_g`, `wave_b`, `fWaveAlpha` |
| Densidade | `n_shapes`, `n_waves`, `has_warp_shader`, `has_comp_shader`, `psversion` |
| Qualidade | `contrast`, `motion` (calculados na geração do poster) |

`contrast` (desvio-padrão do frame) e `motion` (diferença média entre primeiro e último
frame) foram medidos e discriminam bem (53–60 e 47–49 nas amostras). Servem tanto para
filtrar presets mortos quanto como portão de qualidade da Fase 3.

Todos os campos numéricos têm cobertura de 100% no corpus (verificado em amostra de 400).

## UI da Fase 1

Responsiva de 390px (celular na LAN) a 1920px (monitor). Mesmo código nos dois.

- **Navegação em três níveis:** família → subfamília → grid. Nunca 9.795 de uma vez.
- Grid virtualizado, carregamento preguiçoso por `IntersectionObserver`.
- Poster estático no grid; anima no hover/toque. Animar dezenas ao mesmo tempo derrete a
  Iris Xe.
- Clicar carrega o preset no motor ao vivo (via WebSocket).
- Favoritar.
- **"Mais assim"**: vizinhos por distância euclidiana sobre o vetor de features
  normalizado. Sem ML, sem embeddings.

Restrições de design vindas do contexto (operado no escuro, olhando para a TV, não para o
controle): tema escuro, alvos ≥44px, nenhuma ação destrutiva, tudo reversível.

**Fora do escopo da Fase 1:** pad de emoção, reescrita de parâmetros no carregamento,
dials ao vivo. Tudo isso é Fase 2.

## Testes

- `milk_parser`: unitários com presets reais de cada uma das 10 famílias, incluindo casos
  degenerados (preset sem shader, sem shapes, com campos ausentes).
- `reference`: determinismo — o mesmo seed produz o mesmo hash de buffer.
- `pm_ffi`: smoke test de create/destroy sem vazamento de handle.
- Loop de render: sem teste automatizado viável. Validação é visual — é para isso que a
  Fase 0 existe.

## Riscos

| Risco | Estado | Mitigação |
|---|---|---|
| ctypes + contexto GL | **RESOLVIDO** | `glewInit()` + `glewExperimental=1` antes de `projectm_create()` |
| Captura de frame | **RESOLVIDO** | `glReadPixels`; a API de debug da lib é no-op |
| Python da Microsoft Store restringe DLL | **RESOLVIDO** | `os.add_dll_directory(APP)` antes do `CDLL` |
| Tamanho/tempo dos previews | Mitigado | Duas camadas: poster para todos, animado sob demanda |
| Iris Xe engasga em preset pesado | Aberto | `projectm_set_mesh_size()` como válvula |

## Decisões

1. **Sinal de referência configurável** entre `synthetic` (padrão) e `file`, com cache
   versionado pelo hash do sinal. — *pedido explícito do usuário*
2. **SQLite** em vez de JSON. — aprovado
3. **`git init`** em `C:\Users\Jordh\projectM` com e-mail pessoal. — aprovado
4. **ffmpeg descartado** da lista de dependências: Pillow grava WebP animado. O
   `winget install Gyan.FFmpeg` falhou com `0x80072f7d` (falha de TLS, provável
   interceptação por VPN) e não precisa ser resolvido.
