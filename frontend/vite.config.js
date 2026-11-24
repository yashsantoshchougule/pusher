import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 3000,
    open: false,
    proxy: {
      '/api': {
        target: process.env.PUSHER_DEV_API_ORIGIN || 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  }
});
