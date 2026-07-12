---
name: capture
description: 本轮对话有收获时触发（用户说"整理一下"）。把当前对话中有价值的部分沉淀成 wiki 笔记。
---

# skill: capture

## 触发
用户说"把这轮对话整理一下 / 沉淀 / 记下来"，或一轮对话结束后用户希望固化收获。

## 流程

### 1. 回顾当前对话
- 提取：学了什么、关键结论、待验证 / 开放问题。
- 判断这些内容该归入哪个 `wiki/<topic>/`（沿用或新建，新建须带 `_overview.md`）。

### 2. 写 / 更新笔记
- 若结论对应已有笔记 → 更新该笔记（刷新 `updated` 日期，补内容）。
- 若是新知识点 → 新建 `<note>.md`（套用 conventions.md 模板）。
- 更新 `_overview.md`。

### 3. 收尾
- `git add -A && git commit -m "capture <topic>: 沉淀对话笔记 <YYYY-MM-DDTHH-MM>"`（commit message 即维护日志）

## 注意
- capture 是**独立** skill，不和 learn 自动绑定；用户掌控节奏。
- 只沉淀有价值的内容，不要为了记而记。
- 不另存完整对话原文：对话精华由本 skill 直接沉淀进 `wiki/`，不维护 `chats/` 之类的原始对话档案目录。
