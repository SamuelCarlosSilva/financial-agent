import react from '@vitejs/plugin-react';
import { loadEnv, type ProxyOptions } from 'vite';
import { defineConfig } from 'vitest/config';

export default defineConfig(({ mode }) => {
  // Sem prefixo VITE_: estas variáveis ficam só no servidor e nunca entram no bundle.
  const env = loadEnv(mode, process.cwd(), '');
  const upstream = env.API_UPSTREAM || 'http://localhost:8000';
  const apiKey = env.FINAGENT_API_KEY ?? '';

  const toUpstream = (path: string) => path.replace(/^\/api/, '');
  const proxy: Record<string, ProxyOptions> = {
    '/api/health': { target: upstream, changeOrigin: true, rewrite: toUpstream },
    '/api/v1': {
      target: upstream,
      changeOrigin: true,
      rewrite: toUpstream,
      configure: (server) => {
        // A chave é sempre a do proxy: a que vier do cliente é descartada.
        server.on('proxyReq', (proxyReq) => {
          proxyReq.removeHeader('x-api-key');
          if (apiKey) proxyReq.setHeader('X-API-Key', apiKey);
        });
      },
    },
  };

  return {
    plugins: [react()],
    server: { proxy },
    preview: { proxy },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['src/test/setup.ts'],
      exclude: ['e2e/**', 'node_modules/**'],
      reporters: process.env.CI ? ['default', 'junit'] : ['default'],
      outputFile: { junit: 'reports/frontend-unit.xml' },
    },
  };
});
