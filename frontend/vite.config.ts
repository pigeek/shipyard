import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The SPA is served same-origin by FastAPI under /app (ADR 0001). `base` makes
// asset URLs absolute under /app/; the bundle is emitted into app/web/spa so the
// backend can serve it (and the Docker image can include it).
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  build: {
    outDir: "../app/web/spa",
    emptyOutDir: true,
  },
  server: {
    // `npm run dev` against a locally-running API (separate origin → see CORS,
    // ADR 0001 Phase 7.5). Cookies ride along thanks to allow-credentials.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/auth": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
