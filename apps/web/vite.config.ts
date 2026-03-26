import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  preview: {
    port: 4173,
  },
  build: {
    // Vendor chunk splitting — keep main bundle small
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-query": ["@tanstack/react-query"],
        },
      },
    },
    // Inline small assets (< 8KB)
    assetsInlineLimit: 8192,
    // Source maps off for production
    sourcemap: false,
    // Target modern browsers only
    target: "es2020",
  },
});
