import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";


export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget = env.VITE_BACKEND_TARGET || "http://127.0.0.1:8200";
  const devHost = env.VITE_DEV_HOST || "127.0.0.1";
  const parsedDevPort = Number.parseInt(env.VITE_DEV_PORT || "", 10);
  const devPort = Number.isInteger(parsedDevPort) && parsedDevPort > 0 ? parsedDevPort : 4173;

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      host: devHost,
      port: devPort,
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
