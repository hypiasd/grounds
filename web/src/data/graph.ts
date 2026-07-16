import { getCollection } from 'astro:content'
import fs from 'node:fs'
import path from 'node:path'

export interface GraphNode {
  id: string
  title: string
  topic: string
  type: 'note' | 'tag'
  isOverview: boolean
  updated: string
}

export interface GraphEdge {
  source: string
  target: string
  type: 'link' | 'tag'
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

const WIKI_DIR = path.resolve(process.cwd(), '../wiki')

// 把相对链接 href 解析成 target slug
function resolveToSlug(href: string, sourceSlug: string): string | null {
  if (/^https?:\/\//.test(href)) return null
  if (href.startsWith('#')) return null
  if (/^[a-z]+:/.test(href)) return null

  let p = href
  if (p.endsWith('.md')) p = p.slice(0, -3)

  const sourceTopic = sourceSlug.split('/')[0]
  const parts = p.split('/')

  if (parts[0] === '..') {
    if (parts.length >= 3) return `${parts[1]}/${parts[2]}`
    return null
  } else if (parts[0] === '.') {
    return `${sourceTopic}/${parts[1]}`
  } else {
    return `${sourceTopic}/${parts[0]}`
  }
}

// 从 markdown 源文件提取笔记间链接
// 匹配 [text](xxx.md) 或 [text](../topic/xxx.md)，不匹配 http/锚点
const LINK_RE = /\[[^\]]*\]\(([^)]+)\)/g

function extractLinks(markdown: string, sourceSlug: string): string[] {
  const targets: string[] = []
  let match
  while ((match = LINK_RE.exec(markdown)) !== null) {
    const href = match[1]
    const slug = resolveToSlug(href, sourceSlug)
    if (slug) targets.push(slug)
  }
  return targets
}

export async function buildGraph(): Promise<GraphData> {
  const notes = await getCollection('notes')
  const nodes: GraphNode[] = []
  const edges: GraphEdge[] = []

  // 1. 笔记节点 + link 边
  for (const note of notes) {
    const id = note.id
    const isOverview = id.endsWith('/_overview')
    const topic = id.split('/')[0]
    const updated = String(note.data.updated || '')
    nodes.push({
      id,
      title: note.data.title || id,
      topic,
      type: 'note',
      isOverview,
      updated,
    })

    // 读源文件提取 link
    const filePath = path.join(WIKI_DIR, `${id}.md`)
    try {
      const markdown = fs.readFileSync(filePath, 'utf-8')
      const targets = extractLinks(markdown, id)
      for (const target of targets) {
        edges.push({ source: id, target, type: 'link' })
      }
    } catch {
      // _overview 可能没文件，跳过
    }
  }

  // 2. tag 节点 + tag 边
  const tagSet = new Set<string>()
  for (const note of notes) {
    for (const tag of note.data.tags || []) {
      tagSet.add(tag)
    }
  }
  for (const tag of tagSet) {
    nodes.push({
      id: `tag:${tag}`,
      title: `#${tag}`,
      topic: '',
      type: 'tag',
      isOverview: false,
      updated: '',
    })
  }
  for (const note of notes) {
    for (const tag of note.data.tags || []) {
      edges.push({ source: note.id, target: `tag:${tag}`, type: 'tag' })
    }
  }

  return { nodes, edges }
}

// 反向链接：target slug → source 笔记列表
export function getBacklinks(
  slug: string,
  graph: GraphData
): Array<{ id: string; title: string; summary: string }> {
  return graph.edges
    .filter(e => e.type === 'link' && e.target === slug)
    .map(e => {
      const sourceNode = graph.nodes.find(n => n.id === e.source)
      return {
        id: e.source,
        title: sourceNode?.title || e.source,
        summary: '',
      }
    })
}
