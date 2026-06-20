/**
 * Component/Module: vite.config
 * Path: frontend/vite.config.ts
 *
 * Descripcion:
 *   Configuracion de Vite para el frontend del TFG.
 *   El proxy /api redirige las peticiones al backend FastAPI en desarrollo
 *   evitando problemas de CORS sin modificar el codigo de produccion.
 *
 * Sprint: Sprint 3
 */
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
    },
  },
})
