import { defineConfig } from 'astro/config'
import remarkRelinks from './src/plugins/remark-relinks.ts'

export default defineConfig({
  base: '/grounds/',
  site: 'https://tian.github.io',
  trailingSlash: 'never',
  markdown: {
    // Astro 7 默认用 Sätteri（Rust），切回 unified 处理器以支持 remark 插件
    mode: 'unified',
    remarkPlugins: [remarkRelinks],
  },
})
