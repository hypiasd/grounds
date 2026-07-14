---
title: GPU 内存层级
topic: cuda
tags: [cuda, gpu, memory, performance]
summary: GPU 有三层内存：寄存器（最快、线程私有）、共享内存（快、小、block 内可见）、显存（大、慢、全局可见）。共享内存是 SM 内 SRAM 不是显存，速度差一个数量级。核心优化是把数据从显存搬进共享内存，在 block 内反复读写。
created: 2026-07-14
updated: 2026-07-14
---

# GPU 内存层级

## TL;DR

GPU 内存分三层：寄存器（最快、线程私有）、共享内存（快、小、block 内可见）、显存（大、慢、全局可见）。共享内存不是显存——它在 SM 芯片内部的 SRAM，延迟比 HBM/GDDR 显存低一个数量级。核心优化：数据从显存搬进共享内存后在 block 内反复读写，避免重复慢速访存。

## 核心概念

### 三层内存

| 层级 | 位置 | 容量 | 延迟 | 可见性 |
|------|------|------|------|--------|
| 寄存器 | SM 内 | 每线程几十个 | ~1 周期 | 线程私有 |
| 共享内存 | SM 内 | ~几十 KB/SM | ~几十周期 | block 内可见 |
| 显存 | GPU 板卡 | 几十 GB | ~几百周期 | 全局可见 |

```
GPU 板卡
├─ 显存（HBM/GDDR）
└─ SM 芯片
    ├─ 寄存器
    ├─ 共享内存
    └─ CUDA Cores
```

### 共享内存 vs 显存

- **显存（Global Memory）**：GPU 板卡上 HBM/GDDR，容量大（几十 GB），全局可见，延迟高（几百周期）。`cudaMalloc` 分配的就是显存
- **共享内存（Shared Memory）**：SM 芯片内部 SRAM，极小（几十 KB/SM），仅 block 内可见，延迟低（几十周期），比显存快一个数量级

### 核心优化模式

先把数据从慢速显存搬进共享内存，之后反复读写都在共享内存里：

```
__shared__ float tile[32][32];
tile[ty][tx] = A[row * N + col];    // 协作加载到共享内存
__syncthreads();                     // 等所有线程加载完
// 在 tile 上做计算
```

这是 GEMM tiling 优化的核心思想，也是 NVIDIA 面试高频考点。

### 其他内存类型

- **常量内存（Constant Memory）**：只读、全 GPU 可见、有专用 cache，适合所有线程读同一常量
- **本地内存（Local Memory）**：寄存器溢出时使用，实际在显存中，速度慢——是性能悬崖

## 直觉 / 类比

- **显存像仓库**：容量大但远，每次取东西要很久
- **共享内存像工位旁工具箱**：容量小但近，同一 block 的人共用
- **寄存器像你的口袋**：最快但只能放很少东西，只你自己能用

## 常见误区

- 以为共享内存是显存——它是 SM 内 SRAM，和板卡上 HBM/GDDR 是完全不同的物理介质，速度差一个数量级
- 以为所有线程都能访问共享内存——仅同 block 内线程可访问
- 以为 shared memory 越多用越好——占用太多会减少 SM 能同时驻留的 block 数，降低 occupancy。存在一个 sweet spot

## 面试常见问题

- **Q**: shared memory 和 global memory 有什么区别？什么时候用 shared memory 反而不如不用？
  **A**: Shared memory 在 SM 内（SRAM、几十 KB、几十周期、block 内可见），global memory 在板卡上（HBM/GDDR、几十 GB、几百周期、全局可见）。不是银弹：数据只读一次（无复用）时搬到 shared memory 的开销（加载 + `__syncthreads()`）反而拖慢性能。最适合同一 block 线程反复读写同一块数据的场景，如矩阵乘法的 tile。（来源：Stack Overflow、NVIDIA 开发者论坛）
- **Q**: GPU 有哪几种内存？从快到慢排序，分别适合什么场景？
  **A**: 寄存器 > 共享内存 > 常量内存 > 全局内存 > 本地内存。寄存器存临时变量；共享内存存 tile、缓存 block 内共享数据；常量内存存所有线程读的同一常量；全局内存存主数据；本地内存是寄存器溢出时的后备（在显存中、慢）。牛客网 C++/CUDA 面经高频题。（来源：牛客网 CUDA/AI-infra 面经）
- **Q**: GEMM tiling 优化中 shared memory 扮演什么角色？
  **A**: 朴素矩阵乘法每个线程从 global memory 重复读取数据，大量访存浪费。Tiling 将矩阵分小块（tile）加载到 shared memory，block 内所有线程共享 tile，大幅减少 global memory 访问次数。Shared memory 是 tiling 的物理载体——没有它就没有 tiling。NVIDIA 面试经典 deep-dive：optimize CUDA GEMM with tiling and coalescing。（来源：prachub.com NVIDIA Interview Question）

## 关联

- [GPU 线程层级模型](gpu-thread-hierarchy.md) — 共享内存的可见范围就是 block
- [Warp 与 SIMT](warp-and-simt.md) — Latency hiding 掩盖的就是访问 global memory 的高延迟
