import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built files are served by FastAPI (server/app.py) from web/dist, with assets under /assets/.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: { outDir: "dist", assetsDir: "assets", emptyOutDir: true, chunkSizeWarningLimit: 900 },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8080", changeOrigin: true } },
  },
});
