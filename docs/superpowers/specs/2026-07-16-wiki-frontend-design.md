# grounds 笔记仓库前端界面设计

- **日期**：2026-07-16
- **状态**：待实现
- **作者**：tian（brainstorming 协作产出）

---

## 1. 背景与目标

grounds 是个人学习笔记仓库，按 `wiki/<topic>/<note>.md` 组织 markdown 笔记，每篇笔记有完整 frontmatter（title/topic/tags/summary/created/updated），笔记间用标准 markdown 相对链接互链。AGENTS.md 规定了 learn/capture/query/lint 四个 skill 的工作流，笔记是唯一内容源。

**目标**：为仓库增加一个前端界面，把 markdown 笔记渲染成可浏览、可搜索、可视化的数字花园。

**非目标**：
- 不修改 `wiki/` 任何笔记内容
- 不影响现有 AGENTS.md 工作流
- 不做笔记编辑功能（只读浏览）

---

## 2. 决策摘要

通过 brainstorming 对话确认的关键决策：

| 维度 | 决策 |
|------|------|
| 界面风格 | 文档站 + 数字花园两者兼顾 |
| v1 范围 | 完整数字花园（sidebar + 反向链接 + tag 页 + MOC 图谱 + 缩略图谱 + 全文搜索） |
| 部署方式 | 本地预览 + GitHub Pages（project pages，base `/grounds/`） |
| 技术栈偏好 | 无所谓（最终选 Astro Starlight） |
| 工程位置 | 同仓库 `web/` 子目录 |
| URL 结构 | 主题优先：`/<topic>/<note>` |
| 首页布局 | 图谱主导（左大图谱 + 右 topic 列表 + 下最近更新） |
| 笔记页布局 | 右侧栏（正文左 + 右栏 TOC/反向链接，缩略图谱在底部） |
| 视觉风格 | 极简纸感 + 强代码高亮（米白底 + 衬线正文 + 深色代码块） |
| 知识图谱内容 | 笔记 + tag 混合（笔记-笔记实线、笔记-tag 虚线） |
| 缩略图谱行为 | 高亮当前笔记 + 直接邻居 |
| 搜索 | Pagefind 全文搜索 + ⌘K 触发 |
| `_overview.md` 处理 | 直接作为 topic 落地页渲染 |
| 图谱库 | D3-force |
| 构建产物 | `dist/` 不进 git，GH Actions 构建后部署 |

---

## 3. 技术选型

### 3.1 框架：Astro Starlight

**理由**：
- 文档站部分开箱即用（sidebar、Pagefind 搜索、暗色模式、prev/next）
- content collections 直接吃 markdown frontmatter
- 反向链接用 build-time 脚本生成，实现成本低于改造 Quartz 布局
- GitHub Pages 部署官方支持
- 岛屿架构，纯静态 HTML，首屏秒开
- 未来扩展空间大（tag 云、MOC、图谱组件）

**不选其他方案的理由**：
- VitePress：Vue 栈，数字花园特性弱
- Quartz：数字花园强但 sidebar/线性导航弱，"两者兼顾"反而要改布局
- Docusaurus：偏文档站，数字花园特性需大量自建
- 自己 Vite+React：ROI 低，要重实现 markdown 路由、frontmatter 解析、KaTeX 集成、搜索、相对链接重写
- MkDocs Material：Python 栈，数字花园特性弱

### 3.2 图谱库：D3-force

- 轻量（~50KB），原生 SVG
- 适合中等规模图（<500 节点舒适区，当前仓库 ~40 节点）
- 支持力导向布局、点击事件、缩放、拖拽

### 3.3 数据接入策略：方案 B 直接读外部目录

笔记源只有一份（`wiki/`），Astro content collection 通过 `glob({ base: '../wiki' })` 直接读取，**不 sync、不复制、不转格式**。

相对链接改写用 remark 插件在构建时内存处理，不落盘。`_overview.md` 的下划线前缀对 glob loader 无影响（不像 `src/pages/` 路由那样被忽略）。slug 由文件路径自动生成。

---

## 4. 架构总览

```
grounds/
├── wiki/                          # 唯一笔记源（不动，AGENTS.md 规则不变）
└── web/                           # 前端工程
    ├── package.json
    ├── astro.config.mjs           # Starlight + KaTeX + base=/grounds/
    ├── tsconfig.json
    └── src/
        ├── content.config.ts      # glob({ base: '../wiki', pattern: '**/*.md' })
        ├── plugins/
        │   └── remark-relinks.ts  # 构建时改写相对链接 + 收集边数据
        ├── data/
        │   └── graph.ts           # 构建时生成 GraphData
        ├── layouts/
        │   ├── Note.astro         # 笔记页模板
        │   └── Topic.astro        # topic 落地页模板
        ├── components/
        │   ├── Backlinks.astro
        │   ├── Graph.astro        # 首页大图谱（D3-force + React）
        │   ├── MiniGraph.astro    # 笔记页缩略图谱
        │   ├── TagList.astro
        │   └── Toc.astro
        └── pages/
            ├── index.astro        # 首页
            ├── graph.astro        # 全屏图谱页（可选，路由预留）
            ├── tags/
            │   ├── index.astro    # tag 云
            │   └── [tag].astro    # 单 tag 列表
            └── [...slug].astro    # 笔记 + topic 落地页 catch-all 路由
```

### 数据流

```
wiki/**/*.md（唯一源，永不动）
       │
       ▼
Astro content collection（glob base=../wiki）
       │
       ├─ remark-relinks 插件 → 改写链接（内存） + 收集链接边
       │
       ├─ graph.ts → 生成笔记节点 + tag 节点 + 边（内存）
       │
       └─ 反向链接索引 → 从 link 边派生（内存）
              │
              ▼
       静态 HTML（dist/）+ Pagefind 索引
```

所有结构化数据（图谱、反向链接、tag 索引）都在构建时生成，不落盘，不运行时计算。所有页面纯静态。

### 构建时序

```
1. Astro 启动构建
2. content collection glob 扫描 ../wiki/**/*.md
3. 每篇笔记走 remark-relinks 插件：
   - 改写相对链接为 /grounds/<topic>/<note>
   - 收集 (source, target) 链接关系 → edges[]
4. getCollection('notes') 返回所有 NoteEntry
5. graph.ts 生成 GraphData（笔记节点 + tag 节点 + 边）
6. 反向链接索引从 link 边派生
7. Astro 渲染所有页面到 dist/
8. Pagefind 扫描 dist/ 生成搜索索引
9. 完成
```

---

## 5. 数据模型

### 5.1 NoteEntry（笔记元数据）

每篇笔记一条，从 frontmatter + 文件路径提取：

```ts
interface NoteEntry {
  slug: string           // 'cpp/move-semantics'，URL 用，glob loader 自动生成
  title: string          // frontmatter.title
  topic: string          // frontmatter.topic
  tags: string[]         // frontmatter.tags
  summary: string        // frontmatter.summary
  created: string        // frontmatter.created (YYYY-MM-DD)
  updated: string        // frontmatter.updated
  sources?: string[]     // frontmatter.sources（可选）
  status?: 'draft'       // frontmatter.status（可选）
  isOverview: boolean    // 文件名是 _overview.md → true
  filePath: string       // 'cpp/move-semantics.md'，定位原始文件用
  bodyHtml: string       // Astro 渲染后的 HTML 正文
  toc: TocItem[]         // 从 markdown ## 标题提取的本页目录
}

interface TocItem {
  depth: number          // 2 / 3（## / ###）
  text: string           // 标题文本
  slug: string           // 锚点 id（'tldr'、'he-xin-gai-nian'）
}
```

### 5.2 GraphData（图谱数据）

```ts
interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

interface GraphNode {
  id: string             // = slug，如 'cpp/move-semantics'
  title: string
  topic: string          // 用于聚簇颜色（cpp=蓝、cuda=绿、vllm=橙、algorithms=红）
  type: 'note' | 'tag'   // 笔记节点 or tag 节点
  isOverview: boolean    // _overview 节点视觉区分
  updated: string        // 用于节点大小映射（近期更新的稍大）
}

interface GraphEdge {
  source: string         // 节点 id
  target: string         // 节点 id
  type: 'link' | 'tag'   // link=笔记间 markdown 链接（实线），tag=笔记-tag 归属（虚线）
}
```

### 5.3 反向链接索引

从 GraphData 派生：

```ts
function getBacklinks(slug: string, graph: GraphData): NoteEntry[]
```

实现：构建 `Map<targetSlug, sourceSlug[]>` 反向索引，从 edges 里 `type === 'link'` 的边反推。每条 backlink 带源笔记的 title、summary。

### 5.4 链接解析约定

remark-relinks 插件把 markdown 相对链接改写为绝对路径：

| 源链接（笔记里写的） | 改写后（渲染到 HTML） |
|---|---|
| `[noexcept](noexcept.md)` | `[noexcept](/grounds/cpp/noexcept)` |
| `[Dropout](../deep-learning/dropout.md)` | `[Dropout](/grounds/deep-learning/dropout)` |
| `[外部](https://...)` | 不动 |
| `[锚点](#section)` | 不动 |

改写时同时记录"这个链接指向哪个 slug"，作为 GraphData 边的来源。

### 5.5 tag 节点生成

从所有笔记的 `tags` 字段聚合：扫一遍 `getCollection('notes')`，每个出现的 tag 生成一个 GraphNode（`type: 'tag'`），同时为每条 `(笔记, tag)` 关系生成一条 edge（`type: 'tag'`）。

### 5.6 数据规模预估

按当前仓库 16 篇笔记：
- 笔记节点 16 个
- tag 节点 ~25 个
- link 边 ~30 条
- tag 边 ~40 条

总共 ~40 节点、~70 边。D3-force 完全无压力。100 篇笔记规模仍在舒适区（<500 节点）。

---

## 6. 页面与路由

所有路由挂在 `/grounds/` base 下。笔记 URL = `/grounds/<topic>/<note>`，topic URL = `/grounds/<topic>`。

### 6.1 路由表

| URL | 页面 | 数据来源 | 备注 |
|---|---|---|---|
| `/grounds/` | 首页 | 全部笔记 | MOC 图谱 + topic 列表 + 最近更新 |
| `/grounds/graph` | 全屏图谱 | GraphData | 可选，v1 路由预留 |
| `/grounds/tags` | tag 云 | 全部 tags | 每个 tag + 笔记数 |
| `/grounds/tags/<tag>` | 单 tag 列表 | 该 tag 下的笔记 | 按 updated 倒序 |
| `/grounds/<topic>` | topic 落地页 | _overview.md | 渲染 overview 正文 + 自动追加笔记卡片网格 |
| `/grounds/<topic>/<note>` | 笔记页 | 单篇笔记 | 正文 + 右栏 TOC/反向链接 + 底部缩略图谱 + prev/next |

### 6.2 首页 `/grounds/`

布局：
- 顶部：Header（logo + ⌘K 搜索触发 + GitHub 链接）
- Hero 区左侧：Graph 组件（D3-force 知识图谱，全宽，高 ~400px，节点可点击跳转）
- Hero 区右侧：TopicList（topic + 笔记数，点击进 topic 落地页）
- 底部：RecentUpdates（所有笔记按 updated 倒序前 5 条）

### 6.3 笔记页 `/grounds/<topic>/<note>`

三栏布局：
- **左栏 Sidebar**（Starlight 自带）：所有 topic 折叠列表，当前 topic 展开，当前笔记高亮
- **中栏 NoteContent**：标题 + 元信息行（topic · updated · tags）+ 正文（KaTeX + Shiki 代码高亮）+ 底部缩略图谱 + prev/next
- **右栏**：
  - 上半 Toc（本页 `##` 标题锚点）
  - 下半 Backlinks（反向链接列表，每条带 title + summary）

PrevNext 顺序：同 topic 内按 _overview 的"知识脉络"段顺序，无脉络则按文件名字母序。

### 6.4 topic 落地页 `/grounds/<topic>`

直接渲染 `_overview.md`，末尾自动追加笔记卡片网格（用结构化数据生成）。_overview.md 手写的"包含笔记"段保留为正文一部分，不重复渲染。

`_overview.md` 的 slug 是 `<topic>/_overview`，路由层重写为 `/<topic>`（不暴露 `_overview`）。

### 6.5 tag 云 `/grounds/tags`

字号映射笔记数（多的大、少的小），点击进单 tag 页。

### 6.6 单 tag 页 `/grounds/tags/<tag>`

按 `updated` 倒序，每条带 title + topic + updated + summary。

### 6.7 路由实现

`src/pages/[...slug].astro` 用 catch-all 路由处理笔记和 topic 落地页：

```ts
export async function getStaticPaths() {
  const notes = await getCollection('notes')
  return notes.map(note => ({
    params: { slug: note.slug },
    props: { note }
  }))
}

// 路由层判断：
// - note.isOverview → 渲染 Topic.astro（落地页布局，无右栏 TOC）
// - 否则 → 渲染 Note.astro（笔记页布局）
```

---

## 7. 视觉设计

### 7.1 风格

极简纸感 + 强代码高亮：米白底 + 衬线正文，但代码块永远深底 + 多彩高亮。

### 7.2 配色系统

```css
/* 亮色（默认） */
--bg-page:        #fafaf7;   /* 米白底 */
--bg-elevated:    #ffffff;   /* 卡片/代码块底 */
--bg-sidebar:     #f3f2ed;   /* 侧栏 */
--bg-code:        #1e1e2e;   /* 代码块深底 */
--text-primary:   #1a1a1a;
--text-secondary: #555555;
--text-muted:     #888888;
--text-on-code:   #cdd6f4;
--accent:         #8b5cf6;   /* 紫色主色 */
--accent-hover:   #7c3aed;
--accent-soft:    #ede9fe;
--border:         #e5e3dc;
--border-strong:  #c9c6bd;
```

```css
/* 暗色（跟随系统 prefers-color-scheme） */
--bg-page:        #1a1a1a;
--bg-elevated:    #242424;
--bg-sidebar:     #1f1f1f;
--bg-code:        #11111b;
--text-primary:   #e8e6e1;
--text-secondary: #b0aea7;
--text-muted:     #777571;
--text-on-code:   #cdd6f4;
--accent:         #a78bfa;
--accent-hover:   #c4b5fd;
--accent-soft:    #2a2540;
--border:         #2e2e2e;
--border-strong:  #3d3d3d;
```

代码块在两种模式下都是深底，不变。

### 7.3 字体

```css
--font-body:    'Source Serif Pro', 'Noto Serif SC', Georgia, serif;
--font-heading: -apple-system, 'PingFang SC', 'Noto Sans SC', sans-serif;
--font-mono:    'JetBrains Mono', 'SF Mono', 'Cascadia Code', Consolas, monospace;
```

从 Google Fonts CDN 引入，不嵌字体文件。

### 7.4 代码高亮

Shiki（Starlight 内置），主题 **Catppuccin Mocha**：
- 关键字 → 紫色 `#cba6f7`
- 函数 → 蓝色 `#89b4fa`
- 字符串 → 黄色 `#f9e2af`
- 注释 → 灰色 `#6c7086`
- 数字 → 桃色 `#fab387`

**核心约束**：代码块永远深底（`#1e1e2e`），即使亮色模式。纸感正文 + 深色代码岛，视觉反差强烈。

### 7.5 数学公式

KaTeX（Starlight 内置 remark-math + rehype-katex）：
- 行内 `$...$` → 跟正文同行，继承衬线字体
- 块级 `$$...$$` → 居中，上下留白

### 7.6 笔记页排版

```css
.note-content {
  max-width: 720px;
  margin: 0 auto;
  font-size: 16px;
  line-height: 1.75;       /* 衬线字体行高放宽 */
  color: var(--text-primary);
}
h1 { font-family: var(--font-heading); font-size: 2rem; font-weight: 700; }
h2 { font-family: var(--font-heading); font-size: 1.4rem; font-weight: 600;
     margin-top: 2.5em; border-bottom: 1px solid var(--border); padding-bottom: 0.3em; }
h3 { font-family: var(--font-heading); font-size: 1.15rem; font-weight: 600;
     margin-top: 1.8em; }
.note-meta {
  font-family: var(--font-heading);
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 2em;
}
.note-meta .tag {
  color: var(--accent);
  background: var(--accent-soft);
  padding: 1px 6px;
  border-radius: 3px;
}
pre {
  background: var(--bg-code);
  border-radius: 6px;
  padding: 16px;
  overflow-x: auto;
  font-size: 0.9rem;
  line-height: 1.6;
}
code:not(pre code) {
  background: var(--accent-soft);
  color: var(--accent-hover);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.9em;
}
```

### 7.7 图谱视觉

**节点**：
- 笔记节点：圆形，半径 6-10px（按 `updated` 映射，近期更新的稍大）
- tag 节点：圆角矩形，宽 30-40px，高 16px，内嵌 tag 名
- _overview 节点：双线圆圈
- topic 颜色：cpp=蓝、cuda=绿、vllm=橙、algorithms=红

**边**：
- link 边：实线，1px，半透明灰 `rgba(0,0,0,0.2)`
- tag 边：虚线，1px，更淡 `rgba(0,0,0,0.1)`
- hover 节点：相连边加粗 + 不透明

**交互**：
- 拖拽节点固定位置
- 滚轮缩放
- 点击节点跳转
- hover 节点高亮邻居、淡化其他

### 7.8 缩略图谱（笔记页）

固定 200×150px，放在正文下方：
- 当前节点：紫色实心，半径 10px
- 直接邻居：正常色，半径 6px
- 二度邻居：淡化（opacity 0.3）
- 远处节点：不显示
- 点击邻居跳转

### 7.9 响应式断点

```css
/* 桌面（>1024px）：三栏 */
.sidebar (240px) | content (flex) | right-rail (220px)

/* 平板（768-1024px）：两栏，右栏折叠到正文下方 */
.sidebar (200px) | content (flex)
                  └ toc + backlinks（堆叠在正文末尾）

/* 移动（<768px）：单栏 */
content (full width)
  ├ 顶部 hamburger 菜单（点开 sidebar 抽屉）
  ├ 正文
  ├ toc + backlinks（堆叠，<details> 折叠）
  └ mini graph（隐藏或折叠按钮）
```

### 7.10 其他视觉细节

- **链接**：正文内链接用 accent 紫色 + 下划线，hover 加深
- **分隔线**：`<hr>` 用 1px `--border` 色
- **引用块**：左侧 3px accent 色边框，背景 `--accent-soft`
- **表格**：Starlight 默认样式，斑马纹用 `--bg-elevated`
- **图片**：圆角 6px，最大宽度 100%
- **暗色模式**：跟随系统，不做手动切换按钮（v1 YAGNI）

---

## 8. 构建与部署

### 8.1 本地开发

```bash
cd web
npm install
npm run dev              # http://localhost:4321
```

`npm run dev` = `astro dev`。Astro 自动监听 `../wiki/` 变动（content collection 跨目录监听），笔记保存即重载。

### 8.2 构建命令

```bash
npm run build            # 输出到 web/dist/
```

`npm run build` = `astro build && pagefind --site dist`

顺序很重要：Pagefind 必须在 `astro build` 成功后跑，否则索引不到内容。

### 8.3 Astro 配置

`web/astro.config.mjs`：

```js
import starlight from '@astrojs/starlight'
import { defineConfig } from 'astro/config'

export default defineConfig({
  base: '/grounds/',
  site: 'https://tian.github.io',       // 替换成实际 GH 用户名
  trailingSlash: 'never',
  integrations: [
    starlight({
      title: 'grounds',
    })
  ]
})
```

### 8.4 GitHub Pages 部署

`.github/workflows/deploy.yml`：

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
    paths:
      - 'wiki/**'
      - 'web/**'
      - '.github/workflows/deploy.yml'
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'
          cache-dependency-path: web/package-lock.json
      - name: Install
        working-directory: web
        run: npm ci
      - name: Build
        working-directory: web
        run: npm run build
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/deploy-pages@v4
        id: deployment
```

GH Pages 设置：仓库 Settings → Pages → Source: **GitHub Actions**。

### 8.5 依赖清单

`web/package.json`：

```json
{
  "name": "grounds-web",
  "type": "module",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build && pagefind --site dist",
    "preview": "astro preview",
    "astro": "astro"
  },
  "dependencies": {
    "astro": "^4.0.0",
    "@astrojs/starlight": "^0.25.0",
    "@astrojs/mdx": "^3.0.0",
    "@astrojs/react": "^3.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "d3": "^7.0.0",
    "d3-force": "^3.0.0",
    "@types/d3": "^7.0.0",
    "@types/react": "^18.0.0",
    "@types/react-dom": "^18.0.0",
    "typescript": "^5.0.0"
  },
  "devDependencies": {
    "pagefind": "^1.0.0"
  }
}
```

### 8.6 .gitignore 更新

主仓库 `.gitignore` 追加：

```gitignore
.superpowers/
web/node_modules/
web/dist/
web/.astro/
```

`web/` 目录本身进 git（package.json、astro.config、src/ 都要 commit），只有构建产物和依赖不进。

### 8.7 故障兜底

| 问题 | 表现 | 解决 |
|---|---|---|
| 笔记链接指向不存在文件 | 链接 404 | remark-relinks 检测到目标不存在 → 构建失败 + 错误日志 |
| frontmatter 缺字段 | collection schema 报错 | 构建失败 + 指出哪个文件缺哪个字段 |
| Pagefind 索引为空 | 搜索无结果 | 检查 `astro build` 是否在 `pagefind` 之前成功 |
| GH Pages base 路径错 | 资源 404 | 检查 `astro.config.mjs` 的 `base: '/grounds/'` |
| 笔记相对链接写错 | 链接 404 或路径奇怪 | remark-relinks 严格匹配 `xxx.md` / `../topic/xxx.md` 模式 |

---

## 9. AGENTS.md 影响

| 现有规则 | 前端工程是否影响 |
|---|---|
| 笔记改动即 commit | 不影响。`wiki/` 和 `web/` 改动分开 commit |
| 笔记原子性、frontmatter 规范 | 不影响。前端只读 `wiki/` |
| learn/capture/query/lint skill | 不影响。skill 直接操作 `wiki/` |
| lint 检查孤儿页/断链 | 前端构建也会检查断链，互补 |

**新增约定**：
- `web/` 工程的改动也 commit，commit message 格式 `web <topic>: <一句话>`（如 `web graph: 修复节点点击跳转`）
- 修笔记 ≠ 修前端，不要混在一个 commit 里

---

## 10. 验收标准

部署到 `https://tian.github.io/grounds/` 后：

- [ ] 首页 MOC 图谱能加载、节点可点击跳转、tag 节点和笔记节点视觉区分
- [ ] `/grounds/cpp/move-semantics` 笔记页正常显示：代码高亮（Catppuccin Mocha 深底）、KaTeX 公式、反向链接面板、缩略图谱
- [ ] `/grounds/cpp` topic 落地页渲染 _overview.md 正文 + 自动追加笔记卡片网格
- [ ] `/grounds/tags` tag 云显示所有 tag + 笔记数
- [ ] `/grounds/tags/cpp11` 单 tag 页列出所有带 cpp11 tag 的笔记
- [ ] ⌘K 触发搜索浮层，输入关键词返回结果（带正文片段预览）
- [ ] 暗色模式跟随系统切换
- [ ] 移动端布局正确（单栏、hamburger 菜单、折叠的 TOC/backlinks）
- [ ] 笔记间相对链接全部正确跳转（无 404）
- [ ] 笔记里的 ASCII 图表正确显示（等宽字体 + 不换行）

---

## 11. 未来扩展（v2+，不在本次范围）

- 自定义域名（替换 GH Pages 默认 URL）
- 笔记内嵌交互式 demo（用 MDX wrapper 包 markdown）
- 全屏图谱页 `/grounds/graph` 实现（v1 只预留路由）
- 时间线视图（按 created/updated 时间轴展示笔记）
- 暗色模式手动切换按钮
- 阅读进度条
- 笔记页打印样式优化
- 全文搜索支持中文分词优化（Pagefind 默认对中文支持一般）
