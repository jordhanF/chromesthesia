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
/**
 * Abaixo disto o pixel e tratado como preto de fundo e descartado.
 *
 * Precisa ficar abaixo da luma de um vermelho escuro mas saturado (ex.:
 * rgb(40, 4, 4) tem luma ~0.046) - esse pixel deve ser clareado, nao
 * descartado como se fosse so ruido preto.
 */
const MIN_LUMA = 0.03;
const MAX_LUMA = 0.94;
/**
 * Abaixo disto a cor nao brilha o bastante contra o fundo preto e e clareada.
 *
 * Precisa ficar abaixo da luma de cores ja saturadas e razoavelmente visiveis
 * (ex.: rgb(220, 20, 60) tem luma ~0.257, rgb(90, 60, 200) tem luma ~0.300) -
 * senao o clareamento acaba estourando uma cor que ja estava boa.
 */
const TARGET_MIN_LUMA = 0.22;

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
