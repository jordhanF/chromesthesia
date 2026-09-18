// ui/src/useEngineState.ts
/**
 * Assina o WebSocket do motor.
 *
 * O preset em exibicao vem daqui, nao de otimismo local depois de um clique:
 * o motor e a fonte da verdade, e ele pode trocar de preset por conta propria.
 * Reconecta sozinho porque o celular suspende a aba o tempo todo.
 */
import { useEffect, useRef, useState } from "react";
import type { EngineState } from "./api";

const RECONNECT_MS = 2000;

const VAZIO: EngineState = {
  preset_path: "", preset_name: "", fps: 0,
  audio_peak: 0, audio_connected: false, frame: 0,
};

export function useEngineState(): { state: EngineState; connected: boolean } {
  const [state, setState] = useState<EngineState>(VAZIO);
  const [connected, setConnected] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let descartado = false;

    const abrir = () => {
      if (descartado) return;
      const protocolo = location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocolo}//${location.host}/ws`);

      socket.onopen = () => setConnected(true);
      socket.onmessage = (evento) => {
        const dados = JSON.parse(evento.data);
        if (dados.type === "state") setState(dados as EngineState);
      };
      socket.onclose = () => {
        setConnected(false);
        if (!descartado) timer.current = window.setTimeout(abrir, RECONNECT_MS);
      };
      socket.onerror = () => socket?.close();
    };

    abrir();
    return () => {
      descartado = true;
      window.clearTimeout(timer.current);
      socket?.close();
    };
  }, []);

  return { state, connected };
}
