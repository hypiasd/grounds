import { defineCollection, z } from 'astro:content'
import { glob } from 'astro/loaders'

// YAML 会把 2026-07-15 解析成 Date 对象，用 coerce 转 string
const dateString = z.union([
  z.string(),
  z.coerce.string(),  // Date → "2026-07-15T00:00:00.000Z"，后续截前 10 位
])

// wiki 笔记和 paper 笔记共用同一套 frontmatter schema
const noteSchema = z.object({
  title: z.string().optional(),
  topic: z.string().optional(),
  tags: z.array(z.string()).default([]),
  summary: z.string().default(''),
  created: dateString.optional(),
  updated: dateString.optional(),
  sources: z.array(z.string()).optional(),
  status: z.literal('draft').optional(),
})

const notes = defineCollection({
  loader: glob({ pattern: '**/*.md', base: '../wiki' }),
  schema: noteSchema,
})

const papers = defineCollection({
  loader: glob({ pattern: '**/*.md', base: '../paper' }),
  schema: noteSchema,
})

export const collections = { notes, papers }
