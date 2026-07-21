---
title: "Stanford CS336 Language Modeling from Scratch | Spring 2026 | Lecture 6: Kernels, Triton, XLA"
topic: video
tags: [video]
summary: "视频笔记 — Stanford Online"
published: 2026-07-22
video_url: "https://www.youtube.com/watch?v=xnDHaNUvHBg"
video_channel: "Stanford Online"
video_duration: "86分40秒"
sources:
  - Stanford CS336 Language Modeling from Scratch - Spring 2026 - Lecture 6- Kernels, Triton, XLA.pdf
---

## 课程概览与议程

本讲由 Percy Liang 主讲，承接上一讲对 GPU/TPU 硬件的介绍，进入 ``如何实际写出高性能 kernel'' 的工程世界。Percy 在开场把本讲目标拆成三块：

1. **Review**：回顾 GPU 编程模型（thread、warp、block、SM、内存层次）。
2. **Benchmark \& Profile**：用正确方法测量性能，定位瓶颈。
3. **Write kernels**：从手写 CUDA 的直觉出发，用 Triton 在 Python 中写高效 kernel，并理解编译器（torch.compile / XLA）在背后做什么。

[图：figures/seg5_3300.jpg — 见 PDF]
*本讲议程：从 GPU 回顾到 benchmark、profiling，再到 Triton kernel 实例*

*视频画面时间区间：00:54:00--00:56:00。*

> **[重要]** **本讲核心主张**
> 要写出高性能 GPU kernel，必须同时掌握两层抽象：
>
> - **编程模型**（PyTorch / Triton / PTX）：保证正确性。
> - **硬件模型**（SM、warp、occupancy、bank conflicts）：榨取性能。
>
> 只有两者结合，才能理解为什么 naive 实现慢、builtin 快、compiled kernel 有时候反而比 builtin 慢。

### 本章小结
本讲从 ``会用 PyTorch'' 推进到 ``理解 kernel 为什么快''，核心工具链是：benchmark → profile → fuse/tile/optimize → Triton 实现。

## GPU 回顾：Thread、Warp、Block、SM 与内存层次

### 执行模型

CUDA / GPU 编程模型的层级：

- **Thread**：最细粒度，每个线程执行 kernel 的一份实例。
- **Warp**：32 个线程，GPU 调度的基本单位；同一 warp 内的线程执行 SIMT。
- **Block**：若干 warp 的集合；block 内线程可通过 shared memory 通信与同步。
- **SM（Streaming Multiprocessor）**：block 被调度到某个 SM 上执行；一个 SM 可同时驻留多个 block/warp。

[图：figures/seg1_420.jpg — 见 PDF]
*Thread block 与 warp 的组织：为什么需要 block？因为非逐点运算（softmax、matmul）需要通信与 shared memory*

*视频画面时间区间：00:05:00--00:08:00。*

> **[注意]** **Warp divergence**
> 同一 warp 内若线程进入不同分支，GPU 会串行执行各分支，导致部分线程空转。写 kernel 时应尽量让同一 warp 内线程走同一路径。

### 内存层次与带宽差距

现代 GPU 的内存层次形成巨大带宽梯度：

[图：figures/opening_120.jpg — 见 PDF]
*A100 / H100 / B200 的内存层次与带宽规格：HBM 是瓶颈*

*视频画面时间区间：00:01:30--00:02:30。*

从表中可见：

- Register / shared memory 带宽可达数十 TB/s。
- L2 cache 带宽约 5--12 TB/s。
- HBM 带宽仅 2--8 TB/s，是最窄的脖子。

> **[重要]** **优化的第一性原理**
> **减少 HBM 读写**。要么把数据复用次数提高（tiling），要么让多个运算在一次 HBM 访问中完成（fusion）。

### Occupancy 与 Bank Conflicts

- **Occupancy**：SM 上活跃 warp 数占最大可驻留 warp 数的比例。足够高的 occupancy 才能用计算掩盖内存延迟。
- **Shared memory bank conflicts**：shared memory 被分成 32 个 bank；若同一 warp 的多个线程同时访问同一 bank（不同地址），访问会串行化。

[图：figures/seg2_900.jpg — 见 PDF]
*Occupancy 计算示例与 shared memory bank conflicts*

*视频画面时间区间：00:13:30--00:16:00。*

> **[知识]** **Register 压力**
> 每个 SM 的 register file 有限。若每个线程用太多寄存器，SM 能同时驻留的线程/ warp 数下降，occupancy 降低。因此 kernel 中临时变量和 tile size 不能任意大。

### 本章小结
GPU 性能来自 ``高并发线程 + 低延迟共享内存 + 数据复用''。理解 thread/warp/block 的组织、内存带宽梯度和 occupancy 限制，是手写或调优 kernel 的前提。

## 性能分析：Benchmarking 与 Profiling

### 正确测量 GPU 时间

GPU 是异步设备，直接用 Python `time.time()` 会包含 CPU 开销和 launch 延迟。正确做法：

- 使用 `torch.cuda.Event(enable\_timing=True)` 记录 GPU 时间。
- 调用 `torch.cuda.synchronize()` 确保所有 kernel 完成再读时间。
- 做 warm-up，排除 lazy compilation 和 cache cold-start。
- 多次 trial 取平均，观察方差。

[图：figures/seg3_1500.jpg — 见 PDF]
*用 CUDA event 准确测量 kernel 执行时间*

*视频画面时间区间：00:24:00--00:27:00。*

### Profiling 定位瓶颈

PyTorch profiler 可以显示：

- 每个 kernel 的 GPU 耗时。
- CPU 端 launch overhead。
- 内存访问模式（是否 memory-bound）。

[图：figures/xla_2040.jpg — 见 PDF]
*Profiler 视角：naive GeLU 为什么慢？因为启动多次 kernel 且大量时间花在同步与 activity buffer*

*视频画面时间区间：00:33:30--00:35:00。*

> **[注意]** **测量即优化**
> 讲者强调：``先 profile，再优化''。不要凭直觉猜瓶颈；profile 会告诉你时间花在哪里（HBM 读写、kernel launch、同步、CPU 开销等）。

### 本章小结
准确的 benchmark 和 profiler 是系统优化的眼睛。没有测量，优化就是盲打。

## Naive、Builtin 与 Compiled：优化来自哪里

### GeLU 案例分析

以一个简单的 `y = x * gelu(x)` 为例，三种实现：

1. **Naive**：用 Python 逐元素写，生成多个 PyTorch 算子调用。
2. **Builtin**：调用 PyTorch 的 `nn.functional.gelu`，底层是优化的 CUDA kernel。
3. **Compiled**：用 `torch.compile`（背后是 Inductor + Triton / XLA）把多个操作融合成一个 kernel。

table[H]

tabular{lll}

**实现** & **时间** & **关键差异**

naive & 3.76 ms & 多次 HBM 读写 + 多次 kernel launch

builtin & 0.67 ms & 单一向量化 kernel

compiled & 0.94 ms & 一个 Triton kernel，但可能比 builtin 略慢

tabular
GeLU 三种实现耗时对比
table

> **[重要]** **Compiled kernel 为什么不一定最快？**
> `torch.compile` 的优势来自 **跨算子融合**。对于单个已经高度优化的 builtin GeLU，编译器生成的 Triton kernel 可能不如手写 CUDA kernel 精细。但当算子链较长、融合空间大时，compiled 版本会显著胜出。

### 编译器视角：图级别优化

`torch.compile` / XLA 会：

- 把 eager 模式下的多个算子拼接成计算图。
- 做算子融合、死代码消除、布局优化。
- 最终生成单个或少量 Triton / CUDA kernel。

> **[知识]** **Triton vs XLA**
> - **Triton**：OpenAI 开发的 Python DSL，让你以 block 为粒度写 kernel，编译到 PTX。
> - **XLA**：Google 的线性代数编译器，接收完整计算图并做全局优化（JAX / TensorFlow 用得多）。
> - **torch.compile** 默认后端 Inductor 主要生成 Triton kernel。

### 本章小结
Builtin 算子是手写 CUDA 的巅峰；编译器则把 ``图级别优化'' 自动化。Triton 介于两者之间：比 CUDA 更易写，又比 compiler 更可控。

## Triton 编程模型

### 为什么用 Triton

手写 CUDA 需要处理：

- thread、warp、block 索引。
- shared memory 分配与同步。
- bank conflicts、coalescing、occupancy。

Triton 把这些抽象成 ``一个 block 处理一个 tile''，让你 focus 在算法而不是硬件细节。

[图：figures/seg4_2700.jpg — 见 PDF]
*Triton GeLU kernel：以 block 为粒度处理输入 tile*

*视频画面时间区间：00:44:00--00:46:00。*

### 核心 API

- `tl.program\_id(axis)`：当前 block 的坐标。
- `tl.arange(start, end)`：生成 block 内线程的索引。
- `tl.load(ptr, mask=...)`：带 mask 的向量加载。
- `tl.store(ptr, value, mask=...)`：带 mask 的向量存储。

```
@triton.jit
def triton_gelu_kernel(x_ptr, y_ptr, num_elements, BLOCK_SIZE: tl.constexpr):
    pid = tl.program_id(axis=0)
    start = pid * BLOCK_SIZE
    offsets = start + tl.arange(0, BLOCK_SIZE)
    mask = offsets < num_elements
    x = tl.load(x_ptr + offsets, mask=mask)
    y = x * gelu(x)  # elementwise
    tl.store(y_ptr + offsets, y, mask=mask)
```

> **[重要]** **Triton 的抽象层级**
> Triton 让你以 **block** 为单位思考，而不是以 thread 为单位。编译器再把 block 映射到 CUDA thread、warp 和 shared memory。这大大降低了手写 kernel 的认知负担。

### 本章小结
Triton 用 ``block = tile'' 的抽象屏蔽了 CUDA 的 thread 级细节，同时保留了对内存访问模式和 tiling 的控制。

## Triton 实例：Softmax、Row Sum 与 Reduction

### Reduction 与 shared memory

当运算不是逐点的（如 softmax、row sum），一个 block 内需要 reduction。Triton 提供：

- `tl.sum(x, axis=...)`：warp/block 级求和。
- `tl.max(x, axis=...)`：warp/block 级取最大。

[图：figures/probe_4160.jpg — 见 PDF]
*Triton row\_sum kernel：把一行分成多个 tile，累加后再规约*

*视频画面时间区间：01:09:00--01:11:00。*

### Softmax 的两种情形

1. **行能放进一个 block**：直接在一个 block 内做 `max`、`exp`、`sum`、归一化。
2. **行太大**：需要分多个 block 先算局部 max/sum，再用 online softmax 合并。

> **[知识]** **Online softmax**
> 对于跨多个 tile 的 softmax，需要维护 ``当前最大值 $m$'' 和 ``归一化因子 $d$''。合并新 tile 时按 `new\_m = max(m, tile\_m)` 更新，避免二次扫描。这正是 Flash Attention 的核心技巧。

### 本章小结
Reduction kernel 的关键是正确处理 warp/block 级通信和跨 tile 状态。Triton 的 `tl.sum` / `tl.max` 隐藏了底层 shuffle 与 shared memory 同步。

## 矩阵乘法与 Tiling

### Naive Matmul 的瓶颈

计算 $C = A B$ 的 naive 方式：对每个输出元素 $C[m,n]$，遍历 $k$ 读取 $A[m,k]$ 和 $B[k,n]$，乘累加后写回。

- 运算强度为 $O(1)$：每个输出只做 $K$ 次乘法，但要读 $2K$ 个元素。
- 完全 memory-bound。

[图：figures/seg7_4500.jpg — 见 PDF]
*矩阵乘法 kernel 的 naive 与 tiling 思路*

*视频画面时间区间：01:14:00--01:16:00。*

### Tiling Matmul

把 $A$、$B$、$C$ 分成小 tile：

1. 把 $A$ 的一个行 tile 和 $B$ 的一个列 tile 加载到 shared memory。
2. 在 shared memory 内完成该 tile 的乘累加。
3. 沿 $K$ 方向滑动 tile，累加部分和。
4. 最终把结果 tile 写回 $C$。

> **[重要]** **Tiling 的收益**
> - 每个输入元素被复用 $tile\_size$ 次。
> - 运算强度从 $O(1)$ 提升到 $O(tile\_size)$。
> - 当 tile 足够大时，kernel 从 memory-bound 转为 compute-bound。

### 本章小结
矩阵乘法是深度学习最重要的 kernel。Tiling 把 $O(N^3)$ 计算与 $O(N^2)$ 数据的比值提高，是 cuBLAS 和 Triton matmul 性能的来源。

## 总结与延伸

### 讲者总结

课程结尾，Percy 回到议程图，把本讲提炼成一句话：

[图：figures/seg8_4980.jpg — 见 PDF]
*课程总结：掌握编程模型与硬件模型，才能写出好 kernel*

*视频画面时间区间：01:22:30--01:24:00。*

1. **Know the programming model**（PyTorch / Triton / PTX）：先保证正确。
2. **Understand the hardware**（SMs、warps、occupancy、bank conflicts）：再优化性能。
3. **Benchmark \& profile**：用数据驱动优化。
4. **Triton 思维方式**：read to shared memory → do stuff（fusion） → write back to HBM。

### 我的综合

本讲是上一讲 GPU 硬件的 ``下游''：硬件特性决定了软件优化方向。Percy 用 GeLU、softmax、row sum、matmul 四个例子展示了从 naive 到 Triton 的演进路径。核心思想始终如一：

> **[重要]** **Kernel 优化的三条主线**
> 1. **融合（fusion）**：减少 kernel 数量和 HBM 往返。
> 2. **Tiling**：提高数据复用，提升运算强度。
> 3. **匹配硬件**：合并访问、避免 bank conflicts、保持足够 occupancy。

### 拓展阅读

- Triton 官方文档：<https://triton-lang.org/main/index.html>
- PyTorch torch.compile 深度解析：<https://pytorch.org/tutorials/intermediate/torch_compile_tutorial.html>
- CUDA Mode 社区：<https://discord.gg/cuda-mode>
- ``How to Optimize a CUDA Matmul Kernel''（cuda-mode 系列博客）
