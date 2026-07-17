---
title: llm 论文总览
topic: llm
tags: [llm]
summary: 大语言模型相关论文笔记，覆盖训练/推理加速、注意力优化、长上下文等方向。
created: 2026-07-18
updated: 2026-07-18
---

## 这个主题是什么 / 收录范围

收录与大语言模型（LLM）直接相关的论文：训练/推理系统优化、注意力机制改进、长上下文方法、KV cache 管理等。

收录原则：以"对 LLM 训练或推理栈有实际影响"为标准——纯模型架构论文（如 GPT/Llama）若不涉及系统/算法-系统协同设计，暂不收录。

## 包含论文

- [FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness](FlashAttention.md) — 把 IO-aware 思想引入 attention 计算，tiling + 反向重算让精确 attention 的 HBM 访问从 Θ(Nd+N²) 降到 Θ(N²d²/M)，是 LLM 训练/推理栈的奠基性系统优化

## 阅读脉络

- **FlashAttention v1 (2022)** → v2 (2023, 优化并行度) → v3 (2024, for Hopper, TMA + FP8)：同系列演化路径
- **FlashAttention（训练场景）** ↔ **PagedAttention / vLLM（推理场景）**：互补关系，前者优化 attention kernel 本身，后者优化 KV cache 内存管理
- **FlashAttention v1 Limitations（必须手写 CUDA）** → **Triton**（高层语言方案，见 [wiki/cuda/triton.md](../../wiki/cuda/triton.md)）

## 未读 / 待补

- FlashAttention-2 (Dao, 2023, arXiv:2307.08691)
- FlashAttention-3 (2024, for Hopper)
- PagedAttention / vLLM (2023, arXiv:2309.06180)
- Attention Is All You Need (Vaswani et al., 2017, arXiv:1706.03762) — 标准 attention 的源头
