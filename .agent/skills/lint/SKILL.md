---
name: lint
description: 用户说"体检/lint/检查仓库/有没有矛盾/孤儿页/过时内容"时触发。只读检查仓库健康度，默认只报告不修改。不要在用户没要求时用。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# lint

## 何时用（触发）
- 用户说："lint 一下"、"检查仓库"、"有没有矛盾 / 孤儿页 / 过时内容"。
- 用户想定期维护健康度。

## 目标（完成时仓库应处于的状态）
- 产出问题清单（位置 / 类型 / 建议修复）；若用户授权，已修复并 `git commit`；现有内容不被破坏。

## 流程
1. **扫描（只读）**：
   - **孤儿页**：`wiki/` 下无任何入链、也不被 `_overview.md` 引用的笔记。
   - **缺失链接**：笔记里链接指向不存在的文件。
   - **矛盾说法**：不同笔记对同一概念描述冲突。
   - **过时内容**：引用了被新资料淘汰的说法（对照 `updated` 日期）。
   - **索引覆盖**：列 `wiki/` 核对每个 `<topic>/` 是否都有 `_overview.md`。
   - **模板合规**：frontmatter 是否含 `title/topic/tags/summary/created/updated`；标题是否是主张式（而非"XX 笔记"）；链接是否说明了关系。
2. **报告**：列出清单给用户，**先不自动改**，让用户决定。
3. **若授权修复**：更新 `_overview.md`；`git add -A && git commit -m "lint: 修复 <问题摘要>"`。
4. **校验（必做）**：修复后确认链接已修、`wc -l` 确认文件非空、`git status` 符合预期。

## 报告格式示例

```
## Lint 报告

### 孤儿页（0 入链）
- wiki/llm/forgotten-note.md — 建议：加入 _overview.md 或被其他笔记链接

### 断链
- wiki/llm/attention.md 引用了 [[transformer]] — 目标不存在

### 缺 _overview.md
- wiki/reinforcement-learning/ — 建议新建
```

## Gotchas（真实踩过的坑）

- **默认只读优先**：先报告，用户说"直接修"才改。自动修改曾引入意外破坏——agent 把"看起来冗余"的笔记删了，但那是用户刻意保留的草稿。
- **不要把指向 raw/ 的链接当"断链"修掉**：raw/ 是本地素材引用，链接在本地环境可解析即可。曾把有效的 raw 引用当断链删除，导致溯源断裂。
- **绝不删历史 commit**；删除用冷归档（`.agent/archive/`）——保留回滚可能。

## 注意
- 冷归档：确认废弃的笔记移入 `.agent/archive/`，并在原 `_overview.md` 注明。
- 关联：`AGENTS.md`、`.agent/conventions.md`
