import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 后端服务地址（FastAPI 默认端口）；后端未配置 CORS，开发期统一由 Vite 代理转发
const BACKEND = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      "/auth": BACKEND,
      "/document": BACKEND,
      "/agent": BACKEND,
      "/conversation": BACKEND,
      "/health": BACKEND,
    },
  },
});
