import { defineConfig } from 'vite'

export default defineConfig({
  base: '/hysteresis/',
  worker: {
    format: 'es',
  },
  build: {
    target: 'es2022',
  },
})
