---
name: capture
description: 用户说"整理一下/记下来/沉淀"，或一轮对话结束想固化收获时触发。把当前对话有价值部分沉淀成 wiki 笔记。不要在用户只想继续聊、或本轮无明显收获时使用。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# capture

## 何时用（触发）
- 用户说："把这轮对话整理一下"、"记下来"、"沉淀一下"。
- 一轮对话结束后，用户希望把学到的东西固化进仓库。
- 注意：learn skill 讲解后如果用户说"存一下"，由 learn 自己处理，不需要再走 capture。

## 目标（完成时仓库应处于的状态）
- 仓库新增/更新了相关 `wiki/<topic>/<note>.md`，对应 `_overview.md` 已同步，且已 `git commit`。
- **不**另存原始对话原文（对话精华已在笔记里）。

## 流程
1. **提取**：回顾当前对话，提取学了什么、关键结论、待验证 / 开放问题；列 `wiki/` 看已有主题，判断归属 `wiki/<topic>/`（沿用或新建，新建须带 `_overview.md`）。
2. **判断价值**：对照"值得沉淀"标准筛选，不要全量搬运对话。
3. **写 / 更新笔记**：对应已有笔记 → 更新（刷新 `updated` 日期，补内容）；新知识点 → 新建 `<note>.md`（读 `.agent/conventions.md` 后按模板写）；更新 `_overview.md`。
4. **校验（必做）**：`wc -l <note.md>` 确认非空；确认 frontmatter 包含 `title`（主张式）、`topic`、`tags`、`summary`、`created`、`updated`；`git status` 确认只改了预期文件；检查新增相对链接目标存在。
5. **提交**：`git add -A && git commit -m "capture <topic>: 沉淀对话笔记 <YYYY-MM-DDTHH-MM>"`。

## 什么是"值得沉淀"

**值得沉淀**：
- 对话中产生了新的理解（不是搬运已知事实）
- 有具体的关键结论或待验证的假设
- 填补了仓库现有知识的空白
- 用户明确说"这个很重要，记下来"

**不值得沉淀**：
- 日常闲聊、问候、流程性对话
- 和已有笔记高度重复的内容
- 只有一句话的简单结论，不值得单独成篇
- agent 不确定、无法验证的内容

## Gotchas（真实踩过的坑）

- **不另存完整对话原文**：agent 无法可靠保真地逐字存 transcript（写进去的常是凭记忆重建，并非真原文），对话精华应在笔记中提炼，而非全量搬运。
- **写入后必须校验非空**：并行写文件曾静默丢失内容（报成功但 0 行）。
- **只沉淀有价值的**：不要为记而记。提取时对照"值得沉淀"标准做减法——宁可漏一篇，不要存一堆流水账。曾有 agent 把整段对话逐条拆成多篇笔记，导致 wiki 膨胀。
- **capture 和 learn 的边界**：learn 讲解后用户当场说"存"→ 由 learn 自己处理，无需再走 capture。capture 处理的是 learn 之外的对话收获。

## 注意
- capture 是**独立** skill，不和 learn 自动绑定；用户掌控节奏。
- 关联：`AGENTS.md`、`.agent/conventions.md`
