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

---

## 6. Skill 编写规范（.agent/skills/ 下每个文件）

参考 Anthropic Agent Skills 规范与社区最佳实践，每个 skill 必须包含以下结构，且**约束目标而非死板步骤**：

- **frontmatter**：
  - `name`：小写中划线，唯一。
  - `description`：**写给模型看的触发条件**，不是功能摘要。用"用户说 X / 当 Y 时触发"的句式，带口语关键词；并写明"不要在 … 时用"（负面排除）。
  - `disable-model-invocation: true`：本仓库 skill 均有副作用（写文件 / commit），统一设为仅用户手动触发。
  - `allowed-tools`：声明所需工具（如 `Read, Write, Edit, Bash`），最小权限。
- **正文结构**：
  1. `## 何时用（触发）`：列用户原话 / 场景。
  2. `## 目标（完成时仓库应处于的状态）`：定义完成标准（Definition of Done）。
  3. `## 流程`：步骤，但只约束**目标**，不过度规定顺序；必须含一步 **校验**（写入后 `wc -l` 确认非空、`git status` 确认改动、检查链接可解析）。
  4. `## Gotchas（真实踩过的坑）`：记录实际踩过的坑并随失败持续迭代——这是最高信号量的部分。
  5. `## 注意`：边界与关联。
- **不要**：把 description 写成功能摘要；重复 Claude 已懂的通用知识；写死后不再适用的固定步骤顺序。
