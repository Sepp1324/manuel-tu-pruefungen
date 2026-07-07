import { defineConfig } from "vite";

export default defineConfig({
  plugins: [],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/login": "http://127.0.0.1:8000"
    }
  }
});
