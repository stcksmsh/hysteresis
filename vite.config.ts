import { defineConfig } from 'vite'

export default defineConfig({
  base: '/sinteza-viz/',
  worker: {
    format: 'es',
  },
  build: {
    target: 'es2022',
  },
})
