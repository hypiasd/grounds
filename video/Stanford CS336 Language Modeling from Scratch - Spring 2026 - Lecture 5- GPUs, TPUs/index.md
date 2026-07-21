---
title: "Stanford CS336 Language Modeling from Scratch | Spring 2026 | Lecture 5: GPUs, TPUs"
topic: video
tags: [video]
summary: "视频笔记 — Stanford Online"
published: 2026-07-22
video_url: "https://www.youtube.com/watch?v=izZba4UA7iY"
video_channel: "Stanford Online"
video_duration: "78分39秒"
sources:
  - Stanford CS336 Language Modeling from Scratch - Spring 2026 - Lecture 5- GPUs, TPUs.pdf
---

## 课程概览与资源

本讲由 Tatsunori Hashimoto 主讲，是 CS336 从 ``神经网络基础'' 转向 ``系统与工程'' 的第一课。Hashimoto 在开场时指出，系统部分与前面的模型课程不同：它更 ``合理''（reasonable）——你可以通过一步步的逻辑推导得到结论，但初次接触 GPU 时它又像 ``魔法'' 又像 ``奇怪的设备''。本讲目标正是揭开 GPU 的面纱，让你理解它为何这样设计，以及如何让矩阵乘法、注意力等 ML 工作负载在其上跑得更快。

> **[知识]** **推荐资源**
> 讲者特别推荐了三个社区资源，适合课后深入：
>
> - **Horace He's blog（``Thonk From First Principles''）**：从零第一性原理讲 ML 系统。
> - **CUDA Mode**：读书群和社区，聚焦 CUDA 与 GPU 内核。
> - **``How to Scale Your Model'' / scaling-book**：讲者强调这是 ``一本现在同时覆盖 TPU 与 GPU 的书''，是理解 scaling 的极佳资料。

[图：figures/seg_1_mid_150.jpg — 见 PDF]
*本讲推荐的学习资源与社区*

*视频画面时间区间：00:00:00--00:05:00。*

### 本章小结
本章定位了课程结构：从模型进入系统，核心议题是 GPU/TPU 硬件、内存墙、以及围绕 ``减少内存访问'' 展开的优化技术。

## GPU 硬件解剖：SM、Warp、Thread 与内存层次

### 从 CPU 到 GPU 的设计哲学

GPU 最初为图形渲染设计，后来被 repurposed 用于深度学习。图形管线天然并行：每个像素可以独立计算，因此 GPU 把大量晶体管用于 ``计算'' 而非 ``控制逻辑'' 或 ``缓存''。这与 CPU 形成鲜明对比：CPU 追求单线程低延迟，有复杂的分支预测、乱序执行和大缓存；GPU 追求高吞吐，愿意让许多线程同时停滞来隐藏内存延迟。

> **[重要]** **GPU 的核心设计哲学**
> GPU 是 **吞吐优先（throughput-oriented）** 的处理器。它通过 **大量轻量线程 + SIMD 执行 + 层次化高速内存** 来掩盖延迟，而不是像 CPU 那样用复杂控制逻辑减少单次延迟。

### 执行模型：Thread、Block、Warp、SM

CUDA 程序由 kernel 发起，每个 kernel 被划分为大量线程（thread）。线程按 32 个一组组织成 **warp**，warp 是 GPU 调度的基本单位。多个 warp 组成一个 **block**，一个 block 内的线程可以共享 **shared memory** 并同步。一个 block 被分配到某个 **Streaming Multiprocessor（SM）** 上执行。

[图：figures/gpu_execution_model_945.jpg — 见 PDF]
*CUDA 执行模型：thread、warp、block 与 SM 的关系*

*视频画面时间区间：00:15:30--00:16:00。*

关键要点：

- **SIMT**：同一 warp 内的线程执行同一条指令，但操作不同数据。这是 SIMD 的线程级表现。
- **warp divergence**：如果线程走不同分支，GPU 会串行执行各分支，导致部分线程空闲。
- **block 内共享内存**：shared memory 位于 SM 内部，延迟远低于全局内存。

### 内存层次与延迟

GPU 的内存层次与 CPU 类似，但距离更近、延迟差距更极端：

table[H]

tabular{lll}

**内存类型** & **位置** & **特征**

Global memory（HBM/DRAM） & GPU 芯片外部 & 容量大、带宽高、延迟高

L2 cache & 芯片上 & 比 HBM 快数倍

L1 cache / Shared memory & SM 内部 & 延迟最低、由程序员控制

Register file & SM 内部 & 每个线程私有、速度最快

tabular
GPU 内存层次
table

[图：figures/seg_2_mid_660.jpg — 见 PDF]
*GPU 内存解剖：越靠近 SM 的内存越快*

*视频画面时间区间：00:10:00--00:12:00。*

> **[知识]** **SRAM vs DRAM**
> 讲者强调：**SRAM（shared/cache memory）比 DRAM（global memory）贵约 100 倍，但速度快约 8 倍**。因此 GPU 只有少量 SRAM，却极度依赖它来缓解内存墙。

### 本章小结
GPU 通过 ``大量线程 + SIMT + 层次内存'' 换取高吞吐。理解 thread/warp/block/SM 的组织和内存延迟差距，是后续所有优化的基础。

## GPU vs TPU：两种加速器哲学

### 架构对比

GPU 和 TPU 都是为矩阵运算优化的加速器，但设计哲学不同：

- **GPU**：大量 SM（如 H100 有 132 个），每个 SM 有少量 Tensor Core；控制逻辑较重，通用性强。
- **TPU**：少量大矩阵乘法单元（MXU，如 TPU v5p 只有 2 个 Tensor Core），控制轻量；内存（VMEM）更大，专为 matmul 流水线优化。

[图：figures/seg_3_mid_1170.jpg — 见 PDF]
*GPU 与 TPU 的核心结构对比*

*视频画面时间区间：00:17:30--00:20:00。*

> **[重要]** **GPU vs TPU 的本质差异**
> - **GPU**：**更多控制、更多通用性、更多小核心**。适合不规则并行和 kernels。
> - **TPU**：**轻量控制、大 matmul 单元、大 fast memory**。在规则的大矩阵乘法上效率极高。
>
> 如果目标是能效最高的 ML 加速器，最终都会走向 ``轻量控制 + 大 matmul + 快内存''——这也是 TPU 和新一代 GPU Tensor Core 趋同的原因。

### 本章小结
GPU 和 TPU 是同一目标的不同工程折中：GPU 更通用，TPU 更专用。理解它们的结构差异，有助于判断什么 workload 在哪类硬件上更高效。

## Roofline 模型与内存墙

### FLOPs 增长快于内存带宽

过去 20 年，硬件峰值 FLOPs 增长了约 60000 倍，而 DRAM 带宽只增长了约 100 倍。这意味着：

- 计算能力远超喂数据能力。
- 多数 ML kernels 的瓶颈不是算力，而是 **内存带宽**。

[图：figures/seg_4_mid_1560.jpg — 见 PDF]
*硬件 FLOPs、DRAM 带宽与互连带宽的增长差距*

*视频画面时间区间：00:22:00--00:27:00。*

### Roofline 模型

Roofline 模型把 kernel 性能表示为 ``运算强度（operational intensity）'' 的函数：

$$
\text{ attainable FLOP/s} = \min \begin{cases}
\text{peak FLOP/s} \\
\text{memory bandwidth} \times \text{operational intensity}
\end{cases}
$$

其中运算强度 = FLOPs / bytes moved。当强度低时，性能被内存带宽天花板限制（memory-bound）；当强度高时，被算力天花板限制（compute-bound）。

[图：figures/probe_1887.jpg — 见 PDF]
*Roofline 模型：如何避免陷入 memory-bound 区域*

*视频画面时间区间：00:31:00--00:32:00。*

> **[注意]** **常见误区**
> 不要认为 ``FLOPs 越多越好''。如果运算强度低，增加 FLOPs 只是让内存等待更久。**优化的核心问题不是 ``算得多快''，而是 ``能否持续喂饱计算单元''**。

### 本章小结
现代 GPU 是 memory-bound 的世界。 Roofline 模型给出了诊断工具：先算运算强度，再判断是提升 locality、融合算子，还是换更紧凑的数据类型。

## 低精度与量化：用精度换带宽

### Tensor Core 与低精度运算

现代 GPU 的 Tensor Core 专门为低精度矩阵乘法优化。典型流程：

- 输入是 FP16/BF16（16 位）。
- 乘法在 16 位精度下进行。
- 累加使用 FP32 累加器，避免多次累加后的精度损失。

[图：figures/seg_5_mid_2250.jpg — 见 PDF]
*Tensor Core 的混合精度计算模式*

*视频画面时间区间：00:35:00--00:40:00。*

### 量化：FP8、INT8、FP4

降低精度直接减少内存移动量：

- FP32：4 bytes / element。
- FP16/BF16：2 bytes / element。
- FP8：1 byte / element。
- FP4：0.5 byte / element。

对于 memory-bound 的 kernel，把 FP32 降到 FP16 可以直接让有效带宽翻倍，因为每次读写的数据量减半。

> **[知识]** **哪些运算可以降精度？**
> 讲者给出经验法则：
>
> - **可用 16 位存储**：矩阵乘法、大部分逐点运算（ReLU、tanh、add、mul 等）。
> - **需要更高精度**：小值加到大和的 reduction（如 softmax、normalization）、指数/对数/幂运算、loss 计算。

### 本章小结
低精度是 ``用精度换带宽/算力'' 的杠杆。Tensor Core 通过混合精度累加平衡速度与精度；量化则需要仔细判断哪些运算对数值误差敏感。

## 算子融合：减少数据搬运

### 融合的思想

如果多个算子串行执行，每个算子都把结果写回 global memory，下一个算子再读回来，会造成大量冗余内存流量。**算子融合（operator fusion）** 把多个算子合并成单个 kernel，在寄存器或 shared memory 中传递中间结果。

[图：figures/seg_6_mid_2910.jpg — 见 PDF]
*非融合 kernel（左）与融合 kernel（右）的内存访问对比*

*视频画面时间区间：00:46:00--00:50:00。*

> **[重要]** **融合的收益来源**
> 融合本身不减少计算量，但它减少了：
>
> 1. global memory 的写回次数；
> 2. global memory 的读取次数；
> 3. kernel 启动与同步开销。
>
> 对于 memory-bound 的逐点运算，融合常带来数倍加速。

### 本章小结
融合是系统优化的 ``免费午餐''：不改变数学结果，只改变数据流。它是编译器（如 torch.compile / Triton / XLA）自动优化的主要目标之一。

## 合并访问与 Tiling：优化内存模式

### Coalesced Memory Access

当 warp 中的线程同时读取 global memory 时，如果它们的地址连续，硬件可以把多次访问合并成一次 burst（通常为 128 bytes）。如果线程访问分散，则需要多次独立请求。

[图：figures/seg_7_mid_3300.jpg — 见 PDF]
*合并访问（coalesced）与非合并访问（non-coalesced）的对比*

*视频画面时间区间：00:53:00--00:57:00。*

> **[注意]** **row-major 矩阵的陷阱**
> 对于 row-major 矩阵，线程沿行方向移动时访问不连续，因此 **不按列读取会导致非合并访问**。写 CUDA kernel 时，让相邻线程访问相邻内存是基本功。

### Tiling：把数据放到 shared memory

矩阵乘法 $C = A B$ 中，每个元素被读取多次。Tiling 把矩阵分块，将当前计算所需的小块 $A_{tile}$ 和 $B_{tile}$ 加载到 shared memory，然后在块内复用：

- 每个输出 tile 只需从 global memory 读取一次对应的输入 tile。
- shared memory 内的重复访问几乎免费。

[图：figures/seg_8_mid_3780.jpg — 见 PDF]
*Tiling 的复杂度：tile size 必须整除矩阵尺寸以避免资源浪费*

*视频画面时间区间：01:00:00--01:05:00。*

> **[知识]** **影响 tile size 的因素**
> - **合并访问**：tile 的读取方向要让 warp 访问连续地址。
> - **shared memory 容量**：tile 不能太大，否则放不下。
> - **矩阵尺寸的整除性**：若矩阵尺寸不是 tile size 的倍数，边界 tile 会浪费计算资源。

### 本章小结
合并访问和 tiling 分别从 ``单次访问效率'' 和 ``数据复用'' 两个角度减少 global memory 流量。它们是手写 CUDA kernel 时最核心的优化手段。

## Occupancy、Warp 调度与隐藏延迟

### 为什么需要足够多的 warp

每个 SM 可以同时驻留多个 warp，但同一时刻只有一个 warp 在执行指令（或几个 warp 在不同执行单元上）。当某个 warp 因为等待内存而停滞时，warp scheduler 可以切换到另一个就绪 warp，从而隐藏延迟。

> **[重要]** **Occupancy 的核心直觉**
> **Occupancy** = 实际驻留 warp 数 / SM 最大可驻留 warp 数。要隐藏内存延迟，需要足够多的 warp 让 scheduler 总有事可做。如果 block size 太大导致每个 SM 只能放一个 block，而这个 block 的 warp 数又不足，就会出现空闲周期。

### 本章小结
高 occupancy 不一定等于高性能，但过低的 occupancy 会让内存延迟暴露。优化时需要在 ``每个 block 的 shared memory''、``register 用量'' 和 ``warp 数量'' 之间取得平衡。

## 案例：Flash Attention

### 从 Tiling 到 Online Softmax

Flash Attention 是本讲前面所有概念的综合：

1. **内存墙**：标准注意力的 $N \times N$ attention matrix 太大，无法放进 SRAM。
2. **Tiling**：把 query、key、value 分成小块，逐块计算。
3. **Online softmax**：在分块计算时增量维护最大值 $m$ 和归一化因子 $d$，避免先存完整 attention matrix。
4. **重计算（recomputation）**：反向传播时不存 $N^2$ 激活，而是重新计算 forward 的 attention 值。

[图：figures/flash_attention_4500.jpg — 见 PDF]
*Flash Attention 的核心：分块 + online softmax*

*视频画面时间区间：01:13:00--01:16:00。*

> **[重要]** **Flash Attention 的权衡**
> Flash Attention **用额外的计算换取更少的内存访问**：
>
> - 正向：多算一些 FLOPs（分块迭代）以省去 $O(N^2)$ 的 HBM 读写。
> - 反向：重计算 attention 以省去 $O(N^2)$ 激活存储。
>
> 在 memory-bound 的注意力量化下，这是笔划算的交易。

### 本章小结
Flash Attention 不是新算法，而是把 tiling、online softmax、重计算组合起来，在内存墙的约束下重新安排 attention 的数据流。

## 总结与延伸

### 讲者总结

课程结尾，Hashimoto 把第二部分的核心思想归纳为三类优化杠杆：

1. **减少内存访问**：合并访问（coalescing）、算子融合（fusion）。
2. **把内存移到更近的地方**：Tiling / shared memory。
3. **用计算/精度换内存**：量化（quantization）、重计算（recomputation）。

[图：figures/seg_9_mid_4200.jpg — 见 PDF]
*本讲第二部分总结：让 ML 工作负载变快的三大杠杆*

*视频画面时间区间：01:18:00--01:19:00。*

### 我的综合

本讲本质上是在回答一个问题：**在 FLOPs 增速远超内存带宽的时代，如何让矩阵乘法和注意力等核心操作不被内存饿死？** 答案不是买更快的 HBM（虽然有用），而是重新组织计算，让数据尽可能在芯片内部流动。

> **[重要]** **带走的三个核心直觉**
> 1. **Memory is the bottleneck**： Roofline 模型告诉你，先看运算强度，再谈优化。
> 2. **Data movement is expensive**：每次数据离开 SM 都很贵；融合、tiling、重计算都是围绕减少数据移动。
> 3. **GPU is a throughput machine**：它不是让你一条指令更快，而是让成千上万个线程并行并互相掩盖延迟。

### 拓展阅读

- CUDA Mode Discord 与相关博客：<https://discord.gg/cuda-mode>
- scaling-book（TPU/GPU）：<https://jax-ml.github.io/scaling-book/gpus/>
- FlashAttention 论文：Dao et al., ``FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness''
