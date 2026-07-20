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

标题就是**概念名**，简洁、可扫。

**好的标题**：
- `Dropout`
- `Batch Normalization`
- `Attention Mechanism`

**差的标题**：
- `Dropout 笔记`（多余的"笔记"）
- `关于 BatchNorm 的一些理解`（啰嗦）
- `Dropout 通过随机丢弃神经元来防止过拟合`（把 summary 塞进了标题）

> 主旨和观点放在 `summary` 和 `TL;DR` 里，标题只负责让人一眼定位"这篇讲什么"。

---

## 3. Frontmatter（必填）

```yaml
---
title: Dropout
topic: deep-learning
tags: [regularization, overfitting, practical-tips]
summary: 训练时随机丢弃神经元，迫使网络不依赖特定节点，测试时所有权重乘以保留概率。类比：让团队里的每个人都能独当一面，而不是依赖某个明星员工。
created: 2026-07-13
updated: 2026-07-13
sources:
  - ../../raw/wiki/dropout-paper.pdf
---
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `title` | ✅ | 概念名，简洁、可扫。含 `:` `"` `#` 等特殊字符时整个值用双引号包裹（如 `title: "FlashAttention: ..."`），避免 YAML 解析失败 |
| `topic` | ✅ | 所属主题目录名（小写中划线） |
| `tags` | ✅ | YAML 数组，不加 `#` 前缀。用于跨主题发现——一篇笔记可以属于 `deep-learning` 主题但打上 `regularization` 和 `practical-tips` 标签 |
| `summary` | ✅ | 2-3 句话，包含核心定义 + 一个类比。这是给 agent 做 query 时快速扫描用的——agent 读 summaries 就能定位相关笔记，无需加载全文 |
| `description` | 可选 | 给网站/SEO 用的简短描述。未填时 Quartz 会 fallback 到 `summary` |
| `created` | ✅ | 创建日期 |
| `updated` | ✅ | 最后修改日期 |
| `sources` | 可选 | 关联的 raw 资料路径，有就填。注意：`raw/` 受 `.gitignore` 保护不进 git，跨机器需重新下载/clone，sources 链接仅本机有效 |
| `status` | 可选 | `draft`（草稿，lint 会提醒补完）或省略（默认视为完成） |

---

## 4. Topic 分配指南

当一篇笔记需要归属到某个 `topic` 时，按以下优先级判断：

### 原则一：topic 是浏览入口，tags 是安全网

topic 决定笔记放在哪个目录下；tags 负责跨主题发现。如果一篇笔记可能同时属于两个 topic，**选一个放，另一个打 tag**。

例：`Dropout` 是正则化技术也是深度学习训练技巧。放在 `deep-learning/`，打上 `[regularization, training]` 标签。

### 原则二：topic 不要太宽也不要太窄

- **太宽**（如 `machine-learning/` 下有 50 篇笔记）→ 浏览失去意义
- **太窄**（如 `dropout-variants/` 下只有 2 篇笔记）→ 不如合并到上级

一个 topic 下 3-15 篇笔记是比较健康的范围。超过这个范围时，lint 会提醒。

### 原则三：不确定时，先放再调

不需要在一开始就找到完美归属。先按直觉放，tags 保证能被找到。后续 topic 结构调整时，移动文件 + 更新 `index.md` 即可——成本很低。

---

## 5. Topic 结构会演化

**重分配是正常的，不是架构失败。** 随着笔记增长，一些 topic 会自然分裂，另一些会自然合并。以下操作都是低成本且鼓励的：

- 重命名 topic 目录 → `mv` + 更新所有相关笔记的 `topic` 字段
- 拆分一个大 topic → 新建目录 + 移动笔记 + 更新两边的 `index.md`
- 合并两个小 topic → `mv` + 合并 `index.md`
- 改变笔记的 topic → 移动文件 + 更新 `topic` 字段 + 调整 tags

lint 会定期检查 topic 健康度并给出建议，但它不会自动执行——结构变更由你决策。

---

## 6. 正文结构

```markdown
## TL;DR
（和 frontmatter 的 summary 相同或稍扩展，3-4 句。读者读完这一段就应该知道这篇笔记在说什么。）

## 核心概念
- 关键定义
- 工作原理（用图、伪代码辅助）
- **公式**：涉及公式的概念必须写出来，不能只描述。使用 LaTeX 数学格式（`$$...$$` 或 `$...$`）
- 与其他概念的区别

## 直觉 / 类比
（能让一个外行听懂的说法——"就像..."、"可以理解为..."）
（这是 learn skill 的"老师"角色最有价值的部分）

## 常见误区
- 初学者容易以为 X，实际上 Y
- 什么情况下这个类比会失效

## 面试常见问题

> 格式要点：Q、A、来源三者各自为**独立段落**，彼此之间必须**空一行**。不要写成"Q 行紧接着 A 行、中间无空行"——Markdown 会把软换行折叠成空格，渲染时 Q 和 A 会挤在同一行。列表项内换段落用"空行 + 2 空格缩进"保持归属同一列表项。

- **Q**: [面试题]

  **A**: [用自己的话回答]

  *来源：[平台] • [作者] • [链接]*

- **Q**: ...

## 关联
- [相关笔记 1](../topic/note1.md) — 什么关系
- [相关笔记 2](../topic/note2.md) — 什么关系
- 原始资料：[资料名](../../raw/wiki/xxx.md)
```

> 结构为建议，非强制。关键是**有自己的理解**，不是搬运原文。但 TL;DR、直觉类比、常见误区三者至少要有两个——缺了它们，笔记退化成了百科词条。

---

## 7. 好笔记 vs. 流水账

### 好笔记的特征
- 标题是简洁的概念名
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

## 8. 主题总览 index.md（每个 topic 强制存在）

```markdown
---
title: <topic> 总览
topic: <topic>
tags: [<topic>]
summary: <一句话概括这个主题>
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

## 这个主题是什么 / 学习目标
...

## 包含笔记
- [笔记名](note.md) — 一句话说明这篇笔记的核心内容

## 知识脉络
（笔记之间的依赖 / 推荐阅读顺序）

## 未解问题
- ...
```

每次该主题新增或变更笔记，必须同步更新本文件。

> `index.md` 会被 Quartz 识别为 folder note，访问 `/wiki/<topic>/` 时直接渲染该文件内容。

---

## 9. 链接规范

- 笔记之间使用**相对路径**互链：`[笔记名](../topic/note.md)`
- 链接旁必须说明**什么关系**，不要裸链接：
  - ✅ `[Dropout](../deep-learning/dropout.md) — 和 BatchNorm 一样是正则化手段，但作用机制不同`
  - ❌ `[Dropout](../deep-learning/dropout.md)`
- 不使用 Obsidian 风格的 `[[WikiLinks]]`，使用标准 Markdown 链接。

---

## 10. 命名规范

- 笔记文件：小写中划线，与标题对应。例：标题 `Attention Mechanism` → 文件名 `attention-mechanism.md`
- 主题目录：小写中划线，`deep-learning`
- 主题总览固定名：`index.md`
