import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  build: {
    modulePreload: {
      resolveDependencies: (_filename, dependencies) =>
        dependencies.filter((dependency) => !dependency.includes('motion-')),
    },
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/motion/') || id.includes('/node_modules/framer-motion/')) {
            return 'motion'
          }
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
