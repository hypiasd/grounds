import { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceManyBody, forceLink, forceCenter, forceCollide } from 'd3-force'
import { select } from 'd3-selection'
import { zoom, zoomIdentity } from 'd3-zoom'

// topic 配色
const TOPIC_COLORS = {
  cpp: '#3b82f6',        // 蓝
  cuda: '#10b981',       // 绿
  vllm: '#f59e0b',       // 橙
  algorithms: '#ef4444', // 红
}

function nodeColor(node) {
  if (node.type === 'tag') return '#9ca3af' // 灰
  return TOPIC_COLORS[node.topic] || '#8b5cf6'
}

function nodeRadius(node) {
  if (node.type === 'tag') return 4
  if (node.isOverview) return 10
  return 6
}

// 计算节点 bounds，返回 fit-to-bounds 的 transform
function computeFitTransform(nodes, width, height, padding = 40) {
  if (nodes.length === 0) return null
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const n of nodes) {
    if (n.x < minX) minX = n.x
    if (n.y < minY) minY = n.y
    if (n.x > maxX) maxX = n.x
    if (n.y > maxY) maxY = n.y
  }
  const contentW = maxX - minX
  const contentH = maxY - minY
  const scale = Math.min(
    (width - padding * 2) / Math.max(contentW, 1),
    (height - padding * 2) / Math.max(contentH, 1),
    1.5  // 防止内容太小时过度放大
  )
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  const tx = width / 2 - cx * scale
  const ty = height / 2 - cy * scale
  return zoomIdentity.translate(tx, ty).scale(scale)
}

export default function Graph({ data, currentSlug, height = 400, mini = false }) {
  const svgRef = useRef(null)
  const [hovered, setHovered] = useState(null)
  const [nodes, setNodes] = useState([])
  const [links, setLinks] = useState([])
  const [fitTransform, setFitTransform] = useState(null)

  useEffect(() => {
    if (!data) return
    try {
      // 复制节点和边（forceSimulation 会 mutate）
      // 只把 note 节点放入仿真（tag 节点没有 link 边约束，放进仿真会被斥力推到极远坐标撑爆图谱）
      const simNodes = data.nodes
        .filter(n => n.type !== 'tag')
        .map(n => ({ ...n }))
      const simLinks = data.edges
        .filter(e => e.type === 'link')
        .map(e => ({ source: e.source, target: e.target }))

      // mini 模式：只显示当前节点的邻居
      let filteredNodes = simNodes
      let filteredLinks = simLinks
      if (mini && currentSlug) {
        const neighbors = new Set([currentSlug])
        simLinks.forEach(l => {
          if (l.source === currentSlug) neighbors.add(l.target)
          if (l.target === currentSlug) neighbors.add(l.source)
        })
        filteredNodes = simNodes.filter(n => neighbors.has(n.id))
        filteredLinks = simLinks.filter(l =>
          neighbors.has(l.source) && neighbors.has(l.target)
        )
      }

      const width = svgRef.current?.clientWidth ?? 800
      const h = height
      const simulation = forceSimulation(filteredNodes)
        .force('charge', forceManyBody().strength(mini ? -120 : -260))
        .force('link', forceLink(filteredLinks).id(d => d.id).distance(mini ? 80 : 100).strength(0.2))
        .force('center', forceCenter(width / 2, h / 2))
        .force('collide', forceCollide().radius(d => nodeRadius(d) + 6))

      // 跑 300 tick 让布局稳定（避免动画）
      for (let i = 0; i < 300; i++) simulation.tick()
      simulation.stop()

      // 计算 fit-to-bounds transform，让所有节点都能落在视口内
      const fit = computeFitTransform(filteredNodes, width, h, mini ? 30 : 50)
      setNodes(filteredNodes)
      setLinks(filteredLinks)
      setFitTransform(fit)
    } catch (err) {
      console.error('[Graph] simulation error:', err)
      if (typeof window !== 'undefined') {
        window.__graphErr = err?.message + '\n' + (err?.stack || '').slice(0, 500)
      }
    }
  }, [data, currentSlug, mini, height])

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return
    try {
      const svg = select(svgRef.current)
      const g = svg.select('g.zoom-layer')

      // 应用 fit transform（mini 和非 mini 都需要）
      if (fitTransform) {
        g.attr('transform', fitTransform)
      }

      // zoom（仅非 mini 模式，允许用户交互缩放/平移）
      if (!mini) {
        const zoomBehavior = zoom()
          .scaleExtent([0.2, 3])
          .on('zoom', (event) => {
            g.attr('transform', event.transform)
          })
        svg.call(zoomBehavior)
        // 设置初始 transform 为 fit
        if (fitTransform) {
          svg.call(zoomBehavior.transform, fitTransform)
        }
      }
    } catch (err) {
      console.error('[Graph] zoom setup error:', err)
    }
  }, [nodes, mini, fitTransform])

  if (!data || nodes.length === 0) {
    return <div style={{ height, background: 'var(--bg-elevated)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>加载图谱中...</div>
  }

  const baseUrl = import.meta.env.BASE_URL.replace(/\/$/, '')

  return (
    <svg
      ref={svgRef}
      style={{ width: '100%', height, background: 'var(--bg-elevated)', borderRadius: 6, border: '1px solid var(--border)' }}
    >
      <g className="zoom-layer">
        {/* 边 */}
        {links.map((link, i) => {
          const source = typeof link.source === 'object' ? link.source : nodes.find(n => n.id === link.source)
          const target = typeof link.target === 'object' ? link.target : nodes.find(n => n.id === link.target)
          if (!source || !target) return null
          const isHighlighted = hovered && (source.id === hovered || target.id === hovered)
          return (
            <line
              key={i}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke={isHighlighted ? 'var(--accent)' : 'var(--border-strong)'}
              strokeWidth={isHighlighted ? 2 : 1}
              opacity={hovered && !isHighlighted ? 0.1 : 0.6}
            />
          )
        })}

        {/* 节点 */}
        {nodes.map(node => {
          const isCurrent = node.id === currentSlug
          const isHovered = node.id === hovered
          const isNeighbor = hovered && links.some(l => {
            const s = typeof l.source === 'object' ? l.source.id : l.source
            const t = typeof l.target === 'object' ? l.target.id : l.target
            return (s === hovered && t === node.id) || (t === hovered && s === node.id)
          })
          const opacity = hovered && !isHovered && !isNeighbor ? 0.2 : 1

          const url = `${baseUrl}/${node.id.replace('/_overview', '')}`

          return (
            <g
              key={node.id}
              transform={`translate(${node.x},${node.y})`}
              style={{ cursor: 'pointer', opacity }}
              onMouseEnter={() => setHovered(node.id)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => {
                window.location.href = url
              }}
            >
              <title>{node.title}</title>
              {node.isOverview && (
                <circle
                  r={nodeRadius(node) + 3}
                  fill="none"
                  stroke={nodeColor(node)}
                  strokeWidth={1.5}
                />
              )}
              <circle
                r={nodeRadius(node)}
                fill={isCurrent ? 'var(--accent)' : nodeColor(node)}
                stroke={isHovered ? 'var(--accent)' : 'var(--bg-elevated)'}
                strokeWidth={isHovered ? 3 : 1.5}
              />
              {!mini && (
                <text
                  y={nodeRadius(node) + 12}
                  textAnchor="middle"
                  fontSize={10}
                  fontFamily="var(--font-heading)"
                  fill="var(--text-secondary)"
                  pointerEvents="none"
                >
                  {node.title.length > 15 ? node.title.slice(0, 13) + '...' : node.title}
                </text>
              )}
            </g>
          )
        })}
      </g>
    </svg>
  )
}
