import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/** 生成供同域网关读取的静态产物，不代理业务接口。 */
export default defineConfig({
  plugins: [vue()],
  base: '/',
  build: {
    outDir: 'dist',
  },
})
