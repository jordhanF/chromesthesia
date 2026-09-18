# Chromesthesia

> *Cromestesia* é a forma de sinestesia em que som dispara percepção de cor — algumas
> pessoas veem música. Este projeto tenta construir isso para o resto de nós.

Visualizador de música para quarto de som, construído sobre a
[libprojectM](https://github.com/projectM-visualizer/projectm) 4.1.4 — a reimplementação
open-source do Winamp Milkdrop.

O objetivo não é mais um player de visualizações. É resolver três problemas que a
experiência padrão não resolve:

1. **Navegar 9.795 presets é impossível hoje.** Os nomes são centrados no autor
   (`Goody's Lightning (ps 2-0) --- Isosceles edit.milk`) e não existe pré-visualização.
   A solução é um índice com posters renderizados, organizado pela taxonomia que o
   próprio pacote *cream-of-the-crop* já traz — 10 famílias, ~200 subfamílias.
2. **Escolher visual por emoção, não por nome.** Um pad 2D de valência × ativação mais um
   dial de densidade, mapeado em três camadas: filtro de seleção, reescrita de parâmetros
   no carregamento e dials ao vivo da API.
3. **Gerar presets novos com LLM.** O formato `.milk` é texto e
   `projectm_load_preset_data()` aceita string, então dá para gerar, validar
   automaticamente e curar.

## Estado

| Fase | Escopo | Estado |
|---|---|---|
| 0 | Motor via ctypes, sem compilar nada | **concluída** |
| 1a | Índice SQLite + posters do corpus | plano escrito |
| 1b | Motor ao vivo + servidor + UI React responsiva | a planejar |
| 2 | Pad de emoção | a planejar |
| 3 | Geração de presets por LLM | a planejar |

Documentos em [`docs/superpowers/`](docs/superpowers/).

## Por que Python e ctypes

A `projectM-4.dll` exporta uma API C pura. Isso significa que dá para usá-la **sem
compilador nenhum** — nada de CMake, Visual Studio ou vcpkg. O tubo completo foi provado:
`ctypes` → DLL → contexto OpenGL → render a **119 fps** numa Intel Iris Xe integrada.

Os scripts descartáveis que provaram isso estão em [`tests/`](tests/) com o prefixo
`smoke_`.

## Armadilhas da libprojectM 4.1.4

Verificadas empiricamente contra o binário e o código-fonte. Podem poupar o dia de
alguém:

- **`glewInit()` é obrigatório antes de `projectm_create()`.** Sem ele, a chamada morre
  com *access violation writing `0x0`* — os ponteiros das funções OpenGL vivem dentro do
  GLEW e começam nulos. Em perfil core, também é preciso `glewExperimental = 1`.
- **`projectm_write_debug_image_on_next_frame()` não faz nada.** Está documentada no
  header e exportada pela DLL, mas o corpo é literalmente `// UNIMPLEMENTED`
  (`ProjectMCWrapper.cpp:374`). Use `glReadPixels`.
- **`bass`/`mid`/`treb` não são energia absoluta.** Têm AGC embutido:
  `m_current / m_longAverage` (`Loudness.cpp:48`), com relógio real e convergência rápida
  nos primeiros 50 frames. Injetar nível constante no PCM é absorvido em segundos — só
  transiente e modulação movem o valor.
- **`fRating` é inútil como sinal de qualidade:** 9.790 dos 9.795 presets do pacote valem
  exatamente `5.000000`.
- **O sinal de referência quase não importa.** Medindo contraste e movimento, previews
  renderizados com sinal sintético e com música real ficam estatisticamente
  indistinguíveis — consequência direta do AGC. A escolha é estética, não técnica.

## Requisitos

- Windows com uma GPU que suporte OpenGL 3.3 core
- Python 3.11+
- `pip install -r requirements.txt`
- Uma build da libprojectM. A mais simples é baixar o
  [projectMSDL](https://github.com/projectM-visualizer/frontend-sdl-cpp/releases), que já
  traz `projectM-4.dll`, `glew32.dll`, presets e texturas. Aponte `CHROMESTHESIA_APP_DIR` para a
  pasta extraída.

## Como rodar

Construir o índice e os posters (uma vez, leva horas para o corpus inteiro):

```bash
python -m indexer.build_index
python -m indexer.render_posters
python -m indexer.render_posters --redo-below-contrast 20 --warmup 1200
```

Subir o motor ao vivo:

```bash
python -m engine.app
```

A janela abre, reage ao áudio que estiver tocando, e o terminal imprime o endereço da
máquina na rede. Do celular, `http://<ip>:8765/docs`.

**Duas armadilhas operacionais, ambas medidas:**

- **Rode num terminal de verdade.** Lançado em segundo plano ou destacado do console, o
  processo recebe evento de fechamento e morre logo após subir o servidor — sem
  traceback, o que engana. É um aplicativo de janela; ele quer um console.
- **Não minimize a janela.** O driver estrangula renderização de janela oculta: medido
  **120 fps visível contra 16–26 fps minimizada**, no mesmo preset. Se o visual
  engasgar, a primeira coisa a conferir é se a janela está em primeiro plano — não o
  código.

Se o celular não alcançar, libere a porta num PowerShell como administrador:

```
netsh advfirewall firewall add rule name="Chromesthesia" dir=in action=allow protocol=TCP localport=8765
```

VPN ligada também quebra o alcance da rede local.

## Licença

A libprojectM é LGPL-2.1. Este repositório contém apenas código próprio e não redistribui
binários nem presets.
