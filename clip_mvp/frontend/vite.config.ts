import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8010",
      "/static": "http://127.0.0.1:8010",
      "/uploads": "http://127.0.0.1:8010",
      "/outputs": "http://127.0.0.1:8010",
      "/audio": "http://127.0.0.1:8010",
    },
  },
});
