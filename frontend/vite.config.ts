import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/mnp/",
  plugins: [react()],
  build: {
    outDir: "../mnp_frontend_dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/v1": "http://127.0.0.1:8099",
      "/admin": "http://127.0.0.1:8099",
      "/health": "http://127.0.0.1:8099",
    },
  },
});
