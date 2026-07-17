---
title: FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness
topic: llm
tags: [attention, gpu-optimization, io-aware, systems, long-context]
summary: FlashAttention 把"IO-aware"思想引入 attention 计算——通过 tiling 在 SRAM 内分块计算 + 反向重算避免 N² 中间矩阵落地 HBM，把精确 attention 的 HBM 访问从 Θ(Nd+N²) 降到 Θ(N²d²/M)，wall-clock 加速 2-3x 且内存省 10-20x。是 LLM 训练/推理的奠基性系统优化工作。
created: 2026-07-18
updated: 2026-07-18
sources:
  - ../../raw/papers/2205.14135.pdf
---

# FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness

## TL;DR

Transformer 自注意力的 O(N²) 复杂度让长序列训练又慢又费显存。已有近似注意力方法（sparse / low-rank）只盯 FLOP 减少，忽略 GPU 内存层次访问开销，wall-clock 没快。FlashAttention 反其道而行——**精确不近似**，通过 **tiling（分块）+ recomputation（反向重算）** 让 N×N 中间矩阵永不落地 HBM，把 HBM 访问从 Θ(Nd+N²) 降到 Θ(N²d²/M)，并证明对一定 SRAM 大小 M 范围是最优的。实测：BERT-large 15%、GPT-2 3×、LRA 2.4× 加速；GPT-2 perplexity -0.7；首次让 Transformer 在 Path-X (16K) / Path-256 (64K) 上高于随机。

## 论文信息

- **作者**：Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Ré
- **Venue**：NeurIPS 2022  **年份**：2022  **arxiv**：2205.14135
- **源文件**：[PDF](../../raw/papers/2205.14135.pdf)
- **官方代码**：https://github.com/HazyResearch/flash-attention
- **论文类型**：Systems + Empirical

## 研究背景与动机

**领域问题**：Transformer 的 self-attention 时间和内存复杂度都是 O(N²)，长序列训练瓶颈严重。

**现有方法不足**：
- Sparse attention（Reformer/Longformer）、Low-rank（Linformer/Performer）等方法把 FLOP 降到线性或近线性
- 但实测 wall-clock 没快——crossover 点通常在 512-1024 才出现，短序列反而被标准 attention 吊打
- 根本原因：**只关注 FLOP，忽略了 GPU 内存层次访问开销（IO）**。softmax、matmul 这些操作在 GPU 上是 memory-bound，FLOP 少不等于快

**本文动机**：把系统设计层面的 IO-awareness 引入 ML 算法—— attentive to reads/writes between HBM（慢、大）和 SRAM（快、小）。**反直觉的核心**：在 memory-bound 场景下，加 FLOP 反而可能加速。

## 核心方法

### 标准 Attention 的问题（Section 2.2）

给定 Q, K, V ∈ ℝ^{N×d}，标准实现把中间矩阵 S、P 物化到 HBM：

$$S = QK^\top \in \mathbb{R}^{N \times N}, \quad P = \text{softmax}(S) \in \mathbb{R}^{N \times N}, \quad O = PV \in \mathbb{R}^{N \times d}$$

- 内存：O(N²)
- HBM 访问：Θ(Nd + N²)，softmax 是 memory-bound，反复读写 N² 矩阵 = 慢

### FlashAttention 算法（Algorithm 1）

两个核心技术：

#### Tiling（分块）

把 Q/K/V 切成块，从 HBM 加载到 SRAM，分块算 attention。难点：softmax 跨整个序列耦合，不能直接分块。作者用 **block-softmax 代数分解**：

对向量 x ∈ ℝ^B：

$$m(x) := \max_i x_i, \quad f(x) := [e^{x_1 - m(x)}, \ldots, e^{x_B - m(x)}], \quad \ell(x) := \sum_i f(x)_i, \quad \text{softmax}(x) := \frac{f(x)}{\ell(x)}$$

对拼接 x = [x^(1), x^(2)] ∈ ℝ^{2B}：

$$m(x) = \max\bigl(m(x^{(1)}), m(x^{(2)})\bigr)$$

$$f(x) = \bigl[e^{m(x^{(1)}) - m(x)} f(x^{(1)}), \quad e^{m(x^{(2)}) - m(x)} f(x^{(2)})\bigr]$$

$$\ell(x) = e^{m(x^{(1)}) - m(x)} \ell(x^{(1)}) + e^{m(x^{(2)}) - m(x)} \ell(x^{(2)})$$

**关键洞察**：只要跟踪每行的 (m, ℓ) 统计量，新来一块 K/V 就能更新这两个值并 rescale 之前的累积输出 O。中间矩阵 S、P 永远不落地 HBM——只在 SRAM 内短暂存在。

#### Recomputation（反向重算）

反向传播通常需要 S, P ∈ ℝ^{N×N} 算梯度。FlashAttention **不存这两个矩阵**，只存输出 O 和 (m, ℓ)，反向时在 SRAM 内从 Q/K/V 块重算 S, P。

- 这是 **selective gradient checkpointing** 的一种形式
- 反直觉点：FLOPs 变多了（前向 + 反向各算一次 QK^T），但 HBM 访问少了，wall-clock 反而更快
- 经典 trade-off：**用算力换带宽**——memory-bound 场景下稳赚

#### Kernel Fusion

Tiling 让整个 attention（matmul → softmax → mask → dropout → matmul）能 fuse 进单个 CUDA kernel：HBM 读一次输入，所有计算在 SRAM 内流水，最后写一次输出。

### IO 复杂度（Theorem 2 / Proposition 3）

| 算法 | HBM 访问次数 |
|------|--------------|
| 标准 attention | Θ(Nd + N²) |
| FlashAttention | Θ(N²d² / M) |

其中 M 是 SRAM 大小，d ≤ M ≤ Nd。典型 d=64-128, M≈100KB（A100），d² 远小于 M，所以 FlashAttention 访问次数少一个数量级。

**下界（Proposition 3）**：不存在算法能在所有 M ∈ [d, Nd] 范围内做到 o(N²d²/M) HBM 访问——证明 FlashAttention 在该范围内最优。

### Block-Sparse 扩展（Section 3.3）

加 block-form mask M̃ ∈ {0,1}^{N×N}：

$$P = \text{softmax}(S \odot \tilde{M})$$

IO 复杂度按稀疏度比例下降：Θ(nnz(M̃) · d² / M)。这是论文从"精确加速"延伸到"近似加速"的桥梁。

## 实验设计与关键结果

### 速度对比（验证 IO-aware 比降 FLOP 更重要）

**Table 2（GPT-2 训练 wall-clock）**：vs Huggingface speedup 3.5×（small）/ 3.0×（medium）；vs Megatron-LM 1.7× / 1.7×。**PPL 完全一致**（18.2 / 14.3）——证明精确不近似。

**Table 3（LRA benchmark）**：FlashAttention 平均 speedup 2.4×；block-sparse FlashAttention 2.8×，超过所有近似方法（Linformer 2.5×、Linear Attention 2.3× 等）。

**Fig 3 左（runtime vs seq len）**：FlashAttention 比标准 attention 快 3×；与近似方法 crossover 在 512-1024；block-sparse 全程领先。

### 质量保持 + 长上下文红利

**Table 4（GPT-2 长上下文）**：FlashAttention 4K context 比 Megatron 1K context 还快 30%，且 PPL 从 18.2 降到 17.5（-0.7）。

**Table 5（长文档分类 micro-F1）**：MIMIC-III 从 512 长度的 52.8 提升到 16K 的 57.1；ECtHR 从 72.2 提升到 8K 的 80.7。

**Table 6（Path-X / Path-256）**：**首次**让 Transformer 在这两个长序列任务上高于随机（50%）——FlashAttention 在 Path-X (seq=16K) 达 61.4%；block-sparse 在 Path-256 (seq=64K) 达 63.1%。所有近似方法全是随机水平。

### 消融

**Fig 2 左**：FlashAttention FLOPs（75.2 GFLOPs）比标准（66.6 GFLOPs）**反而更多**——因反向重算；但 HBM 访问 4.4 GB vs 40.3 GB（少 9×），wall-clock 7.3 ms vs 41.7 ms（快 6×）。这是 "FLOP ≠ wall-clock" 的最直接证据。

**Fig 2 中**：block size 增大 → HBM 访问减少 → runtime 减少；但超过 256 后被算力瓶颈接管，且塞不进 SRAM。

## 创新点与贡献

1. **IO-aware exact attention**：首个把 GPU 内存层次建模纳入 attention 算法设计，且**不近似**——数学上与标准 attention 等价（Theorem 1）
2. **IO 复杂度理论**：证明 Θ(N²d²/M) 优于标准 Θ(Nd+N²)，并对 M ∈ [d, Nd] 给出下界（Proposition 3）
3. **Block-sparse 扩展**：把精确加速延伸到近似加速，IO 按稀疏度线性下降
4. **长序列新能力解锁**：Path-X / Path-256 首次高于随机——证明"更快"能带来"做不到的事"

## 局限与改进方向

- **必须写新 CUDA kernel**：每种新 attention 变体都要手写 CUDA，工程量大且不可跨架构移植（Limitations Section 5 第 1 点）。后来 Triton / flash-attn 的 high-level 接口在缓解这个问题
- **只测 A100 GPU**：跨架构验证缺失。后续 v2/v3 扩展到 H100 / Hopper
- **下界只对 M subrange 成立**：Proposition 3 只覆盖 M ∈ [d, Nd]，作者明说"参数化复杂度下界"是 future work
- **Path-X 单 seed**：Table 6 没报告方差，61.4% 是否稳态存疑（后来 v2 论文里复测过）
- **未涉及推理场景**：v1 只测训练。推理（KV cache、PagedAttention）是另一套问题，后来由 vLLM/PagedAttention 接棒
- **多 GPU IO-aware 未触及**：作者明确说是 future direction（Section 5 第 3 点）

## 方法论评估

| 维度 | 评分 | 简评 |
|------|------|------|
| Soundness | 5/5 | Theorem 1-3 数学证明严谨，block-softmax 代数恒等式正确 |
| Novelty | 5/5 | 首次把 IO-aware 引入 attention；tiling + recomputation 组合在 attention 场景是新的 |
| Reproducibility | 4/5 | 开源代码完整，但 CUDA kernel 复现门槛高；论文算法描述清晰 |
| Experimental Design | 5/5 | 速度/质量/长序列能力三层论证，消融完整 |
| Statistical Rigor | 3/5 | Path-X 单 seed，无方差报告；其他实验多 seed |
| Scalability | 5/5 | 跨序列长度 128-64K 全覆盖，理论与实测一致 |

## 我的批判性思考

**最关键的 claim**：FlashAttention 是**精确**的（Theorem 1）。证据充分——block-softmax 代数恒等式 + Table 2 PPL 与 baseline 完全一致。这个 claim 决定了 FlashAttention 不是又一个近似方法，而是替代标准 attention 的"工程升级"。

**复现最容易踩的坑**：
1. **block size 选择**：B_c = ⌈4M/d⌉, B_r = min(⌈4M/d⌉, d)。B_r 在 d 大时取 d 而非 4M/d，容易被忽略
2. **数值稳定性**：m 更新时如果旧 m_new 比 m̃_ij 小很多，e^{m̃_ij - m_new} 会爆；反之 e^{m_i - m_new} 会下溢。实现里要注意 m 始终是 rowmax
3. **反向重算的 RNG**：dropout mask 必须可重现（用 same RNG seed），否则前向反向 mask 不一致导致梯度错误
4. **head dim 限制**：v1 在 d > 128 时性能下降（SRAM 装不下），v2/v3 才优化了大 d 场景

**和已学知识的关系**：FlashAttention 是后续所有 LLM 训练/推理栈的底层组件。它的核心思想"用算力换带宽、tile 在 SRAM 内计算"正是 [Triton](../../wiki/cuda/triton.md) 这类块级 GPU 编程范式的典型应用场景——Triton 让 IO-aware kernel 不必再手写 CUDA。同系列后续工作：FlashAttention-2 (Dao 2023, 优化并行度)、FlashAttention-3 (2024, for Hopper, FP8/TMA)。

## 关联

- **相关 wiki 笔记（单向引用）**：[Triton](../../wiki/cuda/triton.md) — Triton 的块级编程模型正是 FlashAttention 类 IO-aware kernel 的高层语言实现路径，缓解了 v1 论文 Limitations 第 1 点（必须手写 CUDA）的痛点
- **同期/后续工作**：
  - FlashAttention-2 (Dao, 2023, arXiv:2307.08691)：优化并行度，沿 seq 维度切分
  - FlashAttention-3 (2024, for Hopper)：用 TMA + FP8，比 v2 在 H100 上再快 1.5-2×
  - PagedAttention / vLLM (2023)：推理场景的 KV cache 内存管理，与 FlashAttention 互补
  - Triton (OpenAI)：让 IO-aware kernel 能用 Python 级语言写，缓解 v1 的 CUDA 门槛问题
