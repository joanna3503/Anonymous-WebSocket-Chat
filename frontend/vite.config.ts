import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // GitHub Repo Name: Anonymous-WebSocket-Chat
  base: '/Anonymous-WebSocket-Chat/',
  test: {
    environment: 'jsdom',
    globals: true,
  },
});