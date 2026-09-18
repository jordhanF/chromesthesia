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
