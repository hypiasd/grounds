---
title: vllm-plus 决策记录（ADR embryo）
tags: [project, vllm-plus]
created: 2026-07-21
updated: 2026-07-21
---
# vllm-plus 决策记录（ADR embryo）

> 从 git 提交记录 + `experiment_results.md` 提炼的**已落地决策**。每条带实测依据；不确定的标「待确认」。
> 非最终 ADR 格式，先沉淀，后续可结构化。

---

## D1 — KV cache INT8 量化：保留（显存优化，吞吐中性）

- **背景**：能否用 INT8 存 KV 省显存且提速？
- **决策**：保留 INT8 KV 量化（fused dequant attention），作为**显存优化手段**。
- **依据**：本卡上 attention 非瓶颈、GPU 富余，KV 量化**对解码吞吐无提升**；但显存占用 42%→28%。
- **取舍**：吞吐中性换约 1/3 显存，长上下文/高并发场景收益明显。
- 来源：`b945e25 feat(kv): INT8 KV-cache quantization`、`experiment_results.md`

## D2 — 权重量化 W8A8/INT8：放弃，回归 BF16

- **背景**：权重 INT8 能否像 KV 那样省显存+提速？
- **决策**：**不上**，回归 BF16。
- **依据**：`b963fc8` 实测"权重量化在本卡无吞吐收益"——RTX 5090 是计算密集型卡，FP8/INT8 路径反而有转换开销。
- **适用边界**：该结论针对本卡（sm_120）；在老卡/带宽受限卡上结论可能相反（待确认）。

## D3 — KV watermark（vLLM 式）：开启

- **背景**：并发高时频繁 preempt 导致吞吐抖动。
- **决策**：开启 KV watermark，预留少量块防 preempt 抖动。
- **依据**：`76379a7` 引入；接受约 6% 显存开销换取调度稳定性。`043121b` 修复 `watermark_blocks` 在 wm>0 时向下取整为 0 的边界 bug。
- **取舍**：小幅显存换稳定性，默认开。

## D4 — CPU swap 抢占：支持，按需开启

- **背景**：超出 KV 容量时如何不丢请求？
- **决策**：实现 KV swap 到 CPU 的抢占机制，默认支持、按需开启。
- **依据**：`779fdfe` 实验8——长序列/高并发下 swap 保吞吐有效；但**单请求 swap 不划算**。
- **取舍**：吞吐换可行性，适合容量触顶场景。

## D5 — 投机解码：走"无损"路线（禁用贪心回退近似）

- **背景**：投机解码如何保证输出与自回归一致？
- **决策**：Ngram/Prompt Lookup 投机 + 动态树 + 自适应 K；**为保无损禁用 vLLM 的贪心回退近似**，改用 CUDA graph verify。
- **依据**：`e7fdd79`（training-free 投机：Lookahead/Jacobi + 动态树 + 自适应 K + 无损拒绝采样）、`59d224a`（CUDA graph verify）、`509d757`（lookahead 无损性修复全过程）。
- **取舍**：放弃 vLLM 那种"近似加速但有损"的捷径，换取严格无损；高并发/低算占下才有效，单请求无效。

## D6 — 基座选型：nano-vllm（教学版 vLLM）

- **背景**：从零写还是基于现有最小实现？
- **决策**：基于 nano-vllm（连续批处理/分页 KV/CPU 卸载已内建），在其上做优化实验而非重写。
- **依据**：最小化"造引擎"成本，把精力放在优化手段本身；见 `config.py` 与各 engine 模块。
