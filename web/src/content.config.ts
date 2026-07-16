import { defineCollection } from 'astro:content'
import { glob } from 'astro/loaders'

// Phase 1: 无 schema 校验，先跑通基本读取
// Phase 2 会加 frontmatter schema
const notes = defineCollection({
  loader: glob({ pattern: '**/*.md', base: '../wiki' }),
})

export const collections = { notes }
