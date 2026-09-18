/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // O backend da Fase 1b-1 roda em 8765. O proxy evita CORS em desenvolvimento
  // e mantem o mesmo caminho relativo que vale em producao, quando o FastAPI
  // serve o build estatico.
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/ws": { target: "ws://127.0.0.1:8765", ws: true },
    },
  },
  build: { outDir: "dist" },
  test: { environment: "jsdom", globals: true },
});
