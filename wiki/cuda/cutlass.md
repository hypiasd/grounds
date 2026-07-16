---
title: CUTLASS
topic: cuda
tags: [gpu, parallel-computing, matrix-multiplication, performance, cuda, template-metaprogramming, cublas, cute]
summary: CUTLASS 是 NVIDIA 开源的 CUDA C++ 模板库，把矩阵运算中重复的 tiling、shared memory 搬运、warp-level MMA 封装成可组合的零件（TiledCopy、TiledMMA、Epilogue、TileShape），让你拼出高性能 GEMM kernel 而不必手写每一行线程代码。它不是新语言、不是编译器、不是 cuBLAS 开源版——它是 CUDA 生态内的极致性能框架。
created: 2026-07-16
updated: 2026-07-16
---

# CUTLASS

## TL;DR

CUTLASS 是 NVIDIA 开源的 CUDA C++ 模板库，专为高性能 GEMM 类运算设计。它不替换 CUDA——它运行在 CUDA 之上，用 C++ 模板元编程把「tiling → 数据搬运 → 计算 → 写回」这个固定模式拆成可正交组合的零件。你选好零件（tile 大小、搬运工、计算单元、后处理），模板在编译期生成特化的 CUDA kernel。本质上是 CUDA 生态内追求极致性能的工具，性能天花板几乎无损（就是 CUDA），学习曲线陡峭。

## 直觉 / 类比

CUDA 是让你自己烧砖盖楼。CUTLASS 给你预制的墙板（`TiledMMA`、`TiledCopy`），你决定墙板怎么拼、顺序怎么排，但不用自己烧每一块砖。Triton 更激进——你画个户型图，施工队全包了。

CUTLASS 之于 CUDA kernel 开发，如同 STL 之于 C++ 容器操作——你不必每次重写 `sort`，但需要知道 `iterator` 和 `comparator` 怎么配。

## 核心概念

### 把 GEMM 拆成可组合的零件

一个矩阵乘法 kernel 的本质是三层循环嵌套（M/N/K 方向 tiling），每层做同一件事：**把一块数据从 global memory 搬到 shared memory → 在 register 上做乘加 → 写回 global memory**。

CUTLASS 把这个套路抽象成几个正交的零件（C++ 模板类）：

| 零件 | 做什么 | 示例 |
|------|--------|------|
| `TileShape` | 选 tile 大小 | `Shape<_128, _128, _32>`（M×N×K） |
| `TiledCopy` / `Copy_Atom` | 数据搬运：global → shared memory | `SM80_CP_ASYNC_CACHEGLOBAL<cute::uint128_t>` |
| `TiledMMA` / `MMA_Atom` | 计算：shared memory → register → Tensor Core MMA 指令 | `SM80_16x8x16_F32F16F16F32_TN` |
| `Epilogue` | 后处理：bias、激活函数、写回 | `LinearCombination<...>` 或自定义 |

典型 kernel 的拼装代码：

```cpp
// 定义 GEMM kernel 类型
using Gemm = cutlass::gemm::device::Gemm<
    cutlass::half_t,                           // ElementA
    cutlass::half_t,                           // ElementB
    cutlass::half_t,                           // ElementC
    cutlass::layout::RowMajor,                 // LayoutA
    cutlass::layout::ColumnMajor,              // LayoutB
    cutlass::layout::RowMajor,                 // LayoutC
    cutlass::half_t,                           // ElementAccumulator
    cutlass::arch::OpClassTensorOp,            // 使用 Tensor Core
    cutlass::arch::Sm80,                       // SM 架构（A100）
    cutlass::gemm::GemmShape<128, 128, 32>,   // TileShape: M×N×K
    cutlass::gemm::GemmShape<64, 64, 32>,     // WarpShape
    cutlass::gemm::GemmShape<16, 8, 16>,      // InstructionShape
    cutlass::epilogue::thread::LinearCombination<
        cutlass::half_t, 128 / cutlass::sizeof_bits<cutlass::half_t>::value,
        cutlass::half_t, cutlass::half_t>,
    cutlass::gemm::threadblock::GemmIdentityThreadblockSwizzle<>,
    3  // Pipeline Stages
>;

// 运行
Gemm gemm_op;
auto status = gemm_op({M, N, K}, A_tensor, B_tensor, C_tensor, C_tensor, ...);
```

同一个框架覆盖从 fp16 SM80 Tensor Core 到 fp8 Hopper SM90 的多种硬件——只需换模板参数，代码结构不变。

### 和 CUDA 的关系

CUTLASS **运行在 CUDA 之上**，不替换 CUDA。

- CUDA 让你直接写 `threadIdx`、`blockIdx`、`__syncthreads()`、`__shfl_sync()`。
- CUTLASS 把这些东西包进类型系统——你写 `using Mma = TiledMMA<SM80_16x8x16_F32F16F16F32_TN>` 而不是手调 `mma.sync.aligned` 内联汇编。
- **但它不隐藏硬件细节**：你仍然要理解 warp、shared memory bank、Tensor Core 指令形状。CUTLASS 提供的是组织方式，不是黑盒。

### 和 Triton 的关系

两者都解决「手写 CUDA tiling 太痛苦」，但路径相反：

| | CUTLASS | Triton |
|---|---|---|
| 编程模型 | CUDA C++（线程级），模板帮你组织 | Python DSL（块级），编译器生成线程 |
| 抽象层级 | 中——你选积木，编译器/模板帮你拼 | 高——你描述一个 tile 的行为，编译器全包 |
| 性能天花板 | 几乎无损失（本质是 CUDA + 模板元编程） | 接近 cuBLAS 80-95%，规则计算可达 ≈CUTLASS |
| 适用场景 | GEMM、卷积、带复杂 epilogue 的矩阵运算 | 任何 tiled computation，包括 softmax、LayerNorm 等 |
| 学习曲线 | 陡——需要懂 CUDA + 模板元编程 + 硬件指令形状 | 平——Python 语法，几行代码就能跑 |
| 新硬件支持 | NVIDIA 内部同步开发，Hopper TMA 最先支持 | 社区驱动，滞后于 CUTLASS |

一句话：**CUTLASS 是 CUDA 生态内追求极致性能的工具，Triton 是跨生态追求开发效率的工具。**

### 四层 GPU 编程抽象栈

```
抽象层级（高 = 开发快）
  ▲
  │  Triton        Python DSL + 自研编译器 → LLVM/PTX，块级，编译器管线程/内存
  │  TileLang      基于 TVM 的 tile DSL，tile 一等公民，显式管内存层级
  │  CUTLASS       CUDA C++ 模板库，拼 tile 积木，仍在 CUDA 生态内
  │  CUDA          线程级，手动管理一切（线程映射、shared memory、同步）
  └──────────────────────────────────────────────────────► 性能天花板（高 = 跑得快）
```

## CuTe、CUTLASS、cuBLAS 三者的关系

```
cuBLAS     ← 闭源成品，"我要算 GEMM，给我最快的结果"
  ↓ 部分 kernel 由 CUTLASS 生成
CUTLASS    ← 开源框架，"我要定制 GEMM 的 epilogue/pipeline"
  ↓ 3.x 基于
CuTe       ← 核心抽象层，"我要精确控制数据在内存层级间的流动"
  ↓ 跑在
CUDA       ← 线程级编程，"我把每个线程映射到数据上"
```

### cuBLAS：闭源的 BLAS 成品

cuBLAS 是 NVIDIA 对 BLAS 标准的 GPU 实现，闭源。你调用 `cublasGemmEx()`，库内部根据矩阵大小和数据类型从一个预编译的 kernel 池里自动选最优的——部分 kernel 是手工汇编写的，部分由 CUTLASS 生成。对常见 shape，它就是性能天花板。

**「闭源」到底是什么意思？** 闭源 = 你看不到 kernel 的 CUDA C++ 源码，不意味着你不能调用 API。cuBLAS 给你的是编译好的动态库（`libcublas.so`），你通过头文件声明调用——就像你调用 `printf()` 但读不到 glibc 的 `printf` 源码一样。当然你可以用 `cuobjdump` 反汇编 cubin，或用 Nsight Compute 看 SASS 指令，但这和读带注释的源码是两回事。

**cuBLAS 的边界**：只能做标准 BLAS 操作（GEMM、GEMV、TRSM 等）。如果你的需求是 GEMM + 自定义激活函数 + 自定义量化 fused 在一起，cuBLAS 做不到——它是成品，不是积木。

**直觉**：cuBLAS 是 Uber——告诉它去哪，它带你走最优路径。但你不能让它中途绕道买咖啡。

#### 附：BLAS 标准是什么

**BLAS** = **Basic Linear Algebra Subprograms**（基础线性代数子程序），是 1979-1990 年间学术界定义的一套接口标准。它把线性代数操作分成三个层级：

| 层级 | 操作类型 | 典型函数 | 计算量 | 访存量 |
|------|---------|---------|--------|--------|
| Level 1 | 向量-向量 | `SAXPY`、`SDOT` | O(n) | O(n) |
| Level 2 | 矩阵-向量 | `SGEMV`、`STRMV` | O(n²) | O(n²) |
| Level 3 | 矩阵-矩阵 | `SGEMM`、`STRMM` | O(n³) | O(n²) |

越往上，计算/访存比越高，越容易发挥硬件算力。函数命名有规律：`SGEMM` = **S**ingle precision × **GE**neral **M**atrix **M**ultiply（`DGEMM` 就是把 S 换成 Double）。

BLAS 的设计动机很朴素：70-80 年代每个超级计算机厂商都有自己的一套线性代数库。BLAS 定义了一套通用接口，让上层软件（LAPACK、MATLAB、NumPy）只要调 BLAS，底层由各厂商按自家硬件优化实现。cuBLAS（NVIDIA）、MKL（Intel）、OpenBLAS（开源）、BLIS（AMD）都是同一套接口的不同实现。

### CuTe：CUTLASS 3.x 的核心抽象

CuTe（**Cu**da **Te**mplates）是 CUTLASS 3.x 的底层核心库，提供三个基础原语：

- **Layout Algebra**：用数学方式描述数据在内存中的排列（行主序/列主序/swizzle/padding），编译期做 layout 变换——不需要手动算 stride。
- **Copy_Atom / TiledCopy**：描述数据在全局内存 → 共享内存 → 寄存器之间怎么搬运，精确到每个线程搬多少个字节。
- **MMA_Atom / TiledMMA**：描述 Tensor Core 的一条 MMA 指令怎么映射到线程和寄存器。

这三个零件组合起来，可以写任意 tile 级数据流程序——不限于 GEMM。CUTLASS 3.x 的 `CollectiveMainloop` 和 `CollectiveEpilogue` 就是基于 CuTe 搭建的 GEMM 专用高层封装。

**直觉**：CuTe 是发动机，CUTLASS 3.x 是用这台发动机造的车。你也可以不买车，直接用发动机造飞机——CuTe 是通用 tile 编程原语，CUTLASS 仓库之外也能独立使用。

### CUTLASS 2.x vs 3.x：框架自身的演进

```
CUTLASS 2.x                          CUTLASS 3.x
─────────────                        ─────────────
Gemm::device::Gemm                   基于 CuTe 的 Collective
  │ (硬编码 GEMM 模板)                  │
  ├─ TiledCopy (自实现)                ├─ cute::TiledCopy (CuTe 提供)
  ├─ TiledMMA  (自实现)                ├─ cute::TiledMMA  (CuTe 提供)
  └─ Epilogue  (自实现)                └─ cute::Epilogue  (CuTe 提供)
                                           │
                                      CollectiveMainloop
                                      CollectiveEpilogue
                                      (GEMM 专用高层封装)
```

2.x 的 `TiledCopy`、`TiledMMA` 是 CUTLASS 自己实现的，和 GEMM 强绑定。3.x 全部推倒，用 CuTe 的通用抽象重写。这意味着你可以用 CuTe 直接写 kernel（绕过 Collective），也可以只用 Collective 写标准 GEMM，也可以混用。

## 常见误区


- **「CUTLASS 是 cuBLAS 的开源版」**——不是。cuBLAS 是闭源手工调优的 BLAS 库，CUTLASS 是一个**框架**让你自己写类似 cuBLAS 的高性能 kernel。CUTLASS 的目标不是取代 cuBLAS，是让你写 cuBLAS 覆盖不到的定制 kernel（如带自定义激活函数的 fused GEMM）。
- **「用了 CUTLASS 就不用懂 CUDA 了」**——正好相反。CUTLASS 的模板参数（`ThreadblockShape`、`WarpShape`、`InstructionShape`）直接映射到 GPU 硬件特性，不懂 warp 和 Tensor Core 指令形状根本配不出正确参数。
- **「CUTLASS 只能做 GEMM」**——虽然名字是 CUDA Templates for Linear Algebra Subroutines，但它的分解组合设计适用于任何可 tiling 的计算。CUTLASS 3.x 的 CuTe 抽象更是通用 tile 级编程模型。
- **「CUTLASS 性能不如手写 CUDA」**——没有理由。CUTLASS 编译出来就是 CUDA kernel，模板在编译期展开。真正影响性能的是你选的 tile 大小和 pipeline stage 数是否匹配硬件，和用不用 CUTLASS 无关。

## 面试常见问题

- **Q**: CUTLASS 2.x API 和 3.x API 怎么选？有什么判断标准？
  **A**: 2.x API 是经典的 `Gemm::device::Gemm` 模板参数拼装方式——指定 `TileShape`、`WarpShape`、`InstructionShape`、`Epilogue` 等参数，适合 Ampere 及更老的架构上的标准 GEMM/卷积。3.x API（CuTe）引入了 layout algebra 和 `CollectiveMainloop`/`CollectiveEpilogue` 分离，让你能精确控制数据在 HBM → SMEM → Register → Tensor Core 的每一步流动。如果目标是 Hopper 及更新架构，或需要写高度定制的 kernel（如 warp-specialized async pipeline），用 3.x；如果是标准 GEMM 且目标是 Ampere 或更老，2.x 更简单直接。

- **Q**: NVIDIA 面试中常问「如何并行化矩阵乘法」——从 naive 到 CUTLASS 级别的答案是什么？
  **A**: 分层回答。Naive 版：一个线程算一个输出元素，访存是 O(N³) 的全局内存访问，带宽利用率低。Shared memory tiling 版：每个 thread block 协作加载 A 和 B 的 tile 到 shared memory（`__syncthreads()` 保序），然后从 shared memory 计算，每个元素从全局内存只加载一次，访存量降为 O(N³/tile_size)。CUTLASS 版：在此基础上，用 `TiledMMA` 将 shared memory → register → Tensor Core MMA 指令的路径模板化，`Epilogue` 融合 bias/激活函数避免额外 kernel launch，`Pipeline Stages` 做 double/triple buffering 重叠搬运和计算。

- **Q**: 什么时候选 CUTLASS 而不是 Triton？给出具体的决策条件。
  **A**: 三个条件满足任一就应考虑 CUTLASS：（1）需要 tensor-core peak 的定制 GEMM/卷积，且 shape 不在 cuBLAS 覆盖范围——Triton 在 compute-bound GEMM 上通常比 CUTLASS 慢 10-20%；（2）需要最新硬件特性最先支持——Hopper TMA、Blackwell NVFP4，CUTLASS 是 NVIDIA 内部同步开发的，Triton 是社区驱动滞后；（3）需要 warp-specialized async pipeline 或自定义同步模式——Triton 的编程模型不暴露这些。其他情况（fused element-wise、softmax、LayerNorm、快速原型）用 Triton。

- **Q**: cuBLAS、CUTLASS、手写 CUDA 三者性能怎么排？
  **A**: 对标准 GEMM 在常见 shape 上：cuBLAS > CUTLASS ≈ 手写 CUDA（差距在个位数百分点内）。cuBLAS 针对常见 shape 有手工调优的汇编级 kernel，CUTLASS 编译出来就是 CUDA kernel，性能瓶颈在于你选的 tile 大小和 pipeline stage 是否匹配硬件——这和是否用 CUTLASS 无关。手写 CUDA 理论上能达到 cuBLAS 水平，但需要投入量级完全不同的工程时间。CUTLASS 的独特价值在于 cuBLAS 覆盖不到的定制 shape 和 fused epilogue。

- **Q**: 如果 CUDA kernel 在 H100 上只达到 30% 的内存带宽峰值，你会怎么排查？
  **A**: 用 Nsight Compute 先看 `memory_workload_analysis` 章节。最常见的三个元凶：（1）非 coalesced 访存——warp 内 32 线程访问不连续的 128-byte 段，解决方法是将 AoS 转 SoA 或调整数据布局；（2）shared memory bank conflict——Nsight 会报 `shared_memory_bank_conflict` 指标，通常通过 padding 或 swizzle 布局解决；（3）occupancy 太低——block 的 shared memory 或寄存器用量过大导致每个 SM 上同时驻留的 warp 太少，不足以 hide latency，需要调整 block 大小或用 `cudaOccupancyMaxPotentialBlockSize` API 调优。

- **Q**: CUTLASS kernel 和 PyTorch reference 之间的数值差异如何处理？
  **A**: 类似 Triton 的情况：（1）浮点累加顺序不同——Tensor Core MMA 的累加顺序和 cuBLAS 不同，FP16 下用 `atol=1e-2` 验证即可；（2）累加器 dtype 必须是 float32——如果用 FP16 累加会在处理大矩阵时溢出；（3）Epilogue 融合可能改变数值——比如 bias + ReLU 和分步计算的中间精度不同；（4）边界 tile 的 mask 处理——没正确处理 mask 会在 edge tile 上算到垃圾数据。

- **Q**: cuBLAS、cuBLASLt、CUTLASS 的区别和使用场景有什么不同？
  **A**: cuBLAS 是 BLAS 标准的 GPU 闭源实现，API 遵守 BLAS 规范，覆盖传统线性代数场景。cuBLASLt（Lightweight）只覆盖矩阵乘法，不遵守 BLAS API——NVIDIA 用它快速发布 AI 场景的新特性（低精度 GEMM、算子融合等），不需要等 BLAS 标准更新。CUTLASS 是开源 C++ 模板库，用于写 cuBLAS/cuBLASLt 不支持的定制算子。选择逻辑：传统 BLAS 需求 → cuBLAS；AI 矩阵乘且有对应支持 → cuBLASLt；需要定制融合（如 GEMM+LayerNorm、GEMM+TopK、weight-only GEMM）→ CUTLASS。
  *来源：知乎 • zzk again / Vincent • [链接](https://www.zhihu.com/question/4744756570)*

- **Q**: 你们为什么要写算子，算子难道比 cuBLAS 的快吗？（面试中常被追问的问题）
  **A**: 单独一个 GEMM 几乎不可能比 cuBLAS 快——cuBLAS 对常见 shape 有汇编级手工调优的 kernel 池。自己写算子真正比 cuBLAS 快的情况有两种：（1）算子融合——把 GEMM + 激活函数 + 量化 fused 在一个 kernel 里，相比分步调 cuBLAS 再逐个 launch 小 kernel，省掉了中间结果的显存读写和多次 kernel launch 开销；（2）特殊 shape——cuBLASLt 的启发式搜索偶尔会选到次优分块方案，精心调过的 CUTLASS 参数可能撞出一个 bad case。但在标准 GEMM 的常见 shape 上，cuBLAS 就是性能天花板。
  *来源：牛客 • yyfan98（百度异构计算工程师面经）*

- **Q**: 怎么判断一个手写 kernel 是否还有优化空间？用什么工具？
  **A**: 用 Nsight Compute 看三个指标：（1）`memory_workload_analysis`——检查 global memory 的 coalesced 访问和 shared memory 的 bank conflict；（2）`occupancy`——每个 SM 上驻留的 warp 数是否足够 hide latency（寄存器/共享内存用量是主要限制）；（3）`compute_workload_analysis`——看 Tensor Core/FP32 单元的利用率。如果 memory bound（显存带宽已接近峰值），优化方向是减少访存或提高复用；如果 compute bound（计算单元利用率高），优化空间有限——可以考虑换 tile 大小或 pipeline stage 数来微调。另外，用 Roofline 模型快速定位是 memory bound 还是 compute bound，避免盲目调参。
  *来源：知乎 • 不归牛顿管的熊猫（CUDA 面试官面经）*

- **Q**: CUTLASS 入门的高门槛主要体现在哪里？
  **A**: 三个层面：（1）**硬件知识门槛**——模板参数（`ThreadblockShape`、`WarpShape`、`InstructionShape`、Pipeline Stages）直接映射到 GPU 硬件特性，不懂 warp/SM/Tensor Core 指令形状根本配不出正确参数；（2）**C++ 模板元编程门槛**——CUTLASS 大量使用 CRTP、variadic templates、编译期计算，报错信息通常是几百行的模板展开，调试困难；（3）**概念体系门槛**——CUTLASS 3.x 的 CuTe API 引入了 layout algebra、Copy_Atom/MMA_Atom、Collective 等新概念，即使你懂 CUDA 也要重新学一套抽象。建议从 2.x API 的标准 GEMM example 开始，理解 tile/warp/instruction 三级分块后再转 3.x。
  *来源：知乎 • zzk again（122 赞）*


## 关联

- [GPU 执行模型](gpu-execution-model.md) — CUTLASS 的前置知识，理解 warp/Tensor Core/内存层级后才能看懂模板参数的含义
- [Triton](triton.md) — 同一问题的另一种解法：用编译器而非模板库来管理 tiling 复杂度
- [TileLang](tilelang.md) — 基于 TVM 的 tile DSL，在 CUTLASS 和 Triton 之间填了一个生态位
