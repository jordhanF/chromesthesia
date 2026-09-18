# Chromesthesia — Fase 1b-2: interface de navegação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encontrar um preset que combine com o que está tocando em menos de 30 segundos, olhando imagens em vez de nomes — do celular no sofá ou do segundo monitor.

**Architecture:** React + TypeScript servido pelo próprio FastAPI da Fase 1b-1, consumindo `/api/*` e o WebSocket `/ws` sem alteração no backend. Estado do servidor não é duplicado no cliente: o preset em exibição vem do WebSocket, não de otimismo local. Favoritos vivem em `localStorage` — são preferência de aparelho, não dado compartilhado.

**Tech Stack:** Vite, React 18, TypeScript, Vitest, CSS puro com variáveis (sem framework de UI).

**Spec:** `docs/superpowers/specs/2026-09-18-chromesthesia-navegador-visual-design.md`

**Depende de (Fase 1b-1, não modificar):** `server/api.py`, `server/ws.py`, `server/main.py`, `engine/*`, e `data/index.sqlite` com 9.795 presets e seus posters.

---

## Direção de design

**A interface não pode competir com o conteúdo.** Dezenas de posters psicodélicos saturados aparecem na tela ao mesmo tempo. Sombra de card, borda arredondada ou gradiente decorativo viram ruído disputando atenção com exatamente aquilo que o usuário está tentando comparar.

Daí o conceito: **câmara escura**. Fundo preto real, posters sem moldura flutuando sobre ele, tipografia que recua. Os posters são a única fonte de luz da tela.

Três consequências concretas:

1. **Sem molduras, sem cards, sem sombras.** Um poster no grid é só a imagem. A separação vem do espaço, não de linha.
2. **A cor de acento é extraída do poster em exibição.** Quando o preset muda, o brilho da interface migra junto. É o nome do projeto aplicado à própria interface — e é a única cor saturada do cromo.
3. **Tipografia em duas vozes.** Fraunces (serifada de alto contraste, opsz variável) só para nomes de família e o preset em exibição. IBM Plex Mono para tudo que é denso — os nomes de preset são literalmente nomes de arquivo com pontuação estranha, e monoespaçada honra isso em vez de disfarçar.

**Restrições que vêm do contexto de uso**, não de gosto: operada no escuro, possivelmente sem óculos, com o olhar na TV e não no controle. Alvos de toque ≥44px, nada destrutivo, tudo reversível, e nenhum estado que exija leitura atenta para ser entendido.

### Fora de escopo, com motivo

**Previews animados ficam para depois.** Gerar um exige contexto OpenGL próprio, e o do motor está ocupado desenhando ao vivo na thread principal — precisaria de subprocesso, com ~3s de latência e 2,4 GB se pré-gerado. Os posters estáticos já resolvem o critério de sucesso declarado. Só vale pagar esse custo se navegar por imagem parada se mostrar insuficiente na prática.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `ui/src/api.ts` | Cliente tipado dos endpoints. **Puro**, testável com fetch falso. |
| `ui/src/useEngineState.ts` | Assina o WebSocket e devolve o estado do motor |
| `ui/src/useFavorites.ts` | Favoritos em `localStorage`. **Lógica pura**, testável. |
| `ui/src/accent.ts` | Extrai a cor dominante de um poster. **Puro.** |
| `ui/src/styles.css` | Tokens, tipografia, base |
| `ui/src/components/FamilyRail.tsx` | Navegação família → subfamília |
| `ui/src/components/PosterTile.tsx` | Um poster no grid |
| `ui/src/components/PosterGrid.tsx` | Grid com carregamento preguiçoso |
| `ui/src/components/NowPlaying.tsx` | O preset em exibição, fora do grid |
| `ui/src/App.tsx` | Composição |

Lógica testável concentra-se em `api.ts`, `useFavorites.ts` e `accent.ts`. Componentes visuais são validados olhando.

---

### Task 0: Scaffold

**Files:**
- Create: `ui/package.json`, `ui/tsconfig.json`, `ui/vite.config.ts`, `ui/index.html`

- [ ] **Step 1: Criar o projeto**

```bash
cd /c/Users/Jordh/chromesthesia
npm create vite@latest ui -- --template react-ts
cd ui && npm install && npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom
```

- [ ] **Step 2: Apagar o boilerplate que o Vite gera**

```bash
cd /c/Users/Jordh/chromesthesia/ui
rm -f src/App.css src/index.css src/assets/react.svg public/vite.svg
```

- [ ] **Step 3: Configurar proxy para o backend e o Vitest**

```typescript
// ui/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // O backend da Fase 1b-1 roda em 8765. O proxy evita CORS em desenvolvimento
  // e mantem o mesmo caminho relativo que vale em producao, quando o FastAPI
  // serve o build estatico.
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/ws": { target: "ws://127.0.0.1:8765", ws: true },
    },
  },
  build: { outDir: "dist" },
  test: { environment: "jsdom", globals: true },
});
```

- [ ] **Step 4: Confirmar que o scaffold sobe**

Run: `cd /c/Users/Jordh/chromesthesia/ui && npm run build`
Expected: build conclui sem erro, gera `dist/`

- [ ] **Step 5: Ignorar artefatos no git**

Confirmar que `.gitignore` na raiz já contém `ui/node_modules/` e `ui/dist/`. Já contém — verificar com `grep -n "ui/" ../.gitignore`.

- [ ] **Step 6: Commit**

```bash
cd /c/Users/Jordh/chromesthesia
git add ui/
git commit -m "chore(ui): scaffold Vite + React + TS com proxy para o backend"
```

---

### Task 1: Cliente tipado da API

**Files:**
- Create: `ui/src/api.ts`
- Test: `ui/src/api.test.ts`

- [ ] **Step 1: Escrever o teste que falha**

```typescript
// ui/src/api.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchFamilies, fetchPresets, loadPreset, posterUrl } from "./api";

function mockFetch(payload: unknown, ok = true, status = 200) {
  const spy = vi.fn().mockResolvedValue({
    ok, status, json: async () => payload,
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => vi.unstubAllGlobals());

describe("api", () => {
  it("busca familias", async () => {
    mockFetch([{ family: "Reaction", count: 1791 }]);
    expect(await fetchFamilies()).toEqual([{ family: "Reaction", count: 1791 }]);
  });

  it("monta a query de presets com os filtros presentes", async () => {
    const spy = mockFetch({ total: 0, items: [] });
    await fetchPresets({ family: "Hypnotic", limit: 30, offset: 60 });
    const url = spy.mock.calls[0][0] as string;
    expect(url).toContain("family=Hypnotic");
    expect(url).toContain("limit=30");
    expect(url).toContain("offset=60");
  });

  it("omite filtros nao informados em vez de mandar vazio", async () => {
    const spy = mockFetch({ total: 0, items: [] });
    await fetchPresets({ limit: 10 });
    expect(spy.mock.calls[0][0]).not.toContain("family=");
  });

  it("escapa nome de subfamilia com espaco", async () => {
    const spy = mockFetch({ total: 0, items: [] });
    await fetchPresets({ family: "Hypnotic", subfamily: "Polar Warp" });
    expect(spy.mock.calls[0][0]).toContain("subfamily=Polar+Warp");
  });

  it("levanta erro legivel quando a resposta falha", async () => {
    mockFetch({}, false, 503);
    await expect(fetchFamilies()).rejects.toThrow(/503/);
  });

  it("carregar preset usa POST", async () => {
    const spy = mockFetch({ accepted: true, name: "x" });
    await loadPreset(42);
    expect(spy.mock.calls[0][1]).toMatchObject({ method: "POST" });
    expect(spy.mock.calls[0][0]).toContain("/api/load/42");
  });

  it("url de poster e estavel e relativa", () => {
    expect(posterUrl(7)).toBe("/api/poster/7");
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd ui && npx vitest run src/api.test.ts`
Expected: FAIL — não resolve `./api`

- [ ] **Step 3: Implementar**

```typescript
// ui/src/api.ts
/**
 * Cliente dos endpoints da Fase 1b-1.
 *
 * O id publico de um preset e o rowid do SQLite - os nomes tem espaco, acento
 * e pontuacao e nao sobrevivem a uma URL sem sofrimento.
 */

export interface Family {
  family: string;
  count: number;
}

export interface Subfamily {
  subfamily: string;
  count: number;
}

export interface Preset {
  id: number;
  name: string;
  family: string;
  subfamily: string;
  has_poster: boolean;
  /**
   * Opcionais de proposito: /api/presets devolve os dois, /api/similar nao.
   * Marcar como obrigatorios faria o TypeScript mentir sobre a resposta de
   * similar, e o erro so apareceria em tempo de execucao.
   */
  contrast?: number | null;
  motion?: number | null;
}

export interface PresetPage {
  total: number;
  items: Preset[];
}

export interface EngineState {
  preset_path: string;
  preset_name: string;
  fps: number;
  audio_peak: number;
  audio_connected: boolean;
  frame: number;
}

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} respondeu ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchFamilies(): Promise<Family[]> {
  return get<Family[]>("/api/families");
}

export function fetchSubfamilies(family: string): Promise<Subfamily[]> {
  return get<Subfamily[]>(`/api/subfamilies?family=${encodeURIComponent(family)}`);
}

export interface PresetQuery {
  family?: string;
  subfamily?: string;
  limit?: number;
  offset?: number;
}

export function fetchPresets(query: PresetQuery): Promise<PresetPage> {
  const params = new URLSearchParams();
  if (query.family !== undefined) params.set("family", query.family);
  if (query.subfamily !== undefined) params.set("subfamily", query.subfamily);
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  if (query.offset !== undefined) params.set("offset", String(query.offset));
  return get<PresetPage>(`/api/presets?${params.toString()}`);
}

export function fetchSimilar(id: number, k = 12): Promise<Preset[]> {
  return get<Preset[]>(`/api/similar/${id}?k=${k}`);
}

export function fetchState(): Promise<EngineState> {
  return get<EngineState>("/api/state");
}

/** Caminho do poster. Relativo de proposito: vale em dev e em producao. */
export function posterUrl(id: number): string {
  return `/api/poster/${id}`;
}

export async function loadPreset(id: number, smooth = true): Promise<void> {
  const response = await fetch(`/api/load/${id}?smooth=${smooth}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`nao foi possivel carregar o preset ${id}: ${response.status}`);
  }
}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd ui && npx vitest run src/api.test.ts`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add ui/src/api.ts ui/src/api.test.ts
git commit -m "feat(ui): cliente tipado dos endpoints"
```

---

### Task 2: Extração de cor do poster

**Files:**
- Create: `ui/src/accent.ts`
- Test: `ui/src/accent.test.ts`

É o elemento que dá identidade à interface: a cor do cromo vem do preset em exibição.

- [ ] **Step 1: Escrever o teste que falha**

```typescript
// ui/src/accent.test.ts
import { describe, expect, it } from "vitest";
import { dominantAccent, FALLBACK_ACCENT } from "./accent";

/** Monta um bloco RGBA como o que canvas.getImageData devolve. */
function pixels(...cores: Array<[number, number, number]>): Uint8ClampedArray {
  const out = new Uint8ClampedArray(cores.length * 4);
  cores.forEach(([r, g, b], i) => {
    out[i * 4] = r; out[i * 4 + 1] = g; out[i * 4 + 2] = b; out[i * 4 + 3] = 255;
  });
  return out;
}

describe("dominantAccent", () => {
  it("prefere pixel saturado a pixel cinza", () => {
    const cor = dominantAccent(pixels([128, 128, 128], [128, 128, 128], [220, 20, 60]));
    expect(cor).toBe("rgb(220, 20, 60)");
  });

  it("ignora preto, que domina posters escuros sem dizer nada", () => {
    const cor = dominantAccent(pixels([0, 0, 0], [0, 0, 0], [0, 0, 0], [40, 200, 160]));
    expect(cor).toBe("rgb(40, 200, 160)");
  });

  it("ignora branco estourado pelo mesmo motivo", () => {
    const cor = dominantAccent(pixels([255, 255, 255], [255, 255, 255], [90, 60, 200]));
    expect(cor).toBe("rgb(90, 60, 200)");
  });

  it("devolve a cor de reserva quando nao ha nada utilizavel", () => {
    expect(dominantAccent(pixels([0, 0, 0], [255, 255, 255]))).toBe(FALLBACK_ACCENT);
  });

  it("devolve a cor de reserva para entrada vazia", () => {
    expect(dominantAccent(new Uint8ClampedArray(0))).toBe(FALLBACK_ACCENT);
  });

  it("clareia cor saturada mas escura demais para servir de acento", () => {
    // um vermelho muito escuro nao brilha no fundo preto; precisa subir
    const cor = dominantAccent(pixels([40, 4, 4], [40, 4, 4]));
    const [r] = cor.match(/\d+/g)!.map(Number);
    expect(r).toBeGreaterThan(40);
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd ui && npx vitest run src/accent.test.ts`
Expected: FAIL — não resolve `./accent`

- [ ] **Step 3: Implementar**

```typescript
// ui/src/accent.ts
/**
 * Cor de acento da interface, extraida do poster em exibicao.
 *
 * Preto e branco sao descartados de proposito: posters psicodelicos tem muito
 * dos dois, e nenhum dos dois diz nada sobre a identidade do preset. O que
 * identifica e o matiz saturado.
 */

export const FALLBACK_ACCENT = "rgb(184, 164, 255)";

const MIN_SATURATION = 0.25;
const MIN_LUMA = 0.06;
const MAX_LUMA = 0.94;
/** Abaixo disto a cor nao brilha o bastante contra o fundo preto. */
const TARGET_MIN_LUMA = 0.32;

function luma(r: number, g: number, b: number): number {
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
}

function saturation(r: number, g: number, b: number): number {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  return max === 0 ? 0 : (max - min) / max;
}

/**
 * Media dos pixels saturados de um bloco RGBA, clareada se necessario.
 *
 * Recebe o formato cru de CanvasRenderingContext2D.getImageData().data.
 */
export function dominantAccent(data: Uint8ClampedArray): string {
  let somaR = 0;
  let somaG = 0;
  let somaB = 0;
  let contados = 0;

  for (let i = 0; i + 3 < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const l = luma(r, g, b);
    if (l < MIN_LUMA || l > MAX_LUMA) continue;
    if (saturation(r, g, b) < MIN_SATURATION) continue;
    somaR += r;
    somaG += g;
    somaB += b;
    contados += 1;
  }

  if (contados === 0) return FALLBACK_ACCENT;

  let r = Math.round(somaR / contados);
  let g = Math.round(somaG / contados);
  let b = Math.round(somaB / contados);

  const atual = luma(r, g, b);
  if (atual < TARGET_MIN_LUMA && atual > 0) {
    const ganho = TARGET_MIN_LUMA / atual;
    r = Math.min(255, Math.round(r * ganho));
    g = Math.min(255, Math.round(g * ganho));
    b = Math.min(255, Math.round(b * ganho));
  }

  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * Le o poster de uma URL e devolve seu acento.
 *
 * Amostra numa area pequena de proposito: 32x18 e resolucao mais que
 * suficiente para media de cor, e evita alocar o bitmap inteiro.
 */
export async function accentFromImage(url: string): Promise<string> {
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.src = url;
  try {
    await img.decode();
  } catch {
    return FALLBACK_ACCENT;
  }
  const canvas = document.createElement("canvas");
  canvas.width = 32;
  canvas.height = 18;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return FALLBACK_ACCENT;
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return dominantAccent(ctx.getImageData(0, 0, canvas.width, canvas.height).data);
}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd ui && npx vitest run src/accent.test.ts`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add ui/src/accent.ts ui/src/accent.test.ts
git commit -m "feat(ui): acento extraido do poster em exibicao"
```

---

### Task 3: Favoritos

**Files:**
- Create: `ui/src/useFavorites.ts`
- Test: `ui/src/useFavorites.test.ts`

- [ ] **Step 1: Escrever o teste que falha**

```typescript
// ui/src/useFavorites.test.ts
import { beforeEach, describe, expect, it } from "vitest";
import { STORAGE_KEY, readFavorites, toggleFavorite, writeFavorites } from "./useFavorites";

beforeEach(() => localStorage.clear());

describe("favoritos", () => {
  it("comeca vazio", () => {
    expect(readFavorites()).toEqual([]);
  });

  it("guarda e le de volta", () => {
    writeFavorites([3, 1, 2]);
    expect(readFavorites()).toEqual([3, 1, 2]);
  });

  it("alterna acrescentando no inicio, para o mais recente aparecer primeiro", () => {
    expect(toggleFavorite([2], 5)).toEqual([5, 2]);
  });

  it("alterna removendo quando ja existe", () => {
    expect(toggleFavorite([5, 2], 5)).toEqual([2]);
  });

  it("nao duplica", () => {
    expect(toggleFavorite(toggleFavorite([], 7), 7)).toEqual([]);
  });

  it("sobrevive a conteudo corrompido no storage", () => {
    localStorage.setItem(STORAGE_KEY, "{isto nao e json");
    expect(readFavorites()).toEqual([]);
  });

  it("descarta conteudo que nao e lista de numeros", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(["a", null, 3]));
    expect(readFavorites()).toEqual([3]);
  });
});
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd ui && npx vitest run src/useFavorites.test.ts`
Expected: FAIL — não resolve `./useFavorites`

- [ ] **Step 3: Implementar**

```typescript
// ui/src/useFavorites.ts
/**
 * Favoritos por aparelho.
 *
 * Ficam em localStorage de proposito: e preferencia do aparelho, nao dado
 * compartilhado. O celular e o monitor podem ter listas diferentes, e isso
 * esta certo.
 */
import { useCallback, useEffect, useState } from "react";

export const STORAGE_KEY = "chromesthesia.favorites";

/** Le a lista, tolerando storage corrompido ou de versao antiga. */
export function readFavorites(): number[] {
  try {
    const cru = localStorage.getItem(STORAGE_KEY);
    if (!cru) return [];
    const parsed: unknown = JSON.parse(cru);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is number => typeof x === "number");
  } catch {
    return [];
  }
}

export function writeFavorites(ids: number[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // storage cheio ou bloqueado: favoritos sao conveniencia, nao travam nada
  }
}

/** Acrescenta no inicio ou remove. O mais recente aparece primeiro. */
export function toggleFavorite(ids: number[], id: number): number[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [id, ...ids];
}

export function useFavorites() {
  const [ids, setIds] = useState<number[]>(readFavorites);

  useEffect(() => writeFavorites(ids), [ids]);

  const toggle = useCallback((id: number) => {
    setIds((atual) => toggleFavorite(atual, id));
  }, []);

  return { favorites: ids, toggle, isFavorite: (id: number) => ids.includes(id) };
}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd ui && npx vitest run src/useFavorites.test.ts`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add ui/src/useFavorites.ts ui/src/useFavorites.test.ts
git commit -m "feat(ui): favoritos por aparelho em localStorage"
```

---

### Task 4: Estado do motor pelo WebSocket

**Files:**
- Create: `ui/src/useEngineState.ts`

- [ ] **Step 1: Implementar**

```typescript
// ui/src/useEngineState.ts
/**
 * Assina o WebSocket do motor.
 *
 * O preset em exibicao vem daqui, nao de otimismo local depois de um clique:
 * o motor e a fonte da verdade, e ele pode trocar de preset por conta propria.
 * Reconecta sozinho porque o celular suspende a aba o tempo todo.
 */
import { useEffect, useRef, useState } from "react";
import type { EngineState } from "./api";

const RECONNECT_MS = 2000;

const VAZIO: EngineState = {
  preset_path: "", preset_name: "", fps: 0,
  audio_peak: 0, audio_connected: false, frame: 0,
};

export function useEngineState(): { state: EngineState; connected: boolean } {
  const [state, setState] = useState<EngineState>(VAZIO);
  const [connected, setConnected] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let descartado = false;

    const abrir = () => {
      if (descartado) return;
      const protocolo = location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocolo}//${location.host}/ws`);

      socket.onopen = () => setConnected(true);
      socket.onmessage = (evento) => {
        const dados = JSON.parse(evento.data);
        if (dados.type === "state") setState(dados as EngineState);
      };
      socket.onclose = () => {
        setConnected(false);
        if (!descartado) timer.current = window.setTimeout(abrir, RECONNECT_MS);
      };
      socket.onerror = () => socket?.close();
    };

    abrir();
    return () => {
      descartado = true;
      window.clearTimeout(timer.current);
      socket?.close();
    };
  }, []);

  return { state, connected };
}
```

- [ ] **Step 2: Conferir que compila**

Run: `cd ui && npx tsc --noEmit`
Expected: sem erro

- [ ] **Step 3: Commit**

```bash
git add ui/src/useEngineState.ts
git commit -m "feat(ui): estado do motor pelo WebSocket, com reconexao"
```

---

### Task 5: Tokens e tipografia

**Files:**
- Create: `ui/src/styles.css`
- Modify: `ui/index.html`

- [ ] **Step 1: Escrever os tokens**

```css
/* ui/src/styles.css */

/*
 * Camara escura. Os posters sao a unica fonte de luz da tela, entao o cromo
 * recua: sem moldura, sem sombra, sem gradiente decorativo. Qualquer um dos
 * tres viraria ruido disputando atencao com dezenas de miniaturas saturadas.
 *
 * --accent e injetada em tempo de execucao a partir do poster em exibicao.
 */
:root {
  --ground: #08070a;
  --ground-lift: #100e15;
  --rule: #201d28;
  --ink: #e9e5f0;
  --ink-dim: #78718a;
  --ink-faint: #433d52;

  --accent: rgb(184, 164, 255);

  --step: 0.5rem;
  --gutter: calc(var(--step) * 1.5);
  --tap: 44px;

  --font-display: "Fraunces", Georgia, serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;

  color-scheme: dark;
}

* { box-sizing: border-box; }

html, body, #root { height: 100%; }

body {
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
  overscroll-behavior: none;
}

/* Tipografia de duas vozes: serifada so para nomes proprios, mono para dados. */
.display {
  font-family: var(--font-display);
  font-optical-sizing: auto;
  font-weight: 400;
  letter-spacing: -0.01em;
}

.label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-dim);
}

/* O acento so aparece onde significa algo: foco, selecao, o preset em exibicao. */
.accent { color: var(--accent); }

:focus-visible {
  outline: 1px solid var(--accent);
  outline-offset: 2px;
}

button {
  font: inherit;
  color: inherit;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  min-height: var(--tap);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 2: Carregar as fontes e ajustar o HTML**

```html
<!-- ui/index.html -->
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="theme-color" content="#08070a" />
    <title>Chromesthesia</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..600&family=IBM+Plex+Mono:wght@400;500&display=swap"
      rel="stylesheet"
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Importar o CSS no ponto de entrada**

```typescript
// ui/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/styles.css ui/index.html ui/src/main.tsx
git commit -m "feat(ui): tokens da camara escura e tipografia de duas vozes"
```

---

### Task 6: Poster e grid

**Files:**
- Create: `ui/src/components/PosterTile.tsx`, `ui/src/components/PosterGrid.tsx`

- [ ] **Step 1: Implementar o poster**

```tsx
// ui/src/components/PosterTile.tsx
/**
 * Um poster no grid. Sem moldura, sem sombra: e so a imagem.
 *
 * O nome fica escondido ate o foco ou o ponteiro chegar. Num grid de dezenas,
 * texto permanente sob cada miniatura vira uma parede cinza que compete com
 * exatamente aquilo que o usuario esta tentando comparar.
 */
import { memo } from "react";
import { posterUrl, type Preset } from "../api";

interface Props {
  preset: Preset;
  playing: boolean;
  favorite: boolean;
  onLoad: (id: number) => void;
  onToggleFavorite: (id: number) => void;
}

function PosterTileBase({ preset, playing, favorite, onLoad, onToggleFavorite }: Props) {
  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => onLoad(preset.id)}
        title={preset.name}
        aria-label={`Exibir ${preset.name}`}
        style={{
          display: "block",
          width: "100%",
          aspectRatio: "16 / 9",
          padding: 0,
          overflow: "hidden",
          background: "var(--ground-lift)",
          outline: playing ? "2px solid var(--accent)" : "none",
          outlineOffset: "1px",
        }}
      >
        {preset.has_poster ? (
          <img
            src={posterUrl(preset.id)}
            alt=""
            loading="lazy"
            decoding="async"
            style={{
              width: "100%", height: "100%", objectFit: "cover", display: "block",
              opacity: playing ? 1 : 0.86,
              transition: "opacity 180ms ease",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.opacity = "1"; }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = playing ? "1" : "0.86";
            }}
          />
        ) : (
          <span className="label" style={{ opacity: 0.5 }}>sem poster</span>
        )}
      </button>

      <button
        onClick={() => onToggleFavorite(preset.id)}
        aria-label={favorite ? `Desmarcar ${preset.name}` : `Favoritar ${preset.name}`}
        aria-pressed={favorite}
        style={{
          position: "absolute", top: 0, right: 0,
          width: "var(--tap)", minHeight: "var(--tap)",
          color: favorite ? "var(--accent)" : "var(--ink-faint)",
          fontSize: "14px", lineHeight: 1,
        }}
      >
        {favorite ? "◆" : "◇"}
      </button>
    </div>
  );
}

export const PosterTile = memo(PosterTileBase);
```

- [ ] **Step 2: Implementar o grid**

```tsx
// ui/src/components/PosterGrid.tsx
/**
 * Grid de posters com paginacao por rolagem.
 *
 * Nunca renderiza os 9.795 de uma vez: pagina de 60 em 60 e carrega a proxima
 * quando uma sentinela entra no viewport. O atributo loading="lazy" de cada
 * imagem cuida do resto - nao ha necessidade de virtualizacao manual enquanto
 * a pagina for desse tamanho.
 */
import { useEffect, useRef } from "react";
import type { Preset } from "../api";
import { PosterTile } from "./PosterTile";

interface Props {
  presets: Preset[];
  total: number;
  playingName: string;
  isFavorite: (id: number) => boolean;
  onLoad: (id: number) => void;
  onToggleFavorite: (id: number) => void;
  onReachEnd: () => void;
}

export function PosterGrid({
  presets, total, playingName, isFavorite, onLoad, onToggleFavorite, onReachEnd,
}: Props) {
  const sentinela = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const alvo = sentinela.current;
    if (!alvo) return;
    const observer = new IntersectionObserver(
      (entradas) => { if (entradas[0].isIntersecting) onReachEnd(); },
      { rootMargin: "600px" },
    );
    observer.observe(alvo);
    return () => observer.disconnect();
  }, [onReachEnd]);

  if (presets.length === 0) {
    return <p className="label" style={{ padding: "var(--gutter)" }}>nenhum preset aqui</p>;
  }

  return (
    <>
      <div
        style={{
          display: "grid",
          gap: "var(--gutter)",
          gridTemplateColumns: "repeat(auto-fill, minmax(min(160px, 45vw), 1fr))",
          padding: "var(--gutter)",
        }}
      >
        {presets.map((preset) => (
          <PosterTile
            key={preset.id}
            preset={preset}
            playing={preset.name === playingName}
            favorite={isFavorite(preset.id)}
            onLoad={onLoad}
            onToggleFavorite={onToggleFavorite}
          />
        ))}
      </div>
      <div ref={sentinela} style={{ height: 1 }} />
      <p className="label" style={{ textAlign: "center", padding: "var(--gutter)" }}>
        {presets.length} de {total}
      </p>
    </>
  );
}
```

- [ ] **Step 3: Conferir que compila**

Run: `cd ui && npx tsc --noEmit`
Expected: sem erro

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/PosterTile.tsx ui/src/components/PosterGrid.tsx
git commit -m "feat(ui): grid de posters sem moldura, paginado por rolagem"
```

---

### Task 7: Navegação por família

**Files:**
- Create: `ui/src/components/FamilyRail.tsx`

- [ ] **Step 1: Implementar**

```tsx
// ui/src/components/FamilyRail.tsx
/**
 * Navegacao familia -> subfamilia.
 *
 * Trilho horizontal rolavel no celular, coluna no monitor. A contagem fica
 * visivel porque saber que "Reaction" tem 1791 e "Hypnotic" tem 280 muda a
 * decisao de por onde comecar.
 */
import type { Family, Subfamily } from "../api";

interface Props {
  families: Family[];
  subfamilies: Subfamily[];
  selectedFamily: string | null;
  selectedSubfamily: string | null;
  onSelectFamily: (family: string | null) => void;
  onSelectSubfamily: (subfamily: string | null) => void;
}

function Chip({ label, count, active, onClick }: {
  label: string; count?: number; active: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      style={{
        padding: "0 calc(var(--step) * 1.5)",
        whiteSpace: "nowrap",
        color: active ? "var(--ground)" : "var(--ink-dim)",
        background: active ? "var(--accent)" : "transparent",
        borderBottom: active ? "none" : "1px solid var(--rule)",
        letterSpacing: "0.08em",
        fontSize: "11px",
        textTransform: "uppercase",
      }}
    >
      {label}
      {count !== undefined && (
        <span style={{ opacity: 0.55, marginLeft: "var(--step)" }}>{count}</span>
      )}
    </button>
  );
}

export function FamilyRail({
  families, subfamilies, selectedFamily, selectedSubfamily,
  onSelectFamily, onSelectSubfamily,
}: Props) {
  return (
    <nav style={{ borderBottom: "1px solid var(--rule)" }}>
      <div style={{
        display: "flex", gap: "var(--step)", overflowX: "auto",
        padding: "var(--step) var(--gutter)", scrollbarWidth: "none",
      }}>
        <Chip label="tudo" active={selectedFamily === null}
              onClick={() => { onSelectFamily(null); onSelectSubfamily(null); }} />
        {families.map((f) => (
          <Chip key={f.family} label={f.family} count={f.count}
                active={f.family === selectedFamily}
                onClick={() => { onSelectFamily(f.family); onSelectSubfamily(null); }} />
        ))}
      </div>

      {selectedFamily && subfamilies.length > 0 && (
        <div style={{
          display: "flex", gap: "var(--step)", overflowX: "auto",
          padding: "0 var(--gutter) var(--step)", scrollbarWidth: "none",
          borderTop: "1px solid var(--rule)",
        }}>
          <Chip label="toda a familia" active={selectedSubfamily === null}
                onClick={() => onSelectSubfamily(null)} />
          {subfamilies.filter((s) => s.subfamily !== "").map((s) => (
            <Chip key={s.subfamily} label={s.subfamily} count={s.count}
                  active={s.subfamily === selectedSubfamily}
                  onClick={() => onSelectSubfamily(s.subfamily)} />
          ))}
        </div>
      )}
    </nav>
  );
}
```

- [ ] **Step 2: Conferir que compila**

Run: `cd ui && npx tsc --noEmit`
Expected: sem erro

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/FamilyRail.tsx
git commit -m "feat(ui): navegacao familia e subfamilia com contagem visivel"
```

---

### Task 8: O preset em exibição

**Files:**
- Create: `ui/src/components/NowPlaying.tsx`

Este é o elemento que quebra o grid: o preset em exibição não é mais uma célula, é o cabeçalho.

- [ ] **Step 1: Implementar**

```tsx
// ui/src/components/NowPlaying.tsx
/**
 * O preset em exibicao, fora do grid.
 *
 * E o unico lugar onde a tipografia serifada aparece, e o unico lugar com
 * cor saturada. Quebrar o grid aqui e proposital: no escuro, com o olhar na
 * TV, precisa haver um ponto na tela que se distingue sem ser lido.
 *
 * A barra de audio pulsa com o pico real do sinal - e como se ve, de relance,
 * que o motor esta vivo e ouvindo.
 */
import type { EngineState } from "../api";

interface Props {
  state: EngineState;
  connected: boolean;
  onShowSimilar: () => void;
  canShowSimilar: boolean;
}

export function NowPlaying({ state, connected, onShowSimilar, canShowSimilar }: Props) {
  const nome = state.preset_name || (connected ? "nada carregado" : "motor offline");
  const pico = Math.min(1, state.audio_peak * 6);

  return (
    <header style={{
      padding: "calc(var(--step) * 2) var(--gutter)",
      borderBottom: "1px solid var(--rule)",
      background: `linear-gradient(180deg,
        color-mix(in oklab, var(--accent) 7%, var(--ground)) 0%,
        var(--ground) 100%)`,
      transition: "background 700ms ease",
    }}>
      <div className="label">
        {connected ? `${state.fps.toFixed(0)} fps` : "sem conexao"}
        {state.audio_connected ? "" : " · sem audio"}
      </div>

      <h1 className="display accent" style={{
        margin: "var(--step) 0",
        fontSize: "clamp(20px, 5vw, 34px)",
        fontWeight: 400,
        lineHeight: 1.1,
        wordBreak: "break-word",
      }}>
        {nome}
      </h1>

      <div style={{ display: "flex", alignItems: "center", gap: "var(--gutter)" }}>
        <div
          aria-hidden
          style={{
            flex: 1, height: "2px", background: "var(--rule)", position: "relative",
          }}
        >
          <div style={{
            position: "absolute", inset: 0, width: `${pico * 100}%`,
            background: "var(--accent)", transition: "width 120ms linear",
          }} />
        </div>

        {canShowSimilar && (
          <button onClick={onShowSimilar} className="label"
                  style={{ color: "var(--accent)" }}>
            mais assim
          </button>
        )}
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Conferir que compila**

Run: `cd ui && npx tsc --noEmit`
Expected: sem erro

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/NowPlaying.tsx
git commit -m "feat(ui): preset em exibicao quebrando o grid, com pulso de audio"
```

---

### Task 9: Composição

**Files:**
- Create: `ui/src/App.tsx`

- [ ] **Step 1: Implementar**

```tsx
// ui/src/App.tsx
/**
 * Composicao da interface.
 *
 * O preset em exibicao vem do WebSocket, nunca de otimismo local: o motor
 * pode trocar por conta propria e a tela precisa refletir a realidade dele.
 */
import { useCallback, useEffect, useState } from "react";
import {
  fetchFamilies, fetchPresets, fetchSimilar, fetchSubfamilies, loadPreset,
  posterUrl, type Family, type Preset, type Subfamily,
} from "./api";
import { accentFromImage, FALLBACK_ACCENT } from "./accent";
import { useEngineState } from "./useEngineState";
import { useFavorites } from "./useFavorites";
import { FamilyRail } from "./components/FamilyRail";
import { NowPlaying } from "./components/NowPlaying";
import { PosterGrid } from "./components/PosterGrid";

const PAGE = 60;

export default function App() {
  const { state, connected } = useEngineState();
  const { toggle, isFavorite } = useFavorites();

  const [families, setFamilies] = useState<Family[]>([]);
  const [subfamilies, setSubfamilies] = useState<Subfamily[]>([]);
  const [family, setFamily] = useState<string | null>(null);
  const [subfamily, setSubfamily] = useState<string | null>(null);

  const [presets, setPresets] = useState<Preset[]>([]);
  const [total, setTotal] = useState(0);
  const [similarOf, setSimilarOf] = useState<number | null>(null);

  useEffect(() => { void fetchFamilies().then(setFamilies); }, []);

  useEffect(() => {
    if (!family) { setSubfamilies([]); return; }
    void fetchSubfamilies(family).then(setSubfamilies);
  }, [family]);

  // Troca de filtro reinicia a listagem e sai do modo "mais assim".
  useEffect(() => {
    setSimilarOf(null);
    void fetchPresets({
      family: family ?? undefined,
      subfamily: subfamily ?? undefined,
      limit: PAGE, offset: 0,
    }).then((pagina) => { setPresets(pagina.items); setTotal(pagina.total); });
  }, [family, subfamily]);

  // O acento da interface vem do poster em exibicao.
  useEffect(() => {
    const atual = presets.find((p) => p.name === state.preset_name);
    const alvo = atual?.has_poster ? posterUrl(atual.id) : null;
    if (!alvo) {
      document.documentElement.style.setProperty("--accent", FALLBACK_ACCENT);
      return;
    }
    void accentFromImage(alvo).then((cor) => {
      document.documentElement.style.setProperty("--accent", cor);
    });
  }, [state.preset_name, presets]);

  const carregarMais = useCallback(() => {
    if (similarOf !== null || presets.length >= total) return;
    void fetchPresets({
      family: family ?? undefined,
      subfamily: subfamily ?? undefined,
      limit: PAGE, offset: presets.length,
    }).then((pagina) => setPresets((atual) => [...atual, ...pagina.items]));
  }, [family, subfamily, presets.length, total, similarOf]);

  const mostrarSimilares = useCallback(() => {
    const atual = presets.find((p) => p.name === state.preset_name);
    if (!atual) return;
    void fetchSimilar(atual.id, 24).then((vizinhos) => {
      setSimilarOf(atual.id);
      setPresets(vizinhos);
      setTotal(vizinhos.length);
    });
  }, [presets, state.preset_name]);

  const emExibicao = presets.some((p) => p.name === state.preset_name);

  return (
    <main style={{ display: "flex", flexDirection: "column", minHeight: "100%" }}>
      <NowPlaying
        state={state}
        connected={connected}
        onShowSimilar={mostrarSimilares}
        canShowSimilar={emExibicao && similarOf === null}
      />
      <FamilyRail
        families={families}
        subfamilies={subfamilies}
        selectedFamily={family}
        selectedSubfamily={subfamily}
        onSelectFamily={setFamily}
        onSelectSubfamily={setSubfamily}
      />
      {similarOf !== null && (
        <p className="label" style={{ padding: "var(--step) var(--gutter)" }}>
          vizinhos no espaco de features
        </p>
      )}
      <PosterGrid
        presets={presets}
        total={total}
        playingName={state.preset_name}
        isFavorite={isFavorite}
        onLoad={(id) => void loadPreset(id)}
        onToggleFavorite={toggle}
        onReachEnd={carregarMais}
      />
    </main>
  );
}
```

- [ ] **Step 2: Conferir que compila e que a suíte passa**

Run: `cd ui && npx tsc --noEmit && npx vitest run`
Expected: sem erro de tipo, 20 testes passando

- [ ] **Step 3: Commit**

```bash
git add ui/src/App.tsx
git commit -m "feat(ui): composicao da interface"
```

---

### Task 10: Servir pelo backend e validar

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Servir o build estático**

Acrescentar em `server/main.py`, dentro de `build_app`, **depois** dos dois `include_router` (a ordem importa: montar a raiz antes capturaria `/api`):

```python
    ui_dist = config.PROJECT_ROOT / "ui" / "dist"
    if ui_dist.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
```

- [ ] **Step 2: Construir a interface**

Run: `cd /c/Users/Jordh/chromesthesia/ui && npm run build`
Expected: gera `ui/dist/` sem erro

- [ ] **Step 3: Subir o motor e abrir no navegador**

Run, **num terminal de verdade** (não em segundo plano — o processo morre sem console):
```
python -m engine.app
```
Abrir `http://127.0.0.1:8765/` no navegador.

Expected: a interface carrega, mostra o preset em exibição no topo, os chips de família com as contagens (Reaction 1791, Fractal 1354, …) e o grid de posters.

- [ ] **Step 4: Validar o laço completo**

1. Clicar num poster → a janela do visualizador troca de preset
2. O cabeçalho atualiza com o novo nome, vindo do WebSocket, não do clique
3. A cor de acento da interface muda junto com o poster
4. Rolar até o fim → carrega a próxima página
5. Clicar "mais assim" → o grid vira os vizinhos
6. Favoritar, recarregar a página → o favorito persiste

- [ ] **Step 5: Validar no celular**

Abrir `http://192.168.0.226:8765/` no celular, na mesma rede.

Expected: duas colunas de posters, chips roláveis na horizontal, tocar num poster troca o preset na TV.

Se não carregar, é o Firewall — num PowerShell como administrador:
```
netsh advfirewall firewall add rule name="Chromesthesia" dir=in action=allow protocol=TCP localport=8765
```
VPN ligada também quebra o alcance da rede local.

- [ ] **Step 6: Commit**

```bash
git add server/main.py
git commit -m "feat(server): servir o build da interface"
```

---

## Feito quando

- `npx vitest run` passa em `ui/`
- `npx tsc --noEmit` sem erro
- A interface abre em `http://127.0.0.1:8765/` e no celular
- Tocar num poster troca o preset na tela do visualizador
- O acento da interface acompanha o poster em exibição
- Favoritos sobrevivem a recarregar a página

## O que fica para depois, e por quê

**Previews animados.** Exigem contexto OpenGL próprio — o do motor está ocupado — logo, subprocesso com ~3s de latência, ou 2,4 GB pré-gerados. Só vale se navegar por imagem parada se mostrar insuficiente na prática.

**Deduplicação do "mais assim".** O pacote tem variantes quase idênticas do mesmo preset, e elas aparecem juntas nos vizinhos. Resolver exige hash perceptual dos posters. Medir primeiro o quanto incomoda.

**Fase 2.** O pad de emoção valência × ativação + densidade entra aqui, consumindo o mesmo índice e os mesmos endpoints.
