import { defineConfig } from 'astro/config'
import react from '@astrojs/react'
import remarkRelinks from './src/plugins/remark-relinks.ts'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'

export default defineConfig({
  base: '/grounds/',
  site: 'https://tian.github.io',
  trailingSlash: 'never',
  integrations: [react()],
  markdown: {
    mode: 'unified',
    remarkPlugins: [remarkRelinks, remarkMath],
    rehypePlugins: [rehypeKatex],
    shikiConfig: {
      theme: 'catppuccin-mocha',
      wrap: true,
    },
  },
})
