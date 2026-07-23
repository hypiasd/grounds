---
title: Roofline 模型与算术强度
topic: gpu
tags: [gpu, roofline, arithmetic-intensity, bandwidth, benchmark]
summary: 算术强度 AI=FLOPs/Bytes 决定 GEMM 是带宽游戏还是算力游戏；Roofline 性能上限=min(算力上限, 带宽上限×AI)，拐点是两者相等处。decode（低 AI）带宽受限、prefill（高 AI）算力受限。
created: 2026-07-23
updated: 2026-07-23
---

## TL;DR

GEMM 快慢不能只看 FLOPs。算术强度 `AI = FLOPs / Bytes` 才是关键：AI 低 → 瓶颈在 HBM 带宽（带宽游戏），AI 高 → 瓶颈在算力（算力游戏）。Roofline 把两者画成一条「屋顶线」，性能上限 = min(算力天花板, 带宽×AI)。

## 核心概念

### 1. 两套账：计算量 vs 访存量

- **FLOPs（计算量）** = `2·M·N·K`（每输出元素 K 次乘加，共 M·N 个输出）。
- **Bytes（访存量）** = `(M·K + K·N + M·N) · elem_bytes`（A + B + C，fp32=4B）。好分块下每个元素只读/写一次。

### 2. 算术强度 AI = FLOPs / Bytes

- 单位 **FLOP/Byte**：每从 HBM 搬 1 字节能做几次运算。
- **decode**（小 M、大 K=N）：C 极小、A/B 巨大 → 搬多算少 → **低 AI → 带宽受限**。
- **prefill**（大 M）：→ **高 AI → 算力受限**。
- 这正是「权重量化只救 decode、不救 prefill」的机理根：量化减半字节，只帮低 AI 的 decode 摊薄访存。

### 3. Roofline 模型

- 性能上限 = **min(算力上限, 带宽上限 × AI)**。
- **拐点 `AI* = 算力上限 / 带宽上限`**：AI < AI\* 时带宽封顶（性能 = 带宽×AI），AI > AI\* 时算力封顶。
- 例 T4：算力 ~8.1 TFLOPS、HBM ~320 GB/s → `AI* ≈ 25` FLOP/Byte。4090D：~165 TFLOPS / ~1008 GB/s → `AI* ≈ 164`。

### 4. 实测指标怎么算

- `sec`：GPU kernel 异步发射，须 `torch.cuda.synchronize()` 包住计时，多跑取均值。
- `GB/s = Bytes / sec / 1e9`（实际带宽，越近峰值越好）。
- `TFLOPS = FLOPs / sec / 1e12`（实际算力，越近峰值越好）。
- **单位链**：`GB/s × (FLOP/Byte) = 1e9 Byte/s × FLOP/Byte = 1e9 FLOP/s = GFLOP/s` → 带宽×AI = 性能上限（斜线）。

### 5. 怎么读一张 roofline 图

- 每个形状有点 `(AI, 实测 TFLOPS)`；屋顶 = `min(算力天花板, 带宽×AI)`。
- 点离屋顶越近越好；远在下方 = kernel 没喂饱硬件 → 有优化空间。
- **块大小是强杠杆**：大 BLOCK = 更多片上复用 + 更高 SM 占用率 → 同形状下 TFLOPS 可差数倍；但受 shared memory 上限约束（如 T4 64KB，BLOCK=128 的 fp32 双 Tile 放不下）。

## 直觉 / 类比

搬砖模型：GEMM = 工人(SM)用砖(A,B)砌墙(C)。带宽是卡车运砖的路宽，算力是工人手速。AI 低（砖堆远、每次只搬几块）→ 工人老等车 → 瓶颈在路（带宽）；AI 高（砖在手边、一次搬一大摞）→ 工人砌不过来 → 瓶颈在手速（算力）。量化 = 砖做小一半，一趟多运一倍 → 只帮等车的人。

## 常见误区

- **误区：FLOPs 少就快。** 错——decode GEMM FLOPs 远小于 prefill，却更带宽受限、更易慢。
- **误区：AI 是 kernel 属性。** AI 由形状+精度决定（题设），与 kernel 质量无关；GB/s、TFLOPS 才是 kernel 实测。
- **误区：带宽够就快。** 算力受限形状（高 AI）下，带宽再宽也救不了——受算力天花板锁死。

## 面试常见问题

- **Q**：为什么量化只加速 decode 不加速 prefill？

  **A**：decode AI 低（带宽受限），减半字节直接降流量 → 加速；prefill AI 高（算力受限），字节已摊薄，减半字节碰不到带宽墙、救不了算力天花板。

- **Q**：怎么判断一个 GEMM kernel 还有多少优化空间？

  **A**：量实际 GB/s、TFLOPS，画到 roofline 上，看离屋顶多远；再扫 block 大小看 occupancy/复用收益，查 shared mem 是否够放更大 tile。

## 关联

- [HBM 流量与数据复用](hbm-traffic.md) — 带宽游戏的本质（复用压低流量）
- [分块 GEMM 的原理与切法](../gemm/tiled-gemm.md) — 分块如何提升复用 / AI
- [Triton matmul 拆解](../cuda/triton-matmul.md) — 同一个 kernel 怎么写、怎么读
- 项目实践：vllm-plus 路径 A·M1/M2（`project_logs/vllm-plus/runbook.md` 节点 17/18）
