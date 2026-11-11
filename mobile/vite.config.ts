import { defineConfig } from "vite";

// base: './' — GitHub Pages 처럼 하위 경로(/ultron/)에 올려도 그대로 동작하게
export default defineConfig({
  base: "./",
  build: { target: "es2022", sourcemap: false },
  test: { include: ["tests/**/*.test.ts"] },
} as any);
