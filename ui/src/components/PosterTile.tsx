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
