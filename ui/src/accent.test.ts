// ui/src/accent.test.ts
import { describe, expect, it } from "vitest";
import { dominantAccent, FALLBACK_ACCENT, liftForDarkGround } from "./accent";

/** Monta um bloco RGBA como o que canvas.getImageData devolve. */
function pixels(...cores: Array<[number, number, number]>): Uint8ClampedArray {
  const out = new Uint8ClampedArray(cores.length * 4);
  cores.forEach(([r, g, b], i) => {
    out[i * 4] = r; out[i * 4 + 1] = g; out[i * 4 + 2] = b; out[i * 4 + 3] = 255;
  });
  return out;
}

/** Luma (BT.709) de uma string "rgb(r, g, b)", pra conferir legibilidade nos testes. */
function lumaOf(cor: string): number {
  const [r, g, b] = cor.match(/\d+/g)!.map(Number);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
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
});

describe("liftForDarkGround", () => {
  it("deixa intacta uma cor ja clara o bastante", () => {
    // luma ~0.76 - medido contra um poster real do corpus
    expect(liftForDarkGround("rgb(106, 219, 219)")).toBe("rgb(106, 219, 219)");
  });

  it("sobe uma cor escura ate o alvo de legibilidade", () => {
    // luma ~0.22 - o limiar antigo aceitava isso como "clareado o bastante";
    // o novo alvo (0.45) precisa deixar isso bem mais claro que o original.
    const cor = liftForDarkGround("rgb(79, 54, 13)");
    expect(lumaOf(cor)).toBeGreaterThanOrEqual(0.43);
  });

  it("nao gera divisao por zero para preto puro", () => {
    const cor = liftForDarkGround("rgb(0, 0, 0)");
    expect(cor).toBe("rgb(0, 0, 0)");
    expect(cor).not.toContain("NaN");
  });

  it("preserva a proporcao entre canais - vermelho escuro continua vermelho, nao vira cinza", () => {
    const [r, g, b] = liftForDarkGround("rgb(79, 54, 13)").match(/\d+/g)!.map(Number);
    expect(r).toBeGreaterThan(g);
    expect(g).toBeGreaterThan(b);
    // razao entre o canal mais forte e o mais fraco fica perto da original (79/13 ~ 6.1),
    // nao colapsa pra perto de 1 (o que indicaria que a cor virou cinza)
    expect(r / b).toBeGreaterThan(4);
    expect(r / b).toBeLessThan(8);
  });

  it("levanta a luma mesmo quando canais ja estao perto do teto e travam antes de outros", () => {
    // rgb(254, 1, 255), luma ~0.29, medido num poster real: R e B quase no teto de 255,
    // G quase zero. Um ganho de passo unico travaria R e B sem quase mexer em G.
    const cor = liftForDarkGround("rgb(254, 1, 255)");
    expect(lumaOf(cor)).toBeGreaterThanOrEqual(0.40);
  });
});
