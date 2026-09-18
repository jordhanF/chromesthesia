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
