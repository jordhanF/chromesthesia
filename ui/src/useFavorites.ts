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
