import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

/** 单元环境独立于真实浏览器套件，避免把夹具验证混入业务 E2E。 */
export default defineConfig({
  plugins: [vue()],
  test: {
    include: ['tests/unit/**/*.spec.ts'],
    environment: 'jsdom',
    setupFiles: ['./tests/unit/setup.ts'],
    restoreMocks: true,
    clearMocks: true,
  },
})
