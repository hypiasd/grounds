---
name: capture
description: 用户说"整理一下/记下来/沉淀"，或一轮对话结束想固化收获时触发。把当前对话有价值部分沉淀成 wiki 笔记。不要在用户只想继续聊、或本轮无明显收获时使用。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# skill: capture

## 何时用（触发）
- 用户说："把这轮对话整理一下"、"记下来"、"沉淀一下"。
- 一轮对话结束后，用户希望把学到的东西固化进仓库。

## 目标（完成时仓库应处于的状态）
- 仓库新增/更新了相关 `wiki/<topic>/<note>.md`，对应 `_overview.md` 已同步，且已 `git commit`。
- **不**另存原始对话原文（对话精华已在笔记里）。

## 流程
1. **提取**：回顾当前对话，提取学了什么、关键结论、待验证 / 开放问题；判断归属 `wiki/<topic>/`（沿用或新建，新建须带 `_overview.md`）。
2. **写 / 更新笔记**：对应已有笔记 → 更新（刷新 `updated` 日期，补内容）；新知识点 → 新建 `<note>.md`（套 `conventions.md` 模板）；更新 `_overview.md`。
3. **校验（必做）**：`wc -l <note.md>` 确认非空；`git status` 确认只改了预期文件；检查新增相对链接目标存在。
4. **提交**：`git add -A && git commit -m "capture <topic>: 沉淀对话笔记 <YYYY-MM-DDTHH-MM>"`。

## Gotchas（真实踩过的坑）
- **不另存完整对话原文**：`chats/` 已砍掉——agent 无法可靠保真地逐字存 transcript（写进去的常是凭记忆重建，并非真原文），且原始对话价值与 `wiki/` 提炼高度重叠。
- **写入后必须校验非空**：并行写文件曾静默丢失内容（报成功但 0 行）。
- **只沉淀有价值的**：不要为记而记，避免笔记膨胀成流水账。

## 注意
- capture 是**独立** skill，不和 learn 自动绑定；用户掌控节奏。
- 关联：[[../../AGENTS.md]]、[[../../.agent/conventions.md]]
