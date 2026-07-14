---
title: Warp 与 SIMT
topic: cuda
tags: [cuda, gpu, hardware, performance]
summary: Warp 是 GPU 硬件调度的最小单位，32 个线程锁步执行相同指令（SIMT 模型）。不是编程者创造的——SM 拿到 block 后自动按 32 切分 warp。Warp divergence 让分支串行执行致性能腰斩，latency hiding 靠多 warp 驻留掩盖内存延迟。
created: 2026-07-14
updated: 2026-07-14
---

# Warp 与 SIMT

## TL;DR

Warp 是 32 个线程的集合，是 SM 硬件调度的最小单位。同一 warp 内 32 个线程锁步执行相同指令（SIMT），不同 warp 之间完全独立。Warp divergence 导致分支串行执行，性能腰斩。Latency hiding 靠 SM 上驻留多个 warp 掩盖内存延迟——GPU 不是靠缓存，是靠人多。

## 核心概念

### Warp 的定义

GPU 不逐个线程执行，而是把 block 内线程按 **32 个一组**打包成 warp。SM 一次发射一个 warp 的指令，同一 warp 内 32 个线程在同一时钟周期执行**完全相同的指令**——这就是 SIMT（Single Instruction, Multiple Threads）。

$$\text{warps\_per\_block} = \lceil \text{blockDim} / 32 \rceil$$

你定义 block 放 256 个 thread，GPU 自动切成 8 个 warp 逐个执行。

### SIMT vs SIMD

SIMD（CPU 向量指令）要求程序员显式打包数据到向量寄存器，所有元素走同一分支。SIMT（GPU warp）硬件自动管理线程，每个线程表面有独立执行路径——但同一 warp 内走不同分支时硬件仍串行化。SIMT 比 SIMD 更灵活但有 warp divergence 代价。

### SIMT 约束范围

- **同一 warp 内**：32 个线程锁步，同一时刻跑同一条指令
- **不同 warp 之间**：完全独立，SM 的 warp scheduler 自由切换

### Warp Divergence

同一 warp 内线程走不同分支时，硬件被迫串行执行：

```
if (threadIdx.x < 16) { /* 前 16 个执行，后 16 个空转 */ }
else                   { /* 后 16 个执行，前 16 个空转 */ }
```

**缓解方法**：让分支条件以 warp 粒度对齐（按 `threadIdx / 32` 判断），或重构算法避免同一 warp 内出现分支。

### Latency Hiding

当一个 warp 等显存数据（延迟几百周期），SM 切到另一个就绪 warp 继续跑。驻留 warp 越多，能掩盖的延迟越多——GPU 思路是"人多力量大"，不是 CPU 的"给每个人好装备"。

### 驻留 vs 发射

- **驻留（Resident）**：SM 上同时住着多少 warp。架构上限 Volta/Ampere=64，实际取决于 block 占用资源——资源越多能塞下的 warp 越少，即 **occupancy 越低**
- **发射（Issue）**：SM 每周期实际选几个 warp 执行。现代 SM 通常 4 个 warp scheduler，每周期最多发射 4 个 warp

## 直觉 / 类比

- **Warp 像一列火车**：32 节车厢绑在一起走，一半要左一半要右——火车只能先走一边再走另一边（warp divergence）
- **SM 像多轨道调度站**：一条轨道堵了就切另一条，保持总有人在跑（latency hiding）

## 常见误区

- 以为 warp 是编程者定义的——Warp 是硬件自动切分，编程者只管 block 大小
- 以为 block 内不同 warp 不能执行不同指令——可以，SIMT 约束 warp 内部不是 block 内部
- 以为 latency hiding 靠缓存——GPU 靠多 warp 切换，和 CPU 大缓存思路不同
- 以为驻留 warp 数等于发射 warp 数——驻留是住着多少，发射是每周期跑几个

## 面试常见问题

- **Q**: 什么是 warp divergence？怎么缓解？
  **A**: 同一 warp 内线程走不同 if/else 分支时硬件串行执行导致性能下降。缓解：让分支条件 warp 对齐（以 32 为粒度划分数据），或重构算法避免 warp 内分支。NVIDIA 面试高频题，常要求"walk through warp divergence and how to mitigate it"。（来源：techinterview.org NVIDIA 面经）
- **Q**: SIMD 和 SIMT 的本质区别？
  **A**: SIMD 要求程序员显式打包数据到向量寄存器，所有数据走同一分支。SIMT 硬件自动管理线程，每个线程可走不同分支——但同 warp 内仍串行化。SIMT 更灵活但受 warp divergence 影响。（来源：牛客网 CUDA/AI-infra 面经）
- **Q**: GPU 如何掩盖内存延迟？和 CPU 有什么不同？
  **A**: GPU 靠大量 warp 驻留切换（latency hiding），一个 warp 等内存时切到另一个。CPU 靠多级缓存减少延迟。GPU 靠人多，CPU 靠装备好。需要隐藏给定延迟的 warp 数经验公式：`warps ≈ mem_latency / (instruction_time × arithmetic_intensity)`。（来源：UC Berkeley Understanding Latency Hiding on GPUs）

## 关联

- [GPU 线程层级模型](gpu-thread-hierarchy.md) — Warp 是 SM 执行 block 内线程的方式
- [GPU 内存层级](gpu-memory-hierarchy.md) — Latency hiding 掩盖的就是访问显存的高延迟
