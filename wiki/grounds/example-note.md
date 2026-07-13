---
title: Attention Mechanism
topic: grounds
tags: [example]
summary: 注意力机制让模型在处理每个 token 时动态关注输入的不同位置，核心是 Query-Key-Value 的加权求和。类比查字典：你要查的词是 Query，书脊标签是 Key，书的内容是 Value。但这个类比在 Self-Attention 上失效——所有词同时互为 Query 和 Key。
created: 2026-07-13
updated: 2026-07-13
---

# Attention Mechanism

## TL;DR

注意力机制（Attention）让模型在处理序列时动态决定"关注哪些位置"，而不是把所有位置同等对待。核心操作是 Query 和 Key 算相似度，用这个相似度对 Value 加权求和。它的关键突破是解决了长序列的信息瓶颈——在此之前，RNN 要把整个输入压缩成一个固定长度的向量。

## 核心概念

- **Query（查询）**：当前要处理的目标——"我在找什么"
- **Key（键）**：序列中每个位置的标识——"我是什么"
- **Value（值）**：每个位置实际携带的信息——"我有什么"
- **Attention Score**：Query 和 Key 的匹配度，决定"关注多少"
- **Weighted Sum**：按 Score 对 Value 加权求和，得到输出

Self-Attention 是特例：Q、K、V 来自同一个序列，让序列内部的词互相"看见"。

## 直觉 / 类比

**查字典**：你要查一个词（Query），扫过书脊标签（Key），找到匹配后取出内容（Value）。你的注意力不是均匀分布在所有词条上。

**鸡尾酒会**：在嘈杂的房间里，你能"调高"对话对象的音量（关注相关词），同时"调低"其他人的音量（忽略无关词）。

**类比失效的边界**：字典类比只在 Cross-Attention 下成立（Query 和 Key 来自不同序列）。Self-Attention 中所有词同时互为 Query 和 Key——字典条目会随着你的查询动作动态变化，这不再是"查字典"，而是所有条目在互相定义。

## 常见误区

- **误区**："Attention 是 Transformer 发明的"。实际上 Bahdanau et al. (2015) 在 RNN Seq2Seq 中首先引入。Transformer 的贡献是**去掉 RNN，全靠 Attention**。
- **误区**："Multi-Head Attention 就是多做几次取平均"。每个 Head 在不同的投影子空间工作（各自的 W_Q、W_K、W_V），学到的依赖类型不同（语法 vs. 语义 vs. 位置），拼接后才完整。
- **误区**："Attention Score 越高越好"。Score 只表示相关性，不是正确性。模型可能高度关注一个不相关的 token——这正是训练要修正的。

## 关联

- （后续学习 Transformer、Self-Attention 后可互链，说明具体关系）
- （如有论文 PDF 放入 raw/，可在此链接）
