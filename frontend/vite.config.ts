import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/v2': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/v3': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/v4': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      // Added with the /v5/adviser/* API (PR #14) -- every adviser chat
      // request 404'd at the Vite dev server itself (never reached the
      // backend, which serves it fine) until this was added.
      '/v5': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    target: 'esnext',
    minify: 'esbuild',
    sourcemap: true,
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
});
