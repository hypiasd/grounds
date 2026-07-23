---
title: Triton matmul 拆解
topic: cuda
tags: [triton, gpu, gemm, kernel, matmul]
summary: 一个 Triton matmul = host 只启动 + kernel 只写一个输出块；2D 网格扁平成 1D program_id，指针+stride 迭代而非重索引，K 循环 tl.dot 累加，mask 护边缘。类比「只写一块怎么算，编译器铺满整张 C」。
created: 2026-07-23
updated: 2026-07-23
---

## TL;DR

一个 Triton matmul kernel 只描述「C 的一个输出块怎么算」，框架把它复制到整个网格并行。读它的钥匙：`program_id` 反推负责哪块、指针+`stride` 算地址、K 循环 `tl.dot` 累加、`mask` 护边缘。与手写 tiled_gemm 的「块网格 × K 循环累加」同构。

## 核心概念

### 1. 两层结构

- **host（Python `matmul`）**：分配 C、算 `grid`、传 `stride` 与形状。
- **device（kernel）**：只写「**一个输出块**」的逻辑，Triton 自动映射到 `(⌈M/BM⌉ × ⌈N/BN⌉)` 个 program 并行；你不用碰线程 / warp / shared mem。

### 2. 2D 网格扁平成 1D program_id

- `grid` 是 1 维的；逻辑上是 2D 块网格。
- `pid_m = pid // num_pid_n`、`pid_n = pid % num_pid_n`（行主序展开）。
- `offs_m = pid_m*BM + tl.arange(0,BM)`、`offs_n = pid_n*BN + tl.arange(0,BN)` 是这块在 C 中的行/列坐标。

### 3. off / ptr / mask 三件套

- **off（坐标，不含地址）**：`tl.arange` 造的向量，`offs_m`=行号、`offs_n`=列号、`offs_k`=K 窗内偏移。
- **ptr（地址，一整块）**：`a_ptrs = a_base + offs_m[:,None]*stride_am + offs_k[None,:]*stride_ak`，用「坐标×步长」广播出 `(BM,BK)` 指针矩阵，`tl.load` 一把搬整块；循环里 `a_ptrs += BK*stride_ak` 让 K 窗滑动（不重算索引）。`stride` = 相邻元素距离：连续张量下 `stride_am=K, stride_ak=1, stride_bk=N, stride_bn=1`。
- **mask（护盾）**：形状非 BLOCK 整数倍时 `mask=坐标<剩余` 挡越界，配 `other=0.0` 让越界 load 填 0 不污染累加；store 同理护 M/N 边缘。

### 4. K 循环 = 分块 GEMM 的内积分块累加

```python
acc = tl.zeros((BM, BN), dtype=tl.float32)
for k in range(tl.cdiv(K, BK)):
    acc = tl.dot(a_tile, b_tile, acc)
```

- `tl.dot(a, b, acc)` 的**第三参才是累加器**；漏传则每轮覆盖、只算最后一块 K（最易犯的错）。
- 与手写 tiled_gemm 的 `acc += A_tile @ B_tile` 一一对应。

### 5. 寻址手算示例（M=64, K=96, N=64, B=32, pid=0）

- A 连续：`stride_am=K=96, stride_ak=1` → `a_ptrs[i,j] = a_base + i*96 + j`。左上：`a[0,0]=+0, a[0,1]=+1, a[1,0]=+96`（行跳 96 = 跳一行 K）。首窗读 A 行[0..31]×列[0..31]；循环 `a_ptrs += 32` 滑到列[32..63]→[64..95]（`cdiv(96,32)=3` 窗）。
- B：`stride_bk=N=64` → `b_ptrs[i,j] = b_base + i*64 + j`。首窗读 B 行(K)[0..31]×列[0..31]；循环 `b_ptrs += 32*64 = 2048`。
- 3 窗 `tl.dot` 累加 → `c_ptrs = c_base + offs_m[:,None]*64 + offs_n[None,:]` = C 左上块[0..31,0..31]。
- `pid=2 (pid_m=1)`：`offs_m=[32..63]`，仅 base 行号 +32 → `a_ptrs` 首行 = `a_base + 32*96 = 3072`，其余同构。

## 直觉 / 类比

写 kernel 像写「一块砖墙怎么砌」的说明书：你只描述「这一小块砖（输出块）用哪几摞砖（A/B 的对应窗）砌、怎么累加」，Triton 这个包工头把说明书复印 N 份、分给 N 个工人（program）同时砌，最后拼成整面墙（C）。

## 常见误区

- **误区：`tl.dot` 会自动累加。** 实际第三参 `acc` 才接回上轮结果；不传就是覆盖（等价于只算最后一块 K）。
- **误区：要把整个 C 的索引逻辑写进 kernel。** 不用——只写「一个块」，`program_id` 决定每个 program 负责哪块。
- **误区：用高级索引 `A[i,j]`。** Triton 直接操作指针+偏移（`ptr + off*stride`），一把 load 整块，这才是分块快的根源。

## 面试常见问题

- **Q**：Triton 和 CUDA 写 GEMM 最大区别？

  **A**：CUDA 要管线程 / warp / shared mem 三维；Triton 只写「一个块」，编译器生成线程与共享内存管理。代价是精细控制少，但块级编程最快。

- **Q**：为什么 mask 要配 `other=0.0`？

  **A**：边缘块越界位置若读垃圾会污染累加；填 0 使 `tl.dot` 乘积为 0，不影响正确结果。

## 关联

- [分块 GEMM 的原理与切法](../gemm/tiled-gemm.md) — Triton kernel body 与 tiled_gemm 同构（块网格 × K 循环累加）
- [Roofline 模型与算术强度](../gpu/roofline.md) — 同一个 kernel 在不同形状下快慢由 AI 决定
- 项目实践：vllm-plus 路径 A·M1（`project_logs/vllm-plus/runbook.md` 节点 17）
