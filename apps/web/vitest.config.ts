import { defineConfig } from "vitest/config";
import { resolve } from "path";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    exclude: ["e2e/**", "node_modules/**"],
    passWithNoTests: true,
  },
  resolve: {
    alias: {
      "@quant/shared": resolve(__dirname, "../shared/src"),
      "@core": resolve(__dirname, "src/core"),
      "@feat": resolve(__dirname, "src/features"),
      "@shared": resolve(__dirname, "src/shared"),
      "@test": resolve(__dirname, "src/test"),
    },
  },
});
