// ui/src/accent.ts
/**
 * Cor de acento da interface, extraida do poster em exibicao.
 *
 * Preto e branco sao descartados de proposito: posters psicodelicos tem muito
 * dos dois, e nenhum dos dois diz nada sobre a identidade do preset. O que
 * identifica e o matiz saturado.
 *
 * Escolher a cor e torna-la legivel sao responsabilidades separadas de
 * proposito, em duas funcoes. Testar as duas coisas numa funcao so faz o
 * teste de escolha assertar valores RGB exatos para cores cuja luma cai
 * numa faixa qualquer - e forca o limiar de clareamento pra baixo ate esse
 * teste parar de reclamar. O limiar que passa no teste vira ilegivel na
 * tela: medido contra o corpus real, um limiar de 0.22 (que passava nos
 * testes antigos) deixava 4 em 14 posters com acento entre luma 0.22 e 0.24 -
 * tecnicamente "clareado", na pratica quase preto sobre fundo quase preto.
 */

export const FALLBACK_ACCENT = "rgb(184, 164, 255)";

const MIN_SATURATION = 0.25;
/**
 * Abaixo disto o pixel e tratado como preto de fundo e descartado da escolha.
 *
 * Precisa ficar abaixo da luma de um vermelho escuro mas saturado (ex.:
 * rgb(40, 4, 4) tem luma ~0.046) - esse pixel carrega matiz de verdade e
 * precisa entrar na media. Se ele ficar ilegivel depois de escolhido e
 * problema de `liftForDarkGround`, nao motivo pra descartar na escolha.
 */
const MIN_LUMA = 0.03;
const MAX_LUMA = 0.94;

/**
 * Luma minima pra um acento servir na interface: e usado como texto grande
 * sobre o fundo #08070a (luma ~0.03) e como fundo de chip com texto escuro
 * por cima, e nenhum dos dois funciona abaixo de ~0.45. Medido contra o
 * corpus real: um limiar de 0.22 deixava 4 em 14 posters ilegiveis.
 */
const TARGET_MIN_LUMA = 0.45;

function luma(r: number, g: number, b: number): number {
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
}

function saturation(r: number, g: number, b: number): number {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  return max === 0 ? 0 : (max - min) / max;
}

/**
 * Media dos pixels saturados de um bloco RGBA. So escolhe a cor - nao
 * clareia. Legibilidade e responsabilidade de `liftForDarkGround`, chamada
 * depois pelo lado de quem consome a cor escolhida.
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

  const r = Math.round(somaR / contados);
  const g = Math.round(somaG / contados);
  const b = Math.round(somaB / contados);

  return `rgb(${r}, ${g}, ${b})`;
}

function aplicarGanho(r: number, g: number, b: number, ganho: number): [number, number, number] {
  return [Math.min(255, r * ganho), Math.min(255, g * ganho), Math.min(255, b * ganho)];
}

/**
 * Escala uma cor "rgb(r, g, b)" proporcionalmente ate atingir TARGET_MIN_LUMA,
 * preservando a proporcao entre canais - um vermelho escuro continua
 * vermelho, nao vira cinza. Cor ja clara o bastante passa intacta.
 *
 * Nao usa um "ganho = alvo / luma atual" multiplicado direto num passo so:
 * quando um canal ja esta perto do teto de 255, esse ganho unico trava o
 * canal no teto sem levantar a luma quase nada. Isso aconteceu de verdade
 * num poster do corpus - rgb(254, 1, 255), magenta quase puro com luma 0.29:
 * R e B ja quase no teto, G quase zero. O ganho de um passo so (0.45 / 0.29
 * =~ 1.55) so leva G de 1 pra 2 e trava R e B em 255 - luma final continua
 * ~0.29, ilegivel do mesmo jeito. A busca binaria acha o ganho certo mesmo
 * quando alguns canais travam antes de outros: quem trava para de crescer,
 * o resto continua subindo ate a luma alcancar o alvo.
 */
export function liftForDarkGround(cor: string): string {
  const canais = cor.match(/\d+/g);
  if (!canais) return cor;
  const [r, g, b] = canais.map(Number);

  if (r === 0 && g === 0 && b === 0) return cor; // preto puro: nada pra escalar

  if (luma(r, g, b) >= TARGET_MIN_LUMA) return cor;

  let lo = 1;
  let hi = 255; // ganho que garante qualquer canal com valor minimo util (1) no teto
  for (let i = 0; i < 24; i++) {
    const meio = (lo + hi) / 2;
    const [cr, cg, cb] = aplicarGanho(r, g, b, meio);
    if (luma(cr, cg, cb) < TARGET_MIN_LUMA) lo = meio;
    else hi = meio;
  }

  const [fr, fg, fb] = aplicarGanho(r, g, b, hi);
  return `rgb(${Math.round(fr)}, ${Math.round(fg)}, ${Math.round(fb)})`;
}

/**
 * Le o poster de uma URL e devolve seu acento: escolhe a cor dominante e
 * depois levanta se ela estiver escura demais pro fundo.
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
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  return liftForDarkGround(dominantAccent(data));
}
