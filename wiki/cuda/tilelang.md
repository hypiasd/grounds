---
title: TileLang
topic: cuda
tags: [gpu, parallel-computing, tvm, dsl, tile-programming, kernel-programming]
summary: TileLang 是一个基于 TVM 的 tile-level DSL，将 tile 作为一等公民——你显式声明 tile 大小、数据放在哪个内存层级（shared/fragment/global）、如何用 T.copy 在层级间搬运。基于 TVM TIR 编译基础设施，@T.prim_func JIT 编译为 GPU/CPU 代码。在 CUTLASS（CUDA 模板拼积木）和 Triton（编译器全包）之间填了一个生态位：比 CUTLASS 抽象高，比 Triton 控制细。
created: 2026-07-16
updated: 2026-07-16
---

# TileLang

## TL;DR

TileLang 是一个基于 TVM 的 tile-level DSL。和 Triton 一样是 Python DSL，但它让你**显式声明**数据的内存层级（`T.alloc_shared` / `T.alloc_fragment`），手动控制 `T.copy` 在层级间搬运——不像 Triton 那样编译器帮你决定 shared memory。底层的 TVM TIR 编译基础设施带来天然的 auto-tuning 集成。尚处早期阶段（v0.1.x，2025 年论文），但 GPU+CPU 双目标让它有独特定位。

## 直觉 / 类比

如果 CUTLASS 是「CUDA 里拼乐高积木」，Triton 是「画户型图让施工队全包」，那 TileLang 就是「你自己定每面墙在哪、用什么材料，但施工队（TVM）帮你搬砖和水泥」——你明确声明 tile 怎么切、数据在哪个内存层级，但编译器生成实际的线程代码。

再一个类比：TileLang 之于 TVM，如同 Triton 之于其自研编译器——都是在一块成熟的编译基础设施上盖了一层 tile-level 的 Python DSL。

## 核心概念

### 设计哲学：tile 是一等公民

TileLang 的核心理念是让 **tile** 成为编程的基本单元。一个 tile 代表一块有形状的数据，被一个 warp 或 thread block 拥有和处理。你不需要写线程索引，但你需要显式管理数据在不同内存层级间的流动。

```python
import tilelang as T
import tilelang.language as TL

@T.prim_func                      # 标记 kernel，编译为 TVM TIR
def gemm(
    A: T.Tensor((M, K), "float16"),  # global memory
    B: T.Tensor((K, N), "float16"),
    C: T.Tensor((M, N), "float16"),
):
    with T.Kernel(T.ceildiv(N, BLOCK_N), T.ceildiv(M, BLOCK_M)):
        # ── Shared memory 分配 ──
        A_shared = T.alloc_shared((BLOCK_M, BLOCK_K), "float16")
        B_shared = T.alloc_shared((BLOCK_K, BLOCK_N), "float16")
        # ── Register fragment ──
        C_frag = T.alloc_fragment((BLOCK_M, BLOCK_N), "float16")

        # ── 沿 K 方向循环 ──
        for k in T.serial(T.ceildiv(K, BLOCK_K)):
            # 从 global 搬到 shared（需要屏障）
            T.copy(A[...], A_shared)
            T.copy(B[...], B_shared)
            # 从 shared 搬到 fragment，做 MMA
            T.copy(A_shared, A_frag)   # 隐式矩阵乘法累加
            T.copy(B_shared, B_frag)

        # ── 写回 global ──
        T.copy(C_frag, C[...])
```

### 关键语法零件

| 零件 | 做什么 | 对应概念 |
|------|--------|----------|
| `@T.prim_func` | 声明 kernel，JIT 编译为 TVM TIR | Triton 的 `@triton.jit` |
| `T.Kernel(grid...)` | 声明 launch context，grid 和 block 绑定 | CUDA 的 `<<<grid, block>>>` |
| `T.alloc_shared(shape, dtype)` | 分配 shared memory 缓冲区 | CUDA 的 `__shared__` |
| `T.alloc_fragment(shape, dtype)` | 分配 register 级 fragment | Triton 的 tile 变量 |
| `T.alloc_var(...)` | 分配标量变量 | 普通变量 |
| `T.copy(src, dst)` | 在内存层级间搬运 tile（自动插入屏障） | 手写的 `ldmatrix` / `stmatrix` / 同步 |
| `T.serial(...)` | 串行循环 | `for` 循环 |
| `T.Parallel(...)` | 嵌套并行循环 | 映射到 GPU 的并行执行 |
| `T.Pipelined(iters, num_stages=N)` | 软件流水线（producer/consumer 异步） | 类似 CUTLASS 的 pipeline stages |
| `T.unroll(...)` | 循环展开 | `#pragma unroll` |
| `T.ceildiv(a, b)` | 向上取整除法 | `triton.cdiv` |

### 内存层级：显式管理

TileLang 和 Triton 最大的区别就是**是否显式管理内存层级**：

| | Triton | TileLang |
|---|---|---|
| shared memory | 编译器自动分配和同步 | `T.alloc_shared` 显式声明 |
| register fragment | 编译器管理 | `T.alloc_fragment` 显式声明 |
| 数据搬运 | `tl.load` / `tl.store` 一行搞定 | `T.copy(src, dst)` 在 scope 间搬运 |
| 同步 | 编译器自动插入 barrier | `T.copy` 隐含 barrier |

这种显式设计让你更精细地控制数据流（更适合做 pipeline、double buffering 等高级优化），代价是代码更啰嗦。

### 和 TVM 的关系

TileLang 的 kernel 编译为 TVM TIR（Tensor IR），然后走 TVM 的后端生成 GPU/CPU 代码。这意味着：
- 天然继承 TVM 的 auto-tuning 基础设施（AutoTVM / MetaSchedule）
- 可以 target 多种后端（CUDA GPU、ROCm GPU、x86/ARM CPU）
- 但目前成熟度远不如 TVM 本身——TileLang 是 2025 年的论文项目（v0.1.x），仍在快速迭代

### 四层抽象栈中的位置

```
抽象层级（高 = 开发快）
  ▲
  │  Triton        编译器全包，块级，内存管理自动
  │  TileLang      显式内存层级 + TVM 编译，tile 是一等公民
  │  CUTLASS       CUDA C++ 模板拼积木，性能天花板最高
  │  CUDA         线程级，手动管理一切
  └──────────────────────────────────────────────────────► 性能天花板（高 = 跑得快）
```

TileLang 填的是 CUTLASS 和 Triton 之间的缝隙：**比 CUTLASS 抽象高（不用写线程代码），比 Triton 控制细（显式管内存层级和搬运）。** 外加 TVM 生态的 auto-tuning 加持。

## 常见误区

- **「TileLang 就是 TVM 换了个皮」**——不是。TVM 的 TE（Tensor Expression）和 TensorIR 是通用的张量计算抽象，目标是 auto-scheduling 和跨硬件部署。TileLang 专门面向 tile-level GPU/CPU kernel 编程，定位更窄但更深——它优化的是手写 kernel 的开发体验，不是端到端模型部署。
- **「TileLang 可以替代 Triton」**——目前不行。TileLang 还太年轻（2025 论文，v0.1.x），生态、文档、社区远不如 Triton。但它在显式内存控制和 TVM auto-tuning 集成上有独特优势，值得关注。
- **「基于 TVM 意味着性能不如原生 CUDA」**——不一定。TVM 的代码生成质量在 GEMM 类运算上已经非常接近手写 CUDA。TileLang 的瓶颈不是 TVM，是它还年轻的抽象层是否足够薄、是否泄漏了硬件细节。

## 面试常见问题

- **Q**: TileLang 提供了哪三个抽象层级？各对应什么使用场景？
  **A**: Level 1（纯计算逻辑，编译器/auto-tuner 全包调度和优化）适合快速原型和不关心硬件细节的场景，类似 TVM 的 TE。Level 2（用户感知 shared memory、tiling、thread block 但不显式管线程）是主推层级——你写 `T.gemm`、`T.copy`、`T.Pipelined`，编译器通过 layout inference 推导 buffer 形状和布局，类似 Triton 但多了显式内存层级控制。Level 3（线程级原语，几乎等同于手写 CUDA）给性能专家用，可以做 inline PTX、手动 warp specialization。同一个 kernel 里可以混用不同 level——核心路径用 Level 3 追求极致，其余用 Level 2 降低开发成本。

- **Q**: TileLang 和 Triton 的核心区别是什么？什么时候选 TileLang 而不是 Triton？
  **A**: 三个关键区别：（1）TileLang 显式管理内存层级——`T.alloc_shared`、`T.alloc_fragment`、`T.copy` 让你决定数据在哪，而 Triton 编译器自动决定 shared memory 分配；（2）TileLang 基于 TVM，天然集成 auto-tuning（AutoTVM/MetaSchedule），Triton 有自己的 autotuner；（3）TileLang 支持 GPU+CPU 双目标，Triton 以 GPU 为主。选 TileLang 不选 Triton 的场景：需要精细控制 pipeline staging 和 warp partitioning（如 MLA 的 warpgroup split）、需要跨 NVIDIA/AMD 的单一 kernel source、或需要 TVM 生态的 auto-tuning 基础设施。

- **Q**: 什么是 TileLang 的 layout inference？它在 MLA kernel 中怎么发挥作用？
  **A**: Layout inference 是 TileLang 的核心优化技术——用户写 `T.gemm(A, B, C, policy=FullCol)` 这样的高层语义，编译器自动推导 buffer 的所需形状和最优布局（包括 swizzled layout、warp 间数据分布）。在 MLA decode kernel 中，Q@K 的结果需要在 P@V 阶段被完整使用，但两个 warpgroup 各只有一半 acc_s。Layout inference 做的是：从 `policy=FullCol` 推断每个 warpgroup 需要完整 acc_s（形状 `[block_M, block_N]`），向前传播到 staging buffer `S_shared`，再向后传播到 Q@K 阶段每个 warpgroup 的 score slab（形状 `[block_M, block_N/2]`）。用户写的是 warp policy 和数学公式，编译器推导出所有中间 buffer 的形状、swizzle 模式、以及 warp-specialized producer/consumer 同步代码。

- **Q**: GPU 编程中 threadblock swizzling 是什么？TileLang 里怎么做？
  **A**: Threadblock swizzling 是一种优化 L2 cache 命中率的调度技术——传统按 grid 自然顺序调度 threadblock，相邻 block 访存区域不连续导致 L2 cache 低效。Swizzling 用数学映射（对角映射、交错映射）重排 threadblock 执行顺序，使连续调度的 block 访问相邻或重叠的数据区。TileLang 里一行代码搞定：`T.use_swizzle(panel_size: int, order: str = "row")`，指定 swizzle 面板大小和模式。类似地，shared memory swizzling 用 `T.annotate_layout({buf: T.layout.make_swizzled_layout(buf)})` 用 XOR 地址重映射解决 bank conflict。

- **Q**: TileLang 目前主要局限是什么？
  **A**: （1）年轻——2025 年论文，v0.1.x，API 还在快速迭代，文档不完整；（2）生态——远不如 Triton（OpenAI + 社区）或 CUTLASS（NVIDIA 官方）成熟，生产部署案例少；（3）调试工具——不如 CUDA Nsight 或 Triton 的调试基础设施；（4）社区——遇到问题找到答案的概率远低于 Triton/CUTLASS。适合关注 GPU kernel 编程前沿、或需要 TVM 生态集成的团队，但不建议作为唯一的 kernel 编写工具。

## 关联

- [GPU 执行模型](gpu-execution-model.md) — TileLang 的前置知识，理解内存层级后才能理解 `T.alloc_shared` / `T.alloc_fragment` 的意义
- [CUTLASS](cutlass.md) — 同一栈的下一层：CUDA 模板库，性能天花板更高但抽象更低
- [Triton](triton.md) — 同一栈的上一层：编译器全包，开发效率更高但内存控制更粗
