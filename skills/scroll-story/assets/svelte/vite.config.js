import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
// base: "./" so the built site works from any folder of a newsroom's CMS or a static host
// MapLibre alone is about 1 MB minified, so the default 500 kB warning would always fire
export default defineConfig({ plugins: [svelte()], base: "./", build: { chunkSizeWarningLimit: 1600 } });
