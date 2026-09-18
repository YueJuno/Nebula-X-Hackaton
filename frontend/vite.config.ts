import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      // Polling detects edits through Windows/Docker Desktop bind mounts.
      usePolling: true,
      interval: 300,
    },
  },
});
