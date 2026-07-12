---
name: ingest
description: 用户给 PDF / 链接 / 仓库等资料时触发。把资料落地到 raw/，生成 source 摘要页，并与 wiki 交叉链接。
---

# skill: ingest

## 触发
用户提供资料：PDF 文件、网页链接、项目仓库、代码片段等。

## 流程

### 1. 落地资料到 raw/
- 用户已手动放入 `raw/` → 直接用，不移动。
- 用户给链接 / 要求下载 → 下载或抓取文本存到 `raw/`（文件名小写中划线，如 `2026-transformers.pdf` 或 `article-xxx.md`）。
- 用户给仓库 → **不 clone 进仓库**（保持轻量），在 `raw/` 写一份引用页：仓库 URL + 关键说明 + 你关注的目录 / 文件。
- raw/ 内容**不可变**：只增不删、不改原始内容。

### 2. 生成 source 摘要页（可选但推荐）
- 在 `wiki/<topic>/` 下（或 `wiki/sources/`）新建摘要页，记录：资料讲了什么、关键要点、与你学习的关联。
- 通过 `sources:` frontmatter / 相对链接指回 `raw/` 原文。

### 3. 交叉链接
- 摘要页 ↔ 相关 wiki 笔记互链。
- 更新 `_overview.md`。

### 4. 收尾
- `git add -A && git commit -m "ingest raw: <资料名>"`（commit message 即维护日志）

## 注意
- 仓库类资料只存引用页（URL + 关键说明），不把整个仓库放进来。
