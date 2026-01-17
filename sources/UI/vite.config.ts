import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { nodePolyfills } from 'vite-plugin-node-polyfills'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxyTarget =
    env.VITE_API_PROXY_TARGET ||
    (env.VITE_API_URL && env.VITE_API_URL.startsWith('http')
      ? env.VITE_API_URL
      : '') ||
    'http://localhost:8000';

  return {
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
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
    define: {
      global: 'globalThis',
      // Don't override VITE_API_URL - let it use the environment variable or default
      'import.meta.env.VITE_API_KEY': JSON.stringify('test-api-key-12345'),
    },
  };
});
