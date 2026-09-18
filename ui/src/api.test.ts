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
