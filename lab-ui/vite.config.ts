import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "/lab/",
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 4000,
  },
  worker: { format: "es" },
  test: {
    include: ["tests/unit/**/*.test.ts"],
    environment: "node",
  },
});
