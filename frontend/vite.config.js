import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const port = Number(env.VITE_PORT || env.PORT || 5173);
  const host = env.VITE_HOST || '127.0.0.1';
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5000';

  return {
    plugins: [vue()],
    server: {
      host,
      port,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
