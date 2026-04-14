import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

// Vite config for React frontend that can be built for web or dropped into the extension.
export default defineConfig({
  plugins: [react()],
  root: '.',
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        sidebar: resolve(__dirname, 'sidebar.html')
      }
    }
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  // Use relative paths for extension, but can work with '/' for web too
  base: process.env.EXTENSION_BUILD === 'true' ? './' : '/',
});


