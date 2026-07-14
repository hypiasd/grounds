# cuda 总览

## 这个主题是什么 / 学习目标

GPU 编程的基础概念与模型，涵盖线程层级、硬件执行、内存体系。是学习 CUDA 编程和后续 Triton 的前置知识。

## 包含笔记

- [GPU 线程层级模型](gpu-thread-hierarchy.md) — 软件（Grid/Block/Thread）与硬件（SM/CUDA Core）两套层级如何对接，kernel 从编写到执行的完整链路，Block 作为协作边界的意义
- [Warp 与 SIMT](warp-and-simt.md) — Warp 是 32 线程的硬件调度单位，SIMT 锁步执行，warp divergence 和 latency hiding
- [GPU 内存层级](gpu-memory-hierarchy.md) — 寄存器/共享内存/显存三层结构，共享内存 vs 显存的本质区别，核心优化模式

## 知识脉络

推荐阅读顺序：

1. **GPU 线程层级模型** — 地基，理解“谁在跑”：软件和硬件两套体系如何对接
2. **Warp 与 SIMT** — 深入“怎么跑”：硬件执行细节，为什么 32 是魔法数字
3. **GPU 内存层级** — 理解“数据在哪”：内存三层结构及共享内存优化的原理

## 未解问题

- Triton 如何抽象掉 CUDA 的线程层级细节（待学）
- Occupancy 调优的具体方法
- 不同 GPU 架构（Volta/Ampere/Hopper）的 SM 差异
