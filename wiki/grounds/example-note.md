---
title: 示例笔记：注意力机制
topic: grounds
created: 2026-07-13
updated: 2026-07-13
---

# 注意力机制（Attention Mechanism）

## 一句话总结

注意力机制让模型在处理每个 token 时，动态地"关注"输入序列中不同位置的信息，而不是把所有位置同等对待。核心思想是：**不是所有输入都同样重要，模型应该学会"看哪里"**。

## 核心概念

- **Query（查询）**：当前要处理的目标——"我在找什么"
- **Key（键）**：输入序列中每个位置的标识——"我是什么"
- **Value（值）**：每个位置实际携带的信息——"我有什么内容"
- **Attention Score**：Query 和每个 Key 的匹配度，决定"关注多少"
- **Weighted Sum**：按 Attention Score 对 Value 加权求和，得到最终输出

## 直觉 / 类比

想象你在图书馆找一本书（Query），你扫过书架上的书脊标签（Key），发现目标后取出那本书读内容（Value）。你的目光不是均匀扫过所有书架——你对匹配的区域停留更久。这就是 Attention。

另一个类比：在嘈杂的鸡尾酒会上，你能"调高"你对话对象的"音量"（关注）同时"调低"其他人的音量——这就是 Self-Attention 在做的事：在一串 token 中，让相关的 token 之间"互相听见"。

## 常见误区

- **误区 1**："Attention 是 Transformer 发明的"。实际上，Attention 最早在 Bahdanau et al. (2015) 的 RNN Seq2Seq 模型中引入，用于解决长序列的编码瓶颈。Transformer 的贡献是**只用 Attention，去掉 RNN**。
- **误区 2**："Attention Score 越高越好"。Score 的高低只是表示"相关性"，不是"正确性"。一个 token 可能高度关注另一个不相关的 token（学到了错误的关联），这正是模型需要训练的原因。
- **误区 3**："Multi-Head Attention 就是多做几次 Attention 取平均"。不是简单平均——每个 Head 在不同的投影子空间做 Attention，然后拼接。不同 Head 可以学到不同类型的依赖（语法 vs. 语义 vs. 位置）。

## 关联

- 相关笔记：（目前为空仓库，后续学习 Transformer、Self-Attention 后可在此互链）
- 原始资料：（如有论文 PDF 放入 raw/，可在此链接）
