import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build straight into the FastAPI app's static/ dir; relative base so the
// hashed assets resolve regardless of the mount path on Databricks Apps.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../static",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
