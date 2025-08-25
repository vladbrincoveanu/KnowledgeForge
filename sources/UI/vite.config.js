import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { nodePolyfills } from 'vite-plugin-node-polyfills'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    nodePolyfills({
      // Whether to polyfill `global`
      globals: {
        Buffer: true,
        global: true,
        process: true,
      },
      // Whether to polyfill specific globals
      protocolImports: true,
    }),
  ],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  },
  define: {
    global: 'globalThis',
    'import.meta.env.VITE_API_URL': JSON.stringify('http://localhost:8000'),
    'import.meta.env.VITE_API_KEY': JSON.stringify('test-api-key-12345')
  }
})
