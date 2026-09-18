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
