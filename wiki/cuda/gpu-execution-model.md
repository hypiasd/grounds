---
title: GPU 执行模型
topic: cuda
tags: [cuda, gpu, parallel-computing, hardware, memory, performance]
summary: GPU 执行模型有四面相：线程层级（Grid/Block/Thread 软件体系 + SM/CUDA Core 硬件体系）、Warp/SIMT（32 线程锁步执行、warp divergence、latency hiding）、内存层级（寄存器/共享内存/显存）、SM 内部结构（CUDA Core 与 Tensor Core 的硬件定位与分工）。四者互咬——block 的协作边界是 shared memory，warp 的延迟隐藏掩盖的是显存延迟，Tensor Core 的矩阵吞吐反过来依赖 block 协作和共享内存来喂数据。
created: 2026-07-14
updated: 2026-07-17
---


## TL;DR

GPU 执行模型是四个互相咬合的面相：**线程层级**告诉你谁在跑（软件 Grid/Block/Thread 对接硬件 SM），**Warp/SIMT** 告诉你怎么跑（32 线程锁步、分支发散、延迟隐藏），**内存层级**告诉你数据在哪（寄存器/共享内存/显存，速度差百倍），**SM 内部结构**告诉你算力从哪来（CUDA Core 做标量、Tensor Core 做矩阵）。四者不能孤立理解——block 存在是为了共享内存和同步，warp 的 latency hiding 掩盖的正是显存的慢，Tensor Core 的矩阵吞吐反过来依赖 block 协作和共享内存来喂数据。

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

### Block 存在的理由：共享内存的物理边界

如果只有 thread 和 warp，线程间无法协作。Block 给了三个能力：**共享内存**（block 内线程共用高速 SRAM）、**同步**（`__syncthreads()`，跨 block 无此原语）、**分工**（协作加载、汇总）。一句话：block 是线程共享内存和同步的最小边界。

### Block 大小约束

- 硬上限 1024 线程；最好 32 的倍数（warp 按 32 切）；太小浪费 SM 资源，太大挤占 shared memory/寄存器降低 occupancy
- 经验值：128、256、512

### Grid 存在的理由：纯软件概念

grid 本身**没有对应的硬件单元**——它纯粹是软件概念，唯一作用是告诉 GPU 调度器"这次总共要启动多少个 block"。调度器拿到 grid 后把 block 分摊到各个 SM 上：SM 0 领 3 个，SM 1 领 4 个……谁先空出来谁再领，直到全部跑完。

grid 的 1D/2D/3D 维度选择与硬件无关——硬件拿到的是扁平的 block 列表。2D grid 只是让你在写代码时不用手动 `pid // width`、`pid % width` 算行列号。同理，`dim3(width, height)` 的书写顺序是（横向, 纵向），与矩阵的（行, 列）习惯相反——记住"CUDA 的 dim3 是宽度×高度"即可。

**三层设计与硬件的对应**：

| 层级 | 设计动机 | 硬件对应 |
|------|---------|---------|
| Thread | 最小执行单元 | CUDA Core |
| Block | **共享内存的物理边界**（SM 内 SRAM 是隔离的） | 一个 SM（block 不可跨 SM） |
| Grid | 活的总量，给调度器分发用 | 无——纯软件概念 |

block/SM 的关系是"一对多"：一个 block 一定只在一个 SM 上跑（因为共享内存物理隔离），但一个 SM 可以同时驻留多个 block（只要寄存器/共享内存够用）。block 切得越多，每个 SM 能分到的 block 越多，可切换的 warp 越多，latency hiding 越强。

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
- CUDA Core 是工人（一次做一个乘法），Tensor Core 是模具（一次压出一整块矩阵乘加）。模具没有替代工人——工人做杂活，模具专做矩阵

## 常见误区

- GPU 线程 ≠ CPU 线程 —— GPU 线程极轻量、无独立调度栈、靠硬件批量发射
- Block 不是 warp 的集合 —— block 是 thread 集合，warp 是硬件自动切的
- Block 内不同 warp 可以执行不同指令 —— SIMT 约束 warp 内部，不是 block 内部
- 共享内存不是显存 —— 是 SM 内 SRAM，物理介质完全不同
- Latency hiding 不是靠缓存 —— 靠 warp 切换，GPU 和 CPU 思路相反
- Shared memory 不是越多越好 —— 占用太多降低 occupancy
- Tensor Core 是独立芯片 → 不，它在 SM 内部，和 CUDA Core 共享寄存器堆
- 用了 GPU 自动启用 Tensor Core → 不。数据尺寸必须对齐 tile 形状、精度必须匹配硬件期望、编译器必须生成正确的 MMA 指令。任一不满足，Tensor Core 就闲着
- 混合精度会丢精度所以不靠谱 → 乘法丢的尾数精度，在神经网络梯度跨数量级的场景下是安全的。BF16 代替 FP32 训练，loss 曲线几乎重合
- Tensor Core 替代了 CUDA Core → 不，两者共存。标量活（地址计算、控制流、element-wise op）给 CUDA Core，矩阵活给 Tensor Core

## 四、SM 内部：CUDA Core 与 Tensor Core

### SM 里面有什么

SM 不只有 CUDA Core。打开一个 SM，里面有这些硬件单元：

```
┌────────────────── SM ──────────────────┐
│  Warp Scheduler (×4)                    │
│  ┌──────────┐  ┌────────────┐           │
│  │CUDA Core │  │Tensor Core │  SFU ...  │
│  │  (×64)   │  │   (×4)     │           │
│  │ 标量 FMA │  │ 矩阵 MMA   │           │
│  └──────────┘  └────────────┘           │
│  Register File (64K × 32-bit)           │
│  Shared Memory / L1 Cache (192 KB)       │
└─────────────────────────────────────────┘
```

- **CUDA Core**：标量计算单元。一个 CUDA Core 内部是一个 FP32 乘法器 + 一个 FP32 加法器（合起来就是一个 FMA 单元），外加一个 INT32 单元。每周期做 **1 次**标量乘加。
- **Tensor Core**：矩阵计算单元。内部是一组乘加器按矩阵形状连成的 systolic array，每周期完成一 **整块小矩阵**的乘加（MMA, Matrix Multiply-Accumulate）。
- **SFU**（Special Function Unit）：算 sin/cos/exp/reciprocal 等超越函数。
- **Register File**：SM 内所有线程的寄存器存储。
- **Shared Memory / L1 Cache**：可配置的高速 SRAM。
- **Warp Scheduler**：决定每周期发射哪个 warp 的指令给哪个执行单元。

**关键**：CUDA Core 和 Tensor Core 共享同一套寄存器堆和共享内存。warp 调度器决定这一拍发射标量指令给 CUDA Core 还是矩阵指令给 Tensor Core——切换无开销，数据本来就在同一个寄存器文件里。两者都是硅片上的硬件，不是软件抽象。

### FMA：底层算术单元

FMA（Fused Multiply-Add）：一条指令完成

$$a \times b + c$$

关键在"Fused"——乘法做完后**不单独舍入**，保留完整精度的中间结果，和 c 加完后再**舍入一次**。比分开做两条指令（先乘后加，各舍入一次）更快也更准。

CUDA Core 做的是**标量 FMA**（一次一个数），Tensor Core 做的是**矩阵 MMA**（一次一块矩阵，本质是矩阵版 FMA：$D = A \times B + C$）。底层算术电路逻辑一样，区别在于 Tensor Core 把乘加器阵列化了。

### Tensor Core 的核心操作

$$D = A \times B + C$$

A、B 是低精度输入（FP16/BF16/TF32/FP8...），C 和 D 用 FP32 累加。这个 MMA 在一个时钟周期内完成一块小矩阵的乘加。

### 混合精度为什么能工作

浮点数的结构：符号位 + 指数位 + 尾数位。

| 格式 | 符号 | 指数 | 尾数 | 总位宽 | 范围 | 有效位数 |
|------|------|------|------|--------|------|----------|
| FP32 | 1 | 8 | 23 | 32 | 10⁻³⁸~10³⁸ | ~7 位 |
| FP16 | 1 | 5 | 10 | 16 | 10⁻⁵~65504 | ~3 位 |
| BF16 | 1 | 8 | 7 | 16 | 10⁻³⁸~10³⁸ | ~2 位 |
| TF32 | 1 | 8 | 10 | 19 | 10⁻³⁸~10³⁸ | ~3 位 |

**指数管范围（防溢出/下溢），尾数管精度（有效数字）。**

神经网络训练能容忍混合精度的原因有两个：
1. 梯度跨很多个数量级，需要大范围——BF16 的 8 位指数和 FP32 一样大，刚好兜住。
2. 单次乘法的精度要求不高——2 位有效数字够了。真正需要精度的是成千上万次乘法之后的累加，所以累加器必须用 FP32。

这就是 Tensor Core 的设计哲学：**乘法用低精度（快、省电、省带宽），累加用 FP32（稳）。** BF16 是最直观的例子——保留 FP32 的指数范围，砍掉约 16 位尾数，面积省了一大半，loss 曲线几乎不降。

（浮点格式的完整对比和更多细节见 [GPU 浮点格式](float-formats.md)。）

### 为什么 Tensor Core 比 CUDA Core 快这么多

两个原因，都指向"拿面积换吞吐"：

**1. 精度越低，乘法器越小**

乘法器的硅面积大致和尾数位宽的平方成正比。FP32 尾数 23 位，FP16 尾数 10 位——FP16 乘法器面积不到 FP32 的 1/5。同样的硅面积，可以塞 5 个 FP16 乘法器，才抵一个 FP32 乘法器。BF16（7 位尾数）面积优势更大。

**2. 专用化省掉了通用控制逻辑**

CUDA Core 要处理 FP32、INT32、各种指令格式，附带通用寄存器读写、旁路网络、控制逻辑。Tensor Core 只做一件事——矩阵乘加。所有通用控制逻辑都扔了，内部就是一组乘法器+加法器的 systolic array，数据在相邻单元间直接流动，不需要复杂路由。

结果：一个 A100 SM 内有 64 个 CUDA Core（每周期 128 次 FP32 操作）和 4 个 Tensor Core（每周期 1024 次 FP16 FMA，折合 2048 次浮点操作）。面积效率差 ~50-100 倍，来源不是魔术，是**砍精度 + 砍通用性**。

### 各代演进

| 架构 | 代表 GPU | Tensor Core 精度 | 亮点 |
|------|----------|------------------|------|
| Volta | V100 | FP16 | 第一代，FP16 in → FP32 accumulate → FP32 out |
| Turing | T4/RTX 20 | +INT8, INT4 | 推理加速，INT8 成为推理标配 |
| Ampere | A100/RTX 30 | +TF32, BF16, FP64 | TF32 是内部缝合格式；BF16 成为训练标配 |
| Hopper | H100 | +FP8 (E4M3/E5M2) | FP8 训练，4× TF32 吞吐 |
| Blackwell | B200 | +FP4 (E2M1) | FP4 推理，可训练混合专家模型 |

每一代的核心逻辑不变（D=A×B+C），只是支持的精度越来越低、tile 越来越大、吞吐翻倍。


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

- **Q**: 什么是 Tensor Core？它和 CUDA Core 的区别是什么？
  **A**: Tensor Core 是 SM 内部专做矩阵乘加（D=A×B+C）的硬件单元，CUDA Core 是通用标量 FMA 单元。区别有三：（1）计算粒度——CUDA Core 每周期做 1 次标量乘加，Tensor Core 每周期做一整块小矩阵乘加；（2）精度——Tensor Core 依赖低精度输入（FP16/BF16/TF32/FP8/FP4），CUDA Core 支持 FP32/INT32 等通用格式；（3）适用场景——Tensor Core 适合能规整映射为矩阵乘的大计算量算子（GEMM、attention），CUDA Core 适合逐元素操作、规约、分支、采样等不规则计算。两者在 SM 内是邻居，共享寄存器堆，warp scheduler 根据指令类型分发到不同管线。（来源：快手 C/C++面经 • 面试大师 • mianshidashi.cn）
- **Q**: WMMA 和 MMA 的定位差异是什么？
  **A**: WMMA 是 CUDA C++ 提供的高层 warp 级矩阵乘加 API，用 fragment 封装矩阵块的加载、计算与写回，代码可读性好但可控性和能覆盖的指令形态有限。MMA 是更底层的矩阵乘加指令接口（PTX 级或内联汇编），暴露 tile shape、operand layout、寄存器组织等硬件细节，性能控制力更强但代码复杂度和可移植成本也更高。工程上优先用 cuBLAS/cuBLASLt 或 CUTLASS；需要自定义融合算子时考虑 WMMA；极致性能需求才手写 MMA。（来源：阿里巴巴 C/C++面经 • 面试大师 • mianshidashi.cn）
- **Q**: 什么时候用 CUDA Core，什么时候用 Tensor Core？
  **A**: 按算子形态和数据特征判断。适合 Tensor Core：能规整映射为大矩阵乘的算子（线性层、QKV 投影、attention 矩阵乘），低精度或混合精度场景，维度对齐且计算量大。适合 CUDA Core：逐元素操作（激活函数）、规约（softmax、LayerNorm、loss）、采样、索引变换、mask、小 batch/短序列/尾块等不规则 shape。LLM 推理的典型分工——线性层、投影层走 Tensor Core；softmax、layernorm、采样、KV cache 管理走 CUDA Core。最终都要用 profiler 验证，不能凭经验猜测。（来源：快手 C/C++面经 • 面试大师 • mianshidashi.cn）
- **Q**: Tensor Core 只支持 FP16 吗？
  **A**: 不是。不同架构代际支持不同精度：Volta 仅 FP16，Turing 增加 INT8/INT4，Ampere 增加 TF32/BF16/FP64，Hopper 增加 FP8（E4M3/E5M2），Blackwell 增加 FP4（E2M1）。面试里应强调依赖硬件架构和 CUDA 版本，而不是固定一种类型。（来源：阿里巴巴 C/C++面经 • 面试大师 • mianshidashi.cn）
- **Q**: 为什么 Tensor Core 的输入需要维度对齐（如 8 的倍数）？
  **A**: Tensor Core 在硬件层面按固定 tile 形状执行 MMA（如 16×16×16）。如果矩阵维度不是 tile 尺寸的整数倍，尾块需要 padding 或走 CUDA Core 回退路径，Tensor Core 利用率下降。NVIDIA 官方建议 GEMM 的 M、N、K 尽量是 8 的倍数（具体取决于架构和精度），以充分吃满 Tensor Core 硬件。这是混合精度训练中 batch size 和 hidden dim 常取 2 的幂次的原因之一。（来源：NVIDIA Tensor Core 编程指南 • Smarter's blog • smarter.xin）

## 关联

- 前置：无（本笔记是 GPU 编程的起点）
- 后续：
  - [Triton](triton.md) — 块级 GPU 编程，编译器自动管理线程和共享内存；`tl.dot` 自动生成 Tensor Core MMA 指令
  - [GPU 浮点格式](float-formats.md) — Tensor Core 混合精度依赖的浮点格式体系（FP32/FP16/BF16/TF32/FP8/FP4）
  - [CUTLASS](cutlass.md) — 用模板显式拼装 Tensor Core MMA 指令，追求极致性能；3.x 核心抽象 CuTe 直接映射到 Tensor Core tile 操作
