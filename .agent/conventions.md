# conventions.md — 笔记模板与规范

本文件定义仓库内所有 Markdown 内容的统一格式。每次写笔记前必须先读本文件。

---

## 1. 原子性原则

**一篇笔记只讲一个概念。** 如果你发现自己在笔记里写了"另外，还有一个相关的点是..."——那就是另一篇笔记。

原子性的好处：
- 链接更精准——"Dropout 和 BatchNorm 的关系"比"正则化技术（包含 Dropout、BatchNorm、L1/L2...）"更容易被精确引用
- 更新无副作用——改一篇笔记不会影响其他知识
- query 定位更准——agent 可以直接定位到具体概念，而不是在一篇大杂烩里翻找

> 来自 Andy Matuschak 的 evergreen notes 原则和 Zettelkasten 传统。

---

## 2. 标题规范

标题应该是**一个主张，不是一个主题名**。

**好的标题**（读完标题就知道这篇笔记的核心观点）：
- `Dropout 通过随机丢弃神经元来防止过拟合`
- `Batch Normalization 解决的是内部协变量偏移，不是梯度消失`

**差的标题**（读完不知道具体说什么）：
- `Dropout 笔记`
- `关于 Batch Normalization`

> 来自 Zettelkasten 的"declarative title"原则。

---

## 3. Frontmatter（必填）

```yaml
---
title: Dropout 通过随机丢弃神经元来防止过拟合
topic: deep-learning
tags: [regularization, overfitting, practical-tips]
summary: 训练时随机丢弃神经元，迫使网络不依赖特定节点，测试时所有权重乘以保留概率。类比：让团队里的每个人都能独当一面，而不是依赖某个明星员工。
created: 2026-07-13
updated: 2026-07-13
sources:
  - ../raw/dropout-paper.pdf
---
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `title` | ✅ | 一个主张，不是主题名 |
| `topic` | ✅ | 所属主题目录名（小写中划线） |
| `tags` | ✅ | YAML 数组，不加 `#` 前缀。用于跨主题发现——一篇笔记可以属于 `deep-learning` 主题但打上 `regularization` 和 `practical-tips` 标签 |
| `summary` | ✅ | 2-3 句话，包含核心定义 + 一个类比。这是给 agent 做 query 时快速扫描用的——agent 读 summaries 就能定位相关笔记，无需加载全文 |
| `created` | ✅ | 创建日期 |
| `updated` | ✅ | 最后修改日期 |
| `sources` | 可选 | 关联的 raw 资料路径，有就填 |
| `status` | 可选 | `draft`（草稿，lint 会提醒补完）或省略（默认视为完成） |

---

## 4. 正文结构

```markdown
# 标题（主张式）

## TL;DR
（和 frontmatter 的 summary 相同或稍扩展，3-4 句。读者读完这一段就应该知道这篇笔记在说什么。）

## 核心概念
- 关键定义
- 工作原理（用图、公式或伪代码辅助）
- 与其他概念的区别

## 直觉 / 类比
（能让一个外行听懂的说法——"就像..."、"可以理解为..."）
（这是 learn skill 的"老师"角色最有价值的部分）

## 常见误区
- 初学者容易以为 X，实际上 Y
- 什么情况下这个类比会失效

## 关联
- [相关笔记 1](../topic/note1.md) — 什么关系
- [相关笔记 2](../topic/note2.md) — 什么关系
- 原始资料：[资料名](../raw/xxx.md)
```

> 结构为建议，非强制。关键是**有自己的理解**，不是搬运原文。但 TL;DR、直觉类比、常见误区三者至少要有两个——缺了它们，笔记退化成了百科词条。

---

## 5. 好笔记 vs. 流水账

### 好笔记的特征
- 标题是一个主张，读完就知道核心观点
- TL;DR 用自己的话概括，不是复制定义
- 至少有一个直觉类比
- 标注了常见误区
- 与其他笔记建立了关联，且说明了**什么关系**（不是裸链接）
- tags 覆盖了 topic 之外的其他维度

### 流水账的特征
- 标题是主题名（"XX 笔记"）
- 只有定义和公式，没有自己的话
- 没有类比、没有误区、没有关联
- 读完和读 Wikipedia 没有区别
- 一篇笔记塞了多个概念（违反原子性）

> 写笔记前问自己：**三个月后回来看，这篇笔记能让我在 30 秒内 recall 核心理解吗？**

---

## 6. 主题总览 _overview.md（每个 topic 强制存在）

```markdown
# <topic> 总览

## 这个主题是什么 / 学习目标
...

## 包含笔记
- [笔记名](note.md) — 一句话说明这篇笔记的核心主张

## 知识脉络
（笔记之间的依赖 / 推荐阅读顺序）

## 未解问题
- ...
```

每次该主题新增或变更笔记，必须同步更新本文件。

---

## 7. 链接规范

- 笔记之间使用**相对路径**互链：`[笔记名](../topic/note.md)`
- 链接旁必须说明**什么关系**，不要裸链接：
  - ✅ `[Dropout](../deep-learning/dropout.md) — 和 BatchNorm 一样是正则化手段，但作用机制不同`
  - ❌ `[Dropout](../deep-learning/dropout.md)`
- 不使用 Obsidian 风格的 `[[WikiLinks]]`，使用标准 Markdown 链接。

---

## 8. 命名规范

- 笔记文件：小写中划线。从主张式标题中提取 3-5 个关键词作为文件名，不要求文件名和标题完全一致。例：标题"Dropout 通过随机丢弃神经元来防止过拟合"→ 文件名 `dropout-prevents-overfitting.md`
- 主题目录：小写中划线，`deep-learning`
- 主题总览固定名：`_overview.md`
