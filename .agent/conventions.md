# conventions.md — 笔记模板与规范

本文件定义仓库内所有 Markdown 内容的统一格式。agent 在写入任何笔记前必须先读本文件。

---

## 1. 笔记 frontmatter（wiki 下的笔记必须包含）

每篇 `wiki/<topic>/<note>.md` 顶部：

```yaml
---
title: 笔记标题
topic: <topic>
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: stable        # 可选：stable | draft | disputed（仅在你想标记时写）
sources:              # 可选：关联的 raw 资料，相对路径
  - ../raw/xxx.md
---
```

- `status` 为**可选**字段，默认不写。仅当你想标记"草稿 / 有争议"时才加。
- `sources` 为可选，关联原始资料时填写，便于溯源。

---

## 2. 笔记正文建议结构

```markdown
# 标题

## 一句话总结
（用自己话概括核心）

## 核心概念
- ...

## 直觉 / 类比
（帮助理解的类比，老师模式下重点写）

## 常见误区
- ...

## 关联
- 相关笔记：[[其他笔记]]
- 原始资料：[[../raw/xxx]]
```

> 结构为建议，非强制。重点是**清晰、有直觉、标注误区**。

---

## 3. 主题总览 _overview.md（每个 topic 强制存在）

`wiki/<topic>/_overview.md` 内容建议：

```markdown
# <topic> 总览

## 这个主题是什么 / 学习目标
...

## 包含笔记
- [笔记名](note.md) — 一句话
- ...

## 知识脉络
（笔记之间的依赖 / 顺序）

## 未解问题
- ...
```

每次该主题新增或变更笔记，必须同步更新本文件。

---

## 4. 链接规范

- 笔记之间、笔记与 raw 之间使用**相对路径**互链，如 `[[../raw/xxx]]`、`[[llm/attention]]`。
- 目标写文件路径（不含扩展名或含 `.md` 均可，保持仓库内一致即可）。

---

## 5. 命名规范

- 笔记文件：小写中划线，`attention-mechanism.md`
- 主题目录：小写中划线，`llm`、`distributed-systems`
- 主题总览固定名：`_overview.md`
