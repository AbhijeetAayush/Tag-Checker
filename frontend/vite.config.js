import { defineConfig } from "vite";

export default defineConfig({
  // Root-relative assets (correct for Vercel and normal static hosts)
  base: "/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
