import { defineConfig } from "vite";

export default defineConfig({
  plugins: [],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
          icons: ["lucide-react"]
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/login": "http://127.0.0.1:8000",
      // Hochgeladene Fotos liefert FastAPI unter /uploads/cards/... - sonst antwortet Vite darauf.
      "/uploads": "http://127.0.0.1:8000"
    }
  }
});
