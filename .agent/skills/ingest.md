---
name: ingest
description: 用户提供 PDF / 网页链接 / 项目仓库 / 文件等资料，或说"ingest/下载这个/把这个资料加进来/存一下这篇"时触发。把资料落地 raw/ 并生成摘要页。不要用于纯对话提问（那走 learn/query）。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# skill: ingest

## 何时用（触发）
- 用户发来 PDF / 文章 URL / 仓库地址 / 代码片段。
- 用户说："把这个网页存一下"、"下载这篇论文"、"ingest 这个资料"。

## 目标（完成时仓库应处于的状态）
- `raw/` 有该资料（或一份引用页）；`wiki/<topic>/` 下有摘要页，通过 `sources:` 指回 raw；互链建立；`_overview.md` 同步；已 `git commit`（注意 raw 本身不进 git）。

## 流程
1. **落地 raw/**：用户已手动放入 → 直接用；给链接 / 要求下载 → 下载或抓取文本存 `raw/`（文件名小写中划线）；给仓库 → **写引用页**（URL + 关键说明 + 关注的文件），**绝不 clone**。
2. **生成摘要页（推荐）**：在 `wiki/<topic>/` 下新建摘要页，记录资料讲了什么、关键要点、与学习的关联；`sources:` 指回 raw 原文。
3. **交叉链接 + 更新 `_overview.md`**。
4. **校验（必做）**：若下载了文件，`wc -l` / `ls -l` 确认非空；检查摘要页相对链接可解析；`git status` 确认 raw 未被误加进暂存（应被 .gitignore 忽略）。
5. **提交**：`git add -A && git commit -m "ingest raw: <资料名>"`。

## Gotchas（真实踩过的坑）
- **仓库类资料绝不 clone 进仓库**，只存引用页——否则仓库会塞爆。
- **下载 / 抓取前先确认 URL 与文件名**（小写中划线）；大文件先告知用户体积。
- **写入后校验非空**：并行写文件曾静默丢失内容。

## 注意
- 关联：[[../../AGENTS.md]]、[[../../.agent/conventions.md]]
