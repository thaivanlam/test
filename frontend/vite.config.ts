/// <reference types="vitest/config" />
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // Unit tests cover plain functions (schemas, query keys), so they run in
  // Node without a DOM.
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
})
