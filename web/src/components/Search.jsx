import { useEffect, useState, useRef } from 'react'

export default function Search() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  // ⌘K / Ctrl+K 触发
  useEffect(() => {
    function handler(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(o => !o)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // 打开时聚焦输入框
  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current.focus(), 50)
    }
  }, [open])

  // 搜索（防抖）
  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }
    setLoading(true)
    const timer = setTimeout(async () => {
      try {
        // pagefind 是构建后产物，运行时动态加载
        // 用变量名骗过 Vite 静态分析，避免构建时报 UNRESOLVED_IMPORT
        const pagefindUrl = '/pagefind/pagefind.js'
        const pagefindModule = await import(/* @vite-ignore */ pagefindUrl)
        const pagefindSearch = pagefindModule.default || pagefindModule
        if (pagefindSearch.options) await pagefindSearch.options({})
        const search = await pagefindSearch.search(query)
        const top5 = search.results.slice(0, 8)
        const data = await Promise.all(top5.map(r => r.data()))
        setResults(data.map(d => ({
          url: d.url,
          title: d.meta?.title || d.url,
          excerpt: d.excerpt
        })))
      } catch (err) {
        console.error('search error', err)
        setResults([])
      }
      setLoading(false)
    }, 200)
    return () => clearTimeout(timer)
  }, [query])

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          position: 'fixed', bottom: 20, right: 20, zIndex: 50,
          background: 'var(--accent)', color: 'white', border: 'none',
          borderRadius: 8, padding: '8px 14px', cursor: 'pointer',
          fontFamily: 'var(--font-heading)', fontSize: '0.85rem',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
        }}
      >
        ⌘K 搜索
      </button>
    )
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
        paddingTop: '10vh'
      }}
      onClick={() => setOpen(false)}
    >
      <div
        style={{
          background: 'var(--bg-elevated)', borderRadius: 8,
          width: '90%', maxWidth: 600, maxHeight: '70vh',
          display: 'flex', flexDirection: 'column',
          boxShadow: '0 8px 32px rgba(0,0,0,0.2)'
        }}
        onClick={e => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          type="text"
          placeholder="搜索笔记..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          style={{
            width: '100%', padding: '16px 20px', border: 'none',
            borderBottom: '1px solid var(--border)',
            background: 'transparent', color: 'var(--text-primary)',
            fontFamily: 'var(--font-body)', fontSize: '1rem',
            outline: 'none', borderRadius: '8px 8px 0 0'
          }}
        />
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {loading && <div style={{ padding: 16, color: 'var(--text-muted)' }}>搜索中...</div>}
          {!loading && query && results.length === 0 && (
            <div style={{ padding: 16, color: 'var(--text-muted)' }}>无结果</div>
          )}
          {!loading && results.map((r, i) => (
            <a
              key={i}
              href={r.url}
              style={{
                display: 'block', padding: '12px 20px',
                borderBottom: '1px solid var(--border)',
                textDecoration: 'none', color: 'var(--text-primary)'
              }}
              dangerouslySetInnerHTML={{
                __html: `<div style="font-weight:600;font-family:var(--font-heading)">${r.title}</div>${r.excerpt ? `<div style="font-size:0.85em;color:var(--text-secondary);margin-top:4px">${r.excerpt}</div>` : ''}`
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
