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
