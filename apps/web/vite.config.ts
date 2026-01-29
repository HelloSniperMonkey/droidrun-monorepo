import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";
import { lingoCompilerPlugin } from "@lingo.dev/compiler/vite";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 3000,
    hmr: {
      overlay: false,
    },
  },
  plugins: [
    react(),
    mode === "development" && componentTagger(),
    lingoCompilerPlugin({
      sourceLocale: "en",
      targetLocales: ["es", "fr", "de", "ja", "zh-CN", "ar", "pt", "ru", "ko", "it"],
      sourceRoot: "./src",
      lingoDir: "./.lingo",
    }),
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
