import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";


export default defineConfig(({ mode }) => {
  const projectRoot = fileURLToPath(new URL("..", import.meta.url));
  const env = loadEnv(mode, projectRoot, "");
  const backendTarget = env.VITE_BACKEND_TARGET || "http://127.0.0.1:8200";
  const devHost = env.VITE_DEV_HOST || "127.0.0.1";
  const parsedDevPort = Number.parseInt(env.VITE_DEV_PORT || "", 10);
  const devPort = Number.isInteger(parsedDevPort) && parsedDevPort > 0 ? parsedDevPort : 4173;

  return {
    envDir: projectRoot,
    plugins: [vue()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    build: {
      chunkSizeWarningLimit: 750,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules")) {
              if (id.includes("@vicons")) {
                return "vendor-icons";
              }
              if (id.includes("echarts") || id.includes("zrender")) {
                return "vendor-echarts";
              }
              if (id.includes("naive-ui") || id.includes("vue-router") || id.includes("@vue") || id.includes("vue")) {
                return "vendor-framework";
              }
            }

            if (id.includes("AnalysisCenterPage")) {
              return "page-analysis";
            }

            if (id.includes("AlgoRadarPage")) {
              return "page-algo-radar";
            }

            return undefined;
          },
        },
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
