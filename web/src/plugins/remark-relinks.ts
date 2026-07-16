import { visit } from 'unist-util-visit'
import type { Link, Root } from 'mdast'
import type { VFile } from 'vfile'

// 全局边收集器：source slug → target slug 列表
// 构建时由 graph.ts 读取
export const linkEdges = new Map<string, Set<string>>()

// 把相对链接解析成 slug
// - 'noexcept.md' → 同目录，sourceSlug 的 topic + 'noexcept'
// - '../deep-learning/dropout.md' → 跨 topic
// - './note.md' → 同目录
// 返回 null 表示不是笔记链接（外部 URL、锚点等）
function resolveToSlug(href: string, sourceSlug: string): string | null {
  // 外部链接
  if (/^https?:\/\//.test(href)) return null
  // 锚点
  if (href.startsWith('#')) return null
  // mailto 等
  if (/^[a-z]+:/.test(href)) return null

  // 去掉 .md 后缀
  let path = href
  if (path.endsWith('.md')) path = path.slice(0, -3)

  // 解析相对路径
  const sourceTopic = sourceSlug.split('/')[0]
  const parts = path.split('/')

  if (parts[0] === '..') {
    // ../topic/note → 跨 topic
    if (parts.length >= 3) {
      return `${parts[1]}/${parts[2]}`
    }
    return null
  } else if (parts[0] === '.') {
    // ./note → 同目录
    return `${sourceTopic}/${parts[1]}`
  } else {
    // note.md → 同目录
    return `${sourceTopic}/${parts[0]}`
  }
}

// 从 vfile.path 推 slug
// path 形如 '/Users/.../wiki/cpp/move-semantics.md'
// → 'cpp/move-semantics'
function slugFromVFile(vfile: VFile): string | null {
  if (!vfile.path) return null
  // 匹配 wiki/ 之后的路径，去掉 .md
  const match = vfile.path.match(/\/wiki\/(.+)\.md$/)
  if (!match) return null
  return match[1]
}

const BASE = '/grounds'

export default function remarkRelinks() {
  return (tree: Root, vfile: VFile) => {
    const sourceSlug = slugFromVFile(vfile)
    if (!sourceSlug) return

    visit(tree, 'link', (node: Link) => {
      const targetSlug = resolveToSlug(node.url, sourceSlug)
      if (targetSlug) {
        // 改写 URL
        node.url = `${BASE}/${targetSlug}`
        // 收集边
        if (!linkEdges.has(sourceSlug)) {
          linkEdges.set(sourceSlug, new Set())
        }
        linkEdges.get(sourceSlug)!.add(targetSlug)
      }
    })
  }
}
