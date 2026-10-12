import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const apiPort = process.env.STUDIO_API_PORT || "8787";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: Number(process.env.STUDIO_UI_PORT || 5173),
    proxy: {
      "/api": `http://127.0.0.1:${apiPort}`,
    },
  },
});
