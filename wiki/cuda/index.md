---
title: cuda 总览
topic: cuda
tags: [cuda, gpu]
summary: GPU 编程基础与工具栈。
created: 2026-07-17
updated: 2026-07-17
---

## 这个主题是什么 / 学习目标

GPU 编程基础与工具栈，涵盖执行模型（线程层级、warp/SIMT）、内存体系，以及四层 GPU 编程抽象：CUDA（线程级）→ CUTLASS（模板拼积木）→ TileLang（tile DSL + TVM）→ Triton（块级编译器全包）。

## 包含笔记

- [GPU 执行模型](gpu-execution-model.md) — 四面相：线程层级（Grid/Block/Thread + SM）、Warp/SIMT、内存层级、SM 内部结构（CUDA Core 做标量 FMA + Tensor Core 做矩阵 MMA），涵盖混合精度原理与硬件定位
- [GPU 浮点格式](float-formats.md) — FP32/FP16/BF16/TF32/FP8/FP4 的 IEEE 754 结构对比，指数管范围 vs 尾数管精度，BF16 为什么是训练甜点
- [Triton](triton.md) — 块级 GPU 编程语言/编译器，用 Python 风格语法写 kernel，编译器自动管理线程、共享内存和同步
- [CUTLASS](cutlass.md) — NVIDIA 开源的 CUDA C++ 模板库，把 GEMM 拆成可组合的 tile 零件（TiledCopy/TiledMMA/Epilogue），追求极致性能；涵盖 CuTe（3.x 核心抽象层）、cuBLAS/cuBLASLt 的区别与选择
- [TileLang](tilelang.md) — 基于 TVM 的 tile-level DSL，tile 是一等公民，显式管理内存层级（shared/fragment），填在 CUTLASS 和 Triton 之间的生态位
- [权重量化内核效率](weight-quantization-kernel-efficiency.md) — 权重量化提速取决于「字节红利 vs 内核税」：W8 省 2× 不够（exp12 实测慢），INT4+Marlin 省 4× + 生产内核才够；瓶颈是内核质量不是访存次数
- [Triton matmul 拆解](triton-matmul.md) — 一个 Triton matmul = host 只启动 + kernel 只写一个输出块；2D 网格扁平成 1D program_id，指针+stride 迭代，K 循环 tl.dot 累加，mask 护边缘；off/ptr/mask 三件套与寻址手算
- [Triton 张量核限制](triton-tensor-core-limitations.md) — `tl.dot(fp16/int8)` 不会自动吃张量核；红利须编译器 lowering 成 mma.sync 才兑现；Triton 3.x + Turing(sm_75) 下 fp16 退回 CUDA core、int8 编译崩溃，根因是上游把 MMA 路径 gated 到 sm80+

## 知识脉络

推荐阅读顺序：GPU 执行模型（线程层级 → Warp/SIMT → 内存层级 → SM 内部结构）→ GPU 浮点格式 → CUTLASS → TileLang → Triton。
四层抽象栈的核心张力是控制 vs 效率：
- CUDA 线程级手动管理，性能天花板最高但开发最慢
- CUTLASS 用模板拼积木，性能几乎无损，学习曲线陡
- TileLang 显式 tile + TVM 编译，在控制和效率间找平衡
- Triton 编译器全包，块级编程，开发最快但精细控制最少

## 未解问题

- Occupancy 调优的具体方法
- 不同 GPU 架构（Volta/Ampere/Hopper）的 SM 差异
