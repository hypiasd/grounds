---
title: GPU 线程层级模型
topic: cuda
tags: [cuda, gpu, parallel-computing, hardware]
summary: GPU 编程有两套层级——软件侧 Grid/Block/Thread 组织线程，硬件侧 SM/CUDA Core 执行线程。Kernel 启动时创建 Grid，GPU 把 Block 分配到 SM，SM 把 Block 切成 Warp 执行。Block 是线程间共享内存和同步的协作边界。
created: 2026-07-14
updated: 2026-07-14
---

# GPU 线程层级模型

## TL;DR

GPU 编程有两套独立的层级体系：**软件侧**用 Grid → Block → Thread 组织线程，**硬件侧**用 GPU → SM → CUDA Core 执行线程。写 kernel 时你只管软件侧，GPU 负责把 block 分配到 SM 上执行。Block 是线程能共享内存和同步的最小边界——这是它存在的核心理由。

## 核心概念

### 两套层级

**软件侧（编程者组织的）**：

```
Grid（网格）
 └─ Block（线程块）    ← 你决定一个 block 多少 thread
     └─ Thread（线程）
```

**硬件侧（GPU 芯片上的物理结构）**：

```
GPU
 └─ SM（Streaming Multiprocessor）   ← 芯片上一个计算单元
     └─ CUDA Core（执行单元）
```

### Kernel

Kernel 是在 GPU 上执行的函数。用 `__global__` 标记，通过 `<<<gridDim, blockDim>>>` 启动：

```c
__global__ void add(float* a, float* b, float* c, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) c[i] = a[i] + b[i];
}
add<<<40, 256>>>(a, b, c, n);  // 40 个 block × 256 个 thread = 10240 线程
```

普通函数调用一次执行一次，kernel 调用一次启动成千上万个线程同时执行同一函数体，每个线程通过内置变量（`threadIdx`、`blockIdx`、`blockDim`、`gridDim`）知道自己处理哪一块数据。

### 总线程数

$$\text{total\_threads} = \text{gridDim} \times \text{blockDim}$$

### 两套如何对接

1. 你启动 kernel → 创造 1 个 Grid，内含多个 Block，每个 Block 内多个 Thread
2. GPU 把 Block 分配到 SM 上（一个 SM 可接收多个 block，一个 block 只待在一个 SM 上）
3. SM 把 Block 内的 Thread 按 32 个一组切成 Warp 来执行

```
Grid
 ├─ Block 0  →  分配到 SM 0  →  切成 warp 执行
 ├─ Block 1  →  分配到 SM 0  →  切成 warp 执行
 ├─ Block 2  →  分配到 SM 1  →  切成 warp 执行
 └─ ...
```

### Block 是协作边界

如果只有 thread 和 warp，线程之间无法协作。Block 给了三个 warp 没有的能力：

1. **共享内存（Shared Memory）** — 高速片上内存，只有同一 block 内线程可访问
2. **同步（`__syncthreads()`）** — block 内所有线程可在此等待齐步走；跨 block 无同步原语
3. **分工协作** — block 内线程可分工计算，结果汇总到 shared memory

一句话：**Thread 是干活的，Warp 是硬件调度的，Block 是允许线程共享内存和同步的最小边界。**

### Block 大小约束

- **硬约束**：单个 block 最多 1024 个线程（架构上限）
- **软约束**：
  - 最好是 32 的倍数（warp 按 32 切分，不整除浪费硬件资源）
  - 太小 → SM 上驻留 warp 不够，计算单元空转
  - 太大 → 单 block 占用 shared memory 和寄存器多，SM 能同时驻留的 block 数减少，降低 occupancy
- **经验值**：常见选 128、256、512，需结合 kernel 资源占用调优

## 直觉 / 类比

- **CPU 是超级高手**：少数核心，每个很强，擅长串行复杂任务
- **GPU 是一支军队**：成千上万个简单小兵（线程），每个只会简单运算，胜在人多
- **SM 是工厂车间**：GPU 芯片有几十个 SM，每个 SM 里有一组 CUDA core（机器）和共享资源
- **Block 是项目小组**：组内成员共享工具箱（shared memory）和同步协作，组与组之间互不干涉

## 常见误区

- **以为 GPU 线程和 CPU 线程是一回事** — GPU 线程极轻量、没有独立调度栈，靠硬件批量发射
- **以为 block 是 warp 的集合** — Block 是 thread 的集合，warp 是硬件自动切出来的，编程者从不直接操作 warp
- **以为 block 越多越好** — 太多超出 SM 容量排队变慢，太少计算单元空转；需要平衡 occupancy
- **以为 grid/block/warp/thread 在同一条链上** — SM 不在 Grid→Block→Thread 这条链里，它是 block 的宿主，负责接收和执行

## 面试常见问题

- **Q**: Block 为什么不能跨 SM 拆分？Block 是怎么被分配到 SM 上的？
  **A**: Block 的所有线程必须共享同一块 shared memory 并在同一 SM 上执行，才能用 `__syncthreads()` 做块内同步。跨 SM 拆分会导致 shared memory 不可访问、同步原语失效。分配策略：GPU 根据 SM 的资源（寄存器、shared memory）动态调度，一个 SM 可同时驻留多个 block，一个 block 只在一个 SM 上直到执行完毕。（来源：牛客网 CUDA/AI-infra 面经）
- **Q**: 解释 GPU 的线程层次结构，以及它们和硬件 SM 的映射关系
  **A**: 软件侧 Grid → Block → Thread 是编程者组织的层级，硬件侧 SM/CUDA Core 是物理执行单元。启动 kernel 时创建 Grid，GPU 把 Block 分配到 SM 上，SM 把 Block 内线程按 32 切成 Warp 执行。一个 SM 可同时驻留多个 Block，一个 Block 不跨 SM。

## 关联

- [Warp 与 SIMT](warp-and-simt.md) — Warp 是 SM 执行 block 内线程的方式，理解线程层级必须理解 warp
- [GPU 内存层级](gpu-memory-hierarchy.md) — Block 的协作能力来自共享内存，这是内存层级中的关键一环
