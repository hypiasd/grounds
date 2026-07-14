---
title: GPU 执行模型
topic: cuda
tags: [cuda, gpu, parallel-computing, hardware, memory, performance]
summary: GPU 执行模型有三面相：线程层级（Grid/Block/Thread 软件体系 + SM/CUDA Core 硬件体系）、Warp/SIMT（32 线程锁步执行、warp divergence、latency hiding）、内存层级（寄存器/共享内存/显存）。三者互咬——block 的协作边界是 shared memory，warp 的延迟隐藏掩盖的是显存延迟。
created: 2026-07-14
updated: 2026-07-14
---

# GPU 执行模型

## TL;DR

GPU 执行模型是三个互相咬合的面相：**线程层级**告诉你谁在跑（软件 Grid/Block/Thread 对接硬件 SM/CUDA Core），**Warp/SIMT** 告诉你怎么跑（32 线程锁步、分支发散、延迟隐藏），**内存层级**告诉你数据在哪（寄存器/共享内存/显存，速度差百倍）。三者不能孤立理解——block 存在是为了共享内存和同步，warp 的 latency hiding 掩盖的正是显存的慢。

## 一、线程层级：软件与硬件的对接

### 两套体系

- **软件侧（编程者组织）**：Grid → Block → Thread。你决定 grid 里多少 block、每 block 多少 thread
- **硬件侧（GPU 芯片物理结构）**：GPU → SM（Streaming Multiprocessor）→ CUDA Core

### Kernel 启动

```
__global__ void add(float* a, float* b, float* c, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) c[i] = a[i] + b[i];
}
add<<<40, 256>>>(a, b, c, n);  // 40 block x 256 thread = 10240 threads
```

总线程数：$\text{total} = \text{gridDim} \times \text{blockDim}$。每个线程通过内置变量 `threadIdx`、`blockIdx`、`blockDim`、`gridDim` 知道自己处理哪块数据。

### 对接流程

1. 启动 kernel → 创建 Grid（内含 N 个 Block，每 Block 内含 M 个 Thread）
2. GPU 把 Block 分配到 SM。一个 SM 可接收多个 block，一个 block 不跨 SM
3. SM 把 block 内线程按 32 一组切成 Warp 来执行

### Block 存在的理由

如果只有 thread 和 warp，线程间无法协作。Block 给了三个能力：**共享内存**（block 内线程共用高速 SRAM）、**同步**（`__syncthreads()`，跨 block 无此原语）、**分工**（协作加载、汇总）。一句话：block 是线程共享内存和同步的最小边界。

### Block 大小约束

- 硬上限 1024 线程；最好 32 的倍数（warp 按 32 切）；太小浪费 SM 资源，太大挤占 shared memory/寄存器降低 occupancy
- 经验值：128、256、512

## 二、Warp 与 SIMT：硬件怎么跑

### Warp 是什么

GPU 不逐个线程执行——把 block 内线程按 **32 个一组**打包成 warp，SM 一次发射一个 warp 的指令。同一 warp 内 32 线程同时跑同一条指令，这就是 SIMT（Single Instruction, Multiple Threads）。

$\text{warps\_per\_block} = \lceil \text{blockDim} / 32 \rceil$

### SIMT vs SIMD

SIMD（CPU 向量指令）要求程序员显式打包数据。SIMT 硬件自动管理线程，每个线程逻辑上有独立执行路径——但同 warp 内走不同分支时硬件仍串行化。SIMT 更灵活但有 warp divergence 代价。

### Warp Divergence

同一 warp 内线程走不同 if/else 分支 → 硬件串行执行各分支，性能腰斩。如果是 8 路分支，吞吐砍到 1/8。

缓解方法：让分支条件 warp 对齐（以 32 为粒度划分数据），用 `select`/`fmaxf` 消除分支。Attention 的 mask 用乘法不用 `if`。

### Latency Hiding

一个 warp 等显存（几百周期），SM 立刻切到另一个就绪 warp。驻留 warp 越多，能掩盖的延迟越多。GPU 靠人海战术掩盖延迟，不是靠缓存——和 CPU 思路完全不同。

### 驻留 vs 发射

- **驻留**：SM 上住着多少 warp。架构上限 A100 = 64，实际取决于寄存器/shared memory 占用 → occupancy
- **发射**：每周期实际选几个 warp 执行。现代 SM 有 4 个 warp scheduler，每周期最多 4 个

## 三、内存层级：数据在哪

### 三层结构

| 层级 | 位置 | 容量 | 延迟 | 可见性 |
|------|------|------|------|--------|
| 寄存器 | SM 内 | 每线程几十个 | ~1 周期 | 线程私有 |
| 共享内存 | SM 内 | ~几十 KB/SM | ~几十周期 | block 内 |
| 显存 | GPU 板卡 | 几十 GB | ~几百周期 | 全局 |

### 共享内存 ≠ 显存

共享内存是 SM 内 SRAM，延迟 ~几十周期。显存是板卡上 HBM/GDDR，延迟 ~几百周期。`cudaMalloc` 分配的是显存，`__shared__` 声明的是共享内存。两者是不同的物理介质，速度差一个数量级。

### 核心优化模式

数据从显存搬进共享内存，block 内反复读写——避免重复慢速访存。这是矩阵乘法 tiling 优化的本质：

```
__shared__ float tile[32][32];
tile[ty][tx] = A[row * N + col];   // 协作加载
__syncthreads();
// 在 tile 上计算
```

### 其他内存类型

- **常量内存**：只读、全局可见、有专用 cache，适合所有线程读同一常量
- **本地内存**：寄存器溢出时使用，实际在显存中——是性能悬崖
- **Bank conflict**：共享内存分 32 个 bank（每个 4 bytes），同 warp 多线程访问同一 bank 的不同地址时串行化。访问同一地址时可广播，不冲突

## 直觉 / 类比

- CPU 是特种兵（少而精），GPU 是军队（人多力量大）
- SM 是工厂车间，Block 是项目小组（共享工具箱），Warp 是流水线（一次同时加工 32 个）
- 显存像仓库（大而远），共享内存像工位旁工具箱（小而近），寄存器像口袋（最快但极小）
- Latency hiding：一条流水线等料就切另一条，车间永远在转

## 常见误区

- GPU 线程 ≠ CPU 线程 —— GPU 线程极轻量、无独立调度栈、靠硬件批量发射
- Block 不是 warp 的集合 —— block 是 thread 集合，warp 是硬件自动切的
- Block 内不同 warp 可以执行不同指令 —— SIMT 约束 warp 内部，不是 block 内部
- 共享内存不是显存 —— 是 SM 内 SRAM，物理介质完全不同
- Latency hiding 不是靠缓存 —— 靠 warp 切换，GPU 和 CPU 思路相反
- Shared memory 不是越多越好 —— 占用太多降低 occupancy

## 面试常见问题

- **Q**: 讲一下 GPU 的执行模型——Grid、Block、Warp、Thread 的关系，以及它们和 SM 的映射？
  **A**: Grid→Block→Thread 是软件侧；SM 是硬件侧。启动 kernel 创建 Grid，GPU 把 Block 分配到 SM，SM 按 32 切 Block 为 Warp 执行。一个 SM 可驻留多个 Block，一个 Block 不跨 SM。Block 存在是因为它提供了 shared memory 和 `__syncthreads()` 的协作边界。（NVIDIA 面试必问，来源：oavoservice.com）
- **Q**: 什么是 warp divergence？怎么避免？
  **A**: 同 warp 内线程走不同分支时硬件串行执行。避免：分支条件 warp 对齐（以 32 为粒度）、用 `select`/`fmaxf` 消除分支。Attention 的 mask 用乘法不用 if。（来源：quant67.com、techinterview.org）
- **Q**: shared memory 和 global memory 区别？shared memory 是不是银弹？
  **A**: Shared memory 在 SM 内 SRAM（几十周期），global memory 在板卡 HBM（几百周期），速度差一个数量级。不是银弹——数据只用一次时搬到 shared memory 的开销反而不如直接用 global memory。（来源：Stack Overflow、NVIDIA 开发者论坛）
- **Q**: GPU 如何掩盖内存延迟？需要多少 warp？
  **A**: 靠多 warp 驻留切换（latency hiding），不是缓存。经验公式：warps ≈ mem_latency / (instruction_time × arithmetic_intensity)。SM 上 warp 不够 → occupancy 低 → 隐藏不了延迟。（来源：UC Berkeley Latency Hiding 论文）
- **Q**: `__syncthreads()` 是做什么的？跨 block 同步怎么办？
  **A**: Block 内同步——等 block 内所有线程都到达该点再继续。跨 block 没有直接同步原语，一般通过 kernel 结束（隐式全局同步）或 CUDA stream 实现。SM 90+ 的 thread block cluster 支持 `cluster.sync()` 跨 block 同步。（来源：CSDN CUDA 面试题精讲）

## 关联

- 前置：无（本笔记是 GPU 编程的起点）
- 后续：Triton（待学）—— 如何在更高抽象层写 GPU kernel
