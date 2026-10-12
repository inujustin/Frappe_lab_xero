import { copyFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const outputDirectory = fileURLToPath(new URL('../lab_core/public/frontend/', import.meta.url))
const websiteDirectory = fileURLToPath(new URL('../lab_core/www/', import.meta.url))

export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/assets/lab_core/frontend/' : '/lab/',
  plugins: [
    vue(),
    {
      name: 'lab-website-entry',
      apply: 'build',
      async writeBundle() {
        await mkdir(websiteDirectory, { recursive: true })
        await copyFile(`${outputDirectory}/index.html`, `${websiteDirectory}/lab.html`)
      },
    },
  ],
  build: {
    outDir: outputDirectory,
    // Only the generated frontend assets live in this directory.
    emptyOutDir: true,
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/login': 'http://127.0.0.1:8000',
      '/assets': 'http://127.0.0.1:8000',
      '/website_script.js': 'http://127.0.0.1:8000',
    },
  },
}))
