---
title: GPU 执行模型
topic: cuda
tags: [gpu-programming, parallel-computing, hardware, simt]
summary: GPU 通过 kernel 启动一组线程（grid→block→thread 是软件组织方式），分配到物理计算单元 SM 上执行（SM 把 block 切成 warp，warp 内 32 线程锁步执行）。类比：kernel 是任务书，grid/block/thread 是排兵布阵，SM 是车间，warp 是车间流水线。
created: 2026-07-14
updated: 2026-07-14
---

# GPU 执行模型

## TL;DR

GPU 编程有两套层级：**软件侧**（grid→block→thread）是编程者组织线程的方式，**硬件侧**（GPU→SM→warp）是芯片实际执行的方式。Kernel 是跑在 GPU 上的函数，启动时创造一个 grid，GPU 把其中的 block 分配到 SM 上，SM 把 block 内线程按 32 个一组切成 warp 来执行。Block 是线程协作的边界（共享内存+同步），warp 是硬件调度的最小单位（SIMT 锁步执行）。

## 核心概念

### Kernel

Kernel 是一个跑在 GPU 上的函数。调用一次 kernel 不是执行一次，而是启动成千上万个线程**同时执行同一个函数体**，每个线程通过内置变量（`threadIdx`、`blockIdx`）知道自己处理哪一块数据。

```c
__global__ void add(float* a, float* b, float* c, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) c[i] = a[i] + b[i];
}
// 启动：<<<gridDim, blockDim>>>
add<<<40, 256>>>(a, b, c, n);  // 10240 个线程同时跑
```

### 软件层级：Grid → Block → Thread

启动 kernel 时创造：
- **Grid**：所有 block 的集合，整个工作的总称
- **Block**：线程的集合（不是 warp 的集合），编程者决定一个 block 含多少 thread
- **Thread**：最小执行单位

$$\text{total\_threads} = \text{gridDim} \times \text{blockDim}$$

每个线程的内置身份变量：
- `threadIdx` — 在 block 内的编号
- `blockIdx` — block 在 grid 内的编号
- `blockDim` — 每 block 线程数
- `gridDim` — block 总数

全局索引：$i = \text{blockIdx.x} \times \text{blockDim.x} + \text{threadIdx.x}$

### 硬件层级：GPU → SM → Warp

- **SM（Streaming Multiprocessor）**：GPU 芯片上一块独立计算单元，含几十个 CUDA core、寄存器、shared memory。一块 GPU 有几十个 SM
- **Warp**：SM 把 block 内线程按 **32 个一组**自动切成 warp。warp 是 SM 调度和执行的最小单位

$$\text{warps\_per\_block} = \lceil \text{blockDim} / 32 \rceil$$

### 两套层级如何对接

```
Grid
 ├─ Block 0  →  分配到 SM 0  →  切成 warp 逐个执行
 ├─ Block 1  →  分配到 SM 0  →  切成 warp 逐个执行
 ├─ Block 2  →  分配到 SM 1  →  切成 warp 逐个执行
 └─ ...

一个 block 只待在一个 SM 上，不会跨 SM 拆分
一个 SM 可同时驻留多个 block（只要资源够）
```

### Block 的本质：协作授权区

Block 不是多余的组织层级——它是**允许线程之间共享内存和同步的最小边界**。提供三个 warp/thread 无法提供的能力：

1. **共享内存（Shared Memory）**：一块片上高速 SRAM，只有同 block 内线程可访问
2. **同步（`__syncthreads()`）**：block 内所有线程可在此处等待齐步走；跨 block 无同步原语
3. **分工协作**：block 内线程可分工计算、结果汇总到 shared memory

没有 block，线程就是一群各干各的散兵；有了 block，一群线程才能组成协作小组。

### Warp 的双重特性：SIMT

**同一个 warp 内部**：32 个线程锁步执行，同一时钟周期跑完全相同的指令（SIMT — Single Instruction, Multiple Threads）。如果 32 个线程走了不同的 if/else 分支 → **warp divergence**，硬件被迫串行执行两个分支，性能腰斩。

**不同 warp 之间**：完全独立。SM 有 warp scheduler，可自由切换。warp 0 跑乘法、warp 1 跑加载、warp 2 等内存返回——互不干涉。

### Latency Hiding

当一个 warp 等显存数据（延迟几百周期），SM 不干等，立刻切到另一个就绪的 warp 继续跑。靠 warp 数量多来掩盖内存延迟，而非靠缓存。SM 上同时驻留的 warp 越多，能隐藏的延迟越多——这就是 occupancy 调优的意义。

SM 的执行能力分两层：
- **驻留**：SM 上同时住着的 warp 数，有架构上限（如 Volta/Ampere 64 个），受 block 资源占用（寄存器、shared memory）约束
- **发射**：每时钟周期实际选择几个 warp 执行指令，现代 SM 通常 4 个 warp scheduler，每周期最多发射 4 个 warp

### Shared Memory vs 显存

| | Shared Memory | 显存（Global Memory / VRAM） |
---|---|---|
 位置 | SM 芯片内部 SRAM | GPU 板卡 HBM/GDDR 芯片 |
 容量 | 几十 KB | 几十 GB |
 延迟 | 几十周期 | 几百周期 |
 可见性 | 同 block 内线程 | 所有线程 |

典型用法：线程先协作把数据从显存搬进 shared memory，之后反复读写都在 shared memory 里做，避免反复访问慢速显存。

### Block 大小约束

- **硬约束**：单 block 最多 1024 线程（架构相关）
- **软约束**：
  - 最好是 32 的倍数（填满 warp，不浪费）
  - 太小 → SM 上驻留 warp 不够，计算单元空转
  - 太大 → 单 block 占资源多，SM 能同时驻留的 block 数减少
- **经验值**：128、256、512，结合 kernel 的 shared memory 和寄存器用量调

## 直觉 / 类比

- **CPU vs GPU**：CPU 是少数几个超级高手，每个很强，擅长串行复杂任务；GPU 是成千上万个简单小兵，每个只能做简单运算，但胜在人多，适合大规模并行。
- **kernel 是任务书**：你写好一份操作手册（kernel），复印一万份发给一万个工人（线程），每人通过工号（threadIdx）知道自己处理哪块。
- **Block 是协作小组**：一个小组共享一块白板（shared memory），可以互相配合、同步进度。不同小组之间看不到对方的白板。
- **SM 是车间**：车间里有流水线（warp），一条流水线上 32 个工人同时做同一个动作。车间可以同时开多条流水线，一条卡住了就切另一条。

## 常见误区

- **"GPU 线程和 CPU 线程一样"** — 完全不同。GPU 线程极轻量、没有独立调度栈，靠硬件批量发射。
- **"block 是 warp 的集合"** — 不对。Block 是 thread 的集合，warp 是硬件拿到 block 后自动切出来的，编程者不直接操作 warp。
- **"block 越多越好"** — block 太多超出 SM 容量会排队，反而变慢。关键是 occupancy（SM 上实际驻留的 warp 数）。
- **"block 大小随便选"** — 不是 32 的倍数会有 warp 填不满浪费；太小 SM 驻留 warp 不够；太大挤占资源。要结合 kernel 的资源用量调。
- **"同一 block 内所有线程同时执行同一指令"** — 不对。只有同一 warp 内的 32 个线程锁步执行。不同 warp 之间独立调度，可以跑不同指令。SIMT 约束的是 warp 内部，不是 block 内部。

## 面试常见问题

- **Q**: 解释 SIMT 和 SIMD 的区别？
  **A**: SIMD（CPU 的 AVX 指令）是数据级并行——一条指令同时操作一个向量里的多个数据，程序员显式写向量代码。SIMT 是线程级并行——每个线程有自己的寄存器和程序计数器（逻辑上），硬件把 32 个线程打包成一个 warp 统一发射指令。SIMT 对程序员透明，写的是普通标量代码；SIMD 需要显式使用向量类型。不过当 warp 内所有线程走同一分支时，SIMT 在执行层面和 SIMD 效果相同。

- **Q**: warp divergence 是什么？怎么避免？
  **A**: 同一 warp 内 32 个线程如果走了不同的 if/else 分支，硬件必须串行执行两个分支，另一半线程空等。避免方法：尽量让同一 warp 内的线程走同一分支（数据排列时让相邻元素属于同一类别），或用 predicated execution 代替分支。但要注意，不是所有 if/else 都会 divergence——只有同一 warp 内线程走了不同分支才会。

- **Q**: 为什么选择 block 大小通常是 128 或 256？太小或太大会怎样？
  **A**: 32 的倍数保证 warp 填满不浪费。太小（如 32）导致 SM 上同时驻留的 warp 数不够，无法有效 latency hiding，计算单元空转。太大（如 1024）单 block 占用的寄存器和 shared memory 多，SM 能同时驻留的 block 数减少，总 warp 数可能反而下降。128/256 是多数 kernel 的甜点，但最终要看 occupancy 计算和实测。

- **Q**: shared memory 和 L1 cache 有什么关系？
  **A**: 在现代 NVIDIA 架构上（Fermi 之后），shared memory 和 L1 cache 共享同一块物理 SRAM，可通过 `cudaFuncSetAttribute` 配置比例。区别是 shared memory 由编程者显式管理（手动加载/同步），L1 cache 由硬件自动管理。shared memory 的优势是确定性好——你确切知道数据在哪、何时加载，适合有明确复用模式的数据访问。

## 关联

- [_overview.md](_overview.md) — CUDA / GPU 编程主题总览
- （待建）Triton — OpenAI 的 GPU kernel 编程语言，在 block-level 抽象上简化 CUDA 编程，是学本篇笔记的下游应用
- （待建）CUDA 内存层级 — 本篇涉及 shared memory vs global memory，更完整的内存层级（registers → L1 → L2 → HBM）待深入
