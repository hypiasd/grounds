---
title: Triton
topic: cuda
tags: [gpu, parallel-computing, compiler, kernel-programming, performance]
summary: Triton 是 OpenAI 开源的 GPU 内核编程语言和编译器，将 GPU 编程从"线程级"提升到"块级"——你只管数据怎么切 tile，编译器自动分配线程、插入同步、优化访存。核心语法只有几个零件：program_id（定位）、tl.arange（生成索引）、tl.load/store（读写）、tl.constexpr（编译时常量）、reductions（规约）。适合规整的 tiled computation，不规则计算仍需 CUDA。
created: 2026-07-15
updated: 2026-07-16
---


## TL;DR

Triton 让你用 Python 风格语法写 GPU kernel，不需要管理 threadIdx/blockIdx/shared memory/同步。核心理念：**你描述"一个 tile 做什么"，编译器生成"线程怎么做"。** 一个 Triton kernel 永远是 `定位 → 加载 → 计算（含 K 方向循环） → 写回` 四步骨架。擅长矩阵乘法、softmax、LayerNorm 等规整计算，性能接近 cuBLAS 的 80-95%。

## 核心概念

### 设计动机：为什么需要 Triton

CUDA 编程有三个痛点：手动管理线程映射到数据、手写 shared memory tiling 和同步、手调 memory coalescing 和 bank conflict。Triton 把这三种脏活交给编译器。

类比：**CUDA 是你安排每个工人具体拧哪颗螺丝，Triton 是你把一箱货交给一组工人说"这一箱归你们"，组内分工由小组长（编译器）自己安排。**

### 块级 vs 线程级

| | CUDA | Triton |
|---|---|---|
| 编程粒度 | 线程（thread） | 块（tile / program instance） |
| 定位方式 | `blockIdx + threadIdx` 两层坐标套算 | `program_id(axis)` 一层坐标 |
| 数据索引 | 手动算 `pid * blockDim + tid` | `pid * BLOCK + tl.arange(0, BLOCK)` 一行搞定 |
| 共享内存 | 手动 `__shared__` + `__syncthreads()` | 编译器自动分配和同步 |
| 访存优化 | 手动调 coalescing / bank conflict | 编译器自动优化 |
| 启动语法 | `kernel<<<grid, block>>>(args)` | `kernel[(grid,)](args)` |

### 核心语法

```python
import triton
import triton.language as tl

@triton.jit                          # 声明 GPU kernel（= CUDA 的 __global__）
def kernel(ptr, N, BLOCK: tl.constexpr):
    pid   = tl.program_id(0)         # 我是第几个 tile？（= CUDA 的 blockIdx）
    offs  = pid * BLOCK + tl.arange(0, BLOCK)  # 本 tile 覆盖的所有索引
    mask  = offs < N                 # 边界保护
    data  = tl.load(ptr + offs, mask=mask)     # 加载
    # ... 计算 ...
    tl.store(ptr + offs, result, mask=mask)    # 写回

# 启动：方括号里是 grid（多少个 tile），圆括号里是 kernel 参数
kernel[(triton.cdiv(N, BLOCK),)](ptr, N, BLOCK=BLOCK)
```

**语法零件清单：**

- `@triton.jit` — 标记 GPU kernel，JIT 编译为 PTX
- `tl.program_id(axis)` — 返回当前 tile 在 grid 里的第几个位置（标量整数）。`axis=0` 是第一维，`axis=1` 是第二维
- `tl.arange(0, N)` — 返回编译时向量 `[0, 1, ..., N-1]`，形状 `(N,)`。所有后续运算在此向量上逐元素进行
- `tl.load(ptr, mask=..., other=...)` — 从显存加载。`mask` 为 False 的位置用 `other` 填充（默认 0）
- `tl.store(ptr, data, mask=...)` — 写回显存。`mask` 为 False 的位置不写
- `tl.constexpr` — 编译时常量。tile 大小必须标这个，编译器据此做寄存器分配和循环展开
- `tl.sum(x, axis=0)` / `tl.max(x, axis=0)` — 规约操作。编译器自动用 shared memory 做 warp-level reduction
- 指针算术支持 NumPy 风格的广播（`[:, None]` / `[None, :]`）来生成多维地址

### 矩阵乘法：完整示例

```python
@triton.jit
def matmul_kernel(A, B, C, M, N, K,
                  BLOCK_M: tl.constexpr, BLOCK_N: tl.constexpr, BLOCK_K: tl.constexpr):
    # ── 定位：我算 C 的哪个 tile？ ──
    pid_m = tl.program_id(0)
    pid_n = tl.program_id(1)
    offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)   # 行号
    offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)   # 列号

    # ── 累加器 ──
    acc = tl.zeros((BLOCK_M, BLOCK_N), dtype=tl.float32)

    # ── 沿 K 方向滑动 ──
    for k in range(0, K, BLOCK_K):
        offs_k = k + tl.arange(0, BLOCK_K)
        a = tl.load(A + offs_m[:, None] * K + offs_k[None, :])  # [BLOCK_M, BLOCK_K]
        b = tl.load(B + offs_k[:, None] * N + offs_n[None, :])  # [BLOCK_K, BLOCK_N]
        acc += tl.dot(a, b)   # 自动走 Tensor Core

    # ── 写回（带边界保护）──
    mask = (offs_m[:, None] < M) & (offs_n[None, :] < N)
    tl.store(C + offs_m[:, None] * N + offs_n[None, :], acc, mask=mask)
```

**为什么沿 K 方向循环？** 矩阵乘法可以分块计算，这是数学恒等式：一个输出 tile = Σ(A 的行 tile × B 的列 tile)，沿共享的 K 维度累加。每次循环搬一个 K 方向的 tile 进寄存器/SRAM，搬完累加，再搬下一批——用多次小搬运代替一次大搬运，把数据放在更近的内存里反复用。

**指针算术中的广播**（以加载 A 为例）：

```
offs_m = [0, 1, ..., 15]         形状 (16,)
offs_k = [0, 1, ..., 31]         形状 (32,)
K = 128（A 的列数）

offs_m[:, None] * K             → [[0], [128], ..., [15*128]]    形状 (16, 1)
offs_k[None, :]                 → [[0, 1, ..., 31]]              形状 (1, 32)
相加（广播）                     → [[0, 1, ..., 31],
                                    [128, 129, ..., 159],
                                    ...
                                    [15*128, ..., 15*128+31]]    形状 (16, 32)
```

本质上就是把二维索引 `A[row][col]` 转成一维显存地址 `addr = row × K + col`，然后广播一次性算出整个 tile 的所有地址。

**Mask 的广播**：

```python
mask = (offs_m[:, None] < M) & (offs_n[None, :] < N)
```

`offs_m[:, None] < M` 产生 `(BLOCK_M, 1)` 的布尔列向量（逐行判断是否 < M），`offs_n[None, :] < N` 产生 `(1, BLOCK_N)` 的布尔行向量（逐列判断是否 < N）。两者做 `&` 时广播成 `(BLOCK_M, BLOCK_N)`——行和列各自独立判断是否越界，广播把两维判定组合成完整的 2D mask。

### Triton 编译器做了什么

1. **分配线程**：根据 tile 大小自动决定用多少线程去搬数据
2. **插入同步**：在加载和计算之间自动插入 barrier，用户不写 `__syncthreads`
3. **优化访存**：自动排列内存访问顺序，保证 coalescing，消除 bank conflict

## 直觉 / 类比

- CUDA 是给每个工人发一张纸条，精确写上他负责哪个 10cm×10cm 的方格。Triton 是把一面墙切成大方块，每组工人领一块说"这一平方米归你们"
- Triton 之于 CUDA，如同 SIMD intrinsics 之于手写汇编——你指定数据级并行，编译器处理指令级细节

在 GPU 编程抽象栈中，Triton 处于最高层——编译器全包，块级编程，内存管理自动。下面是 TileLang（显式内存层级 + TVM）、CUTLASS（CUDA 模板拼积木）、CUDA（线程级手动管理）：

```
抽象层级（高 = 开发快）
  ▲
  │  Triton        Python DSL + 自研编译器 → LLVM/PTX，块级，编译器管线程/内存
  │  TileLang      基于 TVM 的 tile DSL，tile 一等公民，显式管内存层级
  │  CUTLASS       CUDA C++ 模板库，拼 tile 积木，仍在 CUDA 生态内
  │  CUDA          线程级，手动管理一切（线程映射、shared memory、同步）
  └──────────────────────────────────────────────────────► 性能天花板（高 = 跑得快）
```

这个栈的核心张力是**控制 vs 效率**：每往上一层，开发效率提升，但精细控制减少。Triton 适合快速原型和规整计算，CUTLASS 适合需要极致性能和新硬件特性（如 H100 TMA）的定制 kernel，TileLang 在两者之间填了一个显式内存控制 + TVM auto-tuning 的生态位。

## 常见误区

- **Triton 不是 CUDA 的通用替代品**：它擅长规整的 tiled computation（矩阵乘法、element-wise ops、reduction），遇到不规则数据（稀疏矩阵、图遍历、树结构）时 tile 边界对不齐，编译器无法优化，仍需 CUDA
- **Triton kernel 不是在 Python 解释器里跑的**：通过 LLVM JIT 编译成 PTX——和 nvcc 编译 CUDA 到的中间表示是同一层，性能与手写 CUDA 差距通常在 20% 以内
- **Triton 不暴露 warp 级操作**：如果你需要 `__shfl_xor_sync` 做 warp shuffle，目前只能用 CUDA
- **Block 和 SM 不是一一对应**：一个 block 一定只在一个 SM 上跑（因为 shared memory 是 SM 内物理隔离的），但一个 SM 可以同时跑多个 block，只要寄存器/共享内存够用

## 适用 vs 不适用的场景

**Triton 擅长**：
- 矩阵乘法、softmax、LayerNorm、attention 等规整计算
- 需要快速出 kernel 原型的场景
- 在 PyTorch 生态中写自定义算子

**Triton 不擅长 / 不适用**：
- 稀疏矩阵、图计算、不规则数据结构
- 需要 warp-level 精细控制（warp shuffle、warp vote）
- 使用 Triton 版本尚未支持的新硬件特性（如 SM 90+ 的某些特殊指令）

## 面试常见问题

- **Q**: Triton 的 tile-based 编程模型和 CUDA 的 thread-based 模型的核心区别是什么？这个抽象牺牲了什么？
  **A**: CUDA 你为一个线程写代码——手动算 threadIdx/blockIdx 映射到数据、管理 shared memory、处理 warp 级同步。Triton 你为一个 block（tile）写代码——指定块加载什么数据（tl.load + 偏移范围）、块算什么、结果存哪。编译器接管线程索引、shared memory 分块和 memory coalescing。代价是 Triton 不暴露 warp 级操作（warp shuffle、warp vote），无法自定义 shared memory 布局，不适用于不规则的访存模式。对于 tile-load-compute-store 模式的 kernel，Triton 通常能达到手写 CUDA 的 80-95% 性能，开发时间是 20-30%。

- **Q**: 什么时候会选 CUDA 而不是 Triton？给一个 Triton 确实比不过 CUDA 的具体例子。
  **A**: 最典型的场景是需要 warp-level shuffle 做 reduction。比如写一个直方图 kernel（统计 0-255 每个值的出现次数），高效的 CUDA 做法是用 `__shfl_down_sync` 在 warp 内做归约（每次移动 16→8→4→2→1，一步一个时钟周期，不需要 shared memory）。Triton 没有 warp shuffle 的等价物——它的 `tl.sum` 归约走的是通用路径，必须经过 shared memory，增加了延迟和 bank conflict 风险。这种情况下精心写的 CUDA kernel 通常比 Triton 快 2-3 倍。另一个案例是 H100 的 TMA（Tensor Memory Accelerator），可以用单条指令从全局内存加载 tile 到 shared memory，释放所有计算线程——CUTLASS 广泛使用 TMA 达到接近理论峰值的吞吐，Triton 有部分支持但不如 CUTLASS 灵活。

- **Q**: Triton kernel 和 PyTorch reference 之间的数值不一致通常由什么引起？
  **A**: 四个主要原因：**（1）累加顺序**——浮点加法不满足结合律，Triton 的 `tl.dot` 累加顺序和 PyTorch 的 cuBLAS matmul 不同，FP16 下用 `atol=1e-2` 验证即可。**（2）累加器 dtype 错误**——累加器应该是 float32（`tl.zeros(..., dtype=tl.float32)`），如果用 FP16 会在处理大矩阵时溢出或丢失精度。**（3）mask 未正确应用**——如果 `tl.load` 不传 `mask=mask`，越界元素加载的是未定义值（垃圾数据），最后一个 tile 的 softmax 会在垃圾数据上计算。**（4）stride 错误**——如果 tensor 被 transpose 或 slice 过，stride 和你的假设可能不匹配，kernel 开头应加 `assert tensor.is_contiguous()`。

## 关联

- [GPU 执行模型](gpu-execution-model.md) — Triton 的前置知识，理解线程层级/warp/SIMT/内存层级后才能理解 Triton 抽象掉了什么
- [vLLM 架构](../vllm/vllm-v1-architecture.md) — vLLM 中大量自定义 kernel 用 Triton 实现
- [CUTLASS](cutlass.md) — CUDA 生态内的模板化 GEMM 框架，性能天花板更高但抽象更低
- [TileLang](tilelang.md) — 基于 TVM 的 tile DSL，显式内存层级控制，填在 CUTLASS 和 Triton 之间的生态位
