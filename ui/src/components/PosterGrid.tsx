// ui/src/components/PosterGrid.tsx
/**
 * Grid de posters com paginacao por rolagem.
 *
 * Nunca renderiza os 9.795 de uma vez: pagina de 60 em 60 e carrega a proxima
 * quando uma sentinela entra no viewport. O atributo loading="lazy" de cada
 * imagem cuida do resto - nao ha necessidade de virtualizacao manual enquanto
 * a pagina for desse tamanho.
 */
import { useEffect, useRef } from "react";
import type { Preset } from "../api";
import { PosterTile } from "./PosterTile";

interface Props {
  presets: Preset[];
  total: number;
  playingName: string;
  isFavorite: (id: number) => boolean;
  onLoad: (id: number) => void;
  onToggleFavorite: (id: number) => void;
  onReachEnd: () => void;
}

export function PosterGrid({
  presets, total, playingName, isFavorite, onLoad, onToggleFavorite, onReachEnd,
}: Props) {
  const sentinela = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const alvo = sentinela.current;
    if (!alvo) return;
    const observer = new IntersectionObserver(
      (entradas) => { if (entradas[0].isIntersecting) onReachEnd(); },
      { rootMargin: "600px" },
    );
    observer.observe(alvo);
    return () => observer.disconnect();
  }, [onReachEnd]);

  if (presets.length === 0) {
    return <p className="label" style={{ padding: "var(--gutter)" }}>nenhum preset aqui</p>;
  }

  return (
    <>
      <div
        style={{
          display: "grid",
          gap: "var(--gutter)",
          gridTemplateColumns: "repeat(auto-fill, minmax(min(160px, 45vw), 1fr))",
          padding: "var(--gutter)",
        }}
      >
        {presets.map((preset) => (
          <PosterTile
            key={preset.id}
            preset={preset}
            playing={preset.name === playingName}
            favorite={isFavorite(preset.id)}
            onLoad={onLoad}
            onToggleFavorite={onToggleFavorite}
          />
        ))}
      </div>
      <div ref={sentinela} style={{ height: 1 }} />
      <p className="label" style={{ textAlign: "center", padding: "var(--gutter)" }}>
        {presets.length} de {total}
      </p>
    </>
  );
}
