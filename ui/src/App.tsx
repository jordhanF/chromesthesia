// ui/src/App.tsx
/**
 * Composicao da interface.
 *
 * O preset em exibicao vem do WebSocket, nunca de otimismo local: o motor
 * pode trocar por conta propria e a tela precisa refletir a realidade dele.
 */
import { useCallback, useEffect, useState } from "react";
import {
  fetchFamilies, fetchPresets, fetchSimilar, fetchSubfamilies, loadPreset,
  posterUrl, type Family, type Preset, type Subfamily,
} from "./api";
import { accentFromImage, FALLBACK_ACCENT } from "./accent";
import { useEngineState } from "./useEngineState";
import { useFavorites } from "./useFavorites";
import { FamilyRail } from "./components/FamilyRail";
import { NowPlaying } from "./components/NowPlaying";
import { PosterGrid } from "./components/PosterGrid";

const PAGE = 60;

export default function App() {
  const { state, connected } = useEngineState();
  const { toggle, isFavorite } = useFavorites();

  const [families, setFamilies] = useState<Family[]>([]);
  const [subfamilies, setSubfamilies] = useState<Subfamily[]>([]);
  const [family, setFamily] = useState<string | null>(null);
  const [subfamily, setSubfamily] = useState<string | null>(null);

  const [presets, setPresets] = useState<Preset[]>([]);
  const [total, setTotal] = useState(0);
  const [similarOf, setSimilarOf] = useState<number | null>(null);

  useEffect(() => { void fetchFamilies().then(setFamilies); }, []);

  useEffect(() => {
    if (!family) { setSubfamilies([]); return; }
    void fetchSubfamilies(family).then(setSubfamilies);
  }, [family]);

  // Troca de filtro reinicia a listagem e sai do modo "mais assim".
  useEffect(() => {
    setSimilarOf(null);
    void fetchPresets({
      family: family ?? undefined,
      subfamily: subfamily ?? undefined,
      limit: PAGE, offset: 0,
    }).then((pagina) => { setPresets(pagina.items); setTotal(pagina.total); });
  }, [family, subfamily]);

  // O acento da interface vem do poster em exibicao. Descarta a resposta se
  // o preset em exibicao ja tiver mudado de novo antes dela chegar - senao
  // um acento atrasado (rede lenta, imagem maior) pode sobrescrever por
  // cima do acento de um preset mais recente.
  useEffect(() => {
    let descartado = false;
    const atual = presets.find((p) => p.name === state.preset_name);
    const alvo = atual?.has_poster ? posterUrl(atual.id) : null;
    if (!alvo) {
      document.documentElement.style.setProperty("--accent", FALLBACK_ACCENT);
      return;
    }
    void accentFromImage(alvo).then((cor) => {
      if (!descartado) document.documentElement.style.setProperty("--accent", cor);
    });
    return () => { descartado = true; };
  }, [state.preset_name, presets]);

  const carregarMais = useCallback(() => {
    if (similarOf !== null || presets.length >= total) return;
    void fetchPresets({
      family: family ?? undefined,
      subfamily: subfamily ?? undefined,
      limit: PAGE, offset: presets.length,
    }).then((pagina) => setPresets((atual) => [...atual, ...pagina.items]));
  }, [family, subfamily, presets.length, total, similarOf]);

  const mostrarSimilares = useCallback(() => {
    const atual = presets.find((p) => p.name === state.preset_name);
    if (!atual) return;
    void fetchSimilar(atual.id, 24).then((vizinhos) => {
      setSimilarOf(atual.id);
      setPresets(vizinhos);
      setTotal(vizinhos.length);
    });
  }, [presets, state.preset_name]);

  const emExibicao = presets.some((p) => p.name === state.preset_name);

  return (
    <main style={{ display: "flex", flexDirection: "column", minHeight: "100%" }}>
      <NowPlaying
        state={state}
        connected={connected}
        onShowSimilar={mostrarSimilares}
        canShowSimilar={emExibicao && similarOf === null}
      />
      <FamilyRail
        families={families}
        subfamilies={subfamilies}
        selectedFamily={family}
        selectedSubfamily={subfamily}
        onSelectFamily={setFamily}
        onSelectSubfamily={setSubfamily}
      />
      {similarOf !== null && (
        <p className="label" style={{ padding: "var(--step) var(--gutter)" }}>
          vizinhos no espaco de features
        </p>
      )}
      <PosterGrid
        presets={presets}
        total={total}
        playingName={state.preset_name}
        isFavorite={isFavorite}
        onLoad={(id) => void loadPreset(id)}
        onToggleFavorite={toggle}
        onReachEnd={carregarMais}
      />
    </main>
  );
}
