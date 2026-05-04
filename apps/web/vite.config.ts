import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

  // Resolve paths
  resolve: {
    alias: {
      "@": "/src",
    },
  },

  // Vitest configuration
  test: {
    globals: true,
    environment: "jsdom",
    // Run setup files before each test file
    setupFiles: ["./src/test/setup.ts", "./src/test/server.ts"],
    // Set jsdom URL so axios resolves relative baseURL correctly:
    // axios baseURL '/api/v1' → http://localhost/api/v1/...
    environmentOptions: {
      jsdom: { url: "http://localhost" },
    },
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/features/clients/**", "src/features/agenda/**"],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 75,
      },
    },
  },

  // Dev server configuration
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },

  // Preview server (for testing production build locally)
  preview: {
    port: 4173,
  },
});
