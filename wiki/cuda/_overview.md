# cuda 总览

## 这个主题是什么 / 学习目标

GPU 编程基础，涵盖执行模型（线程层级、warp/SIMT）和内存体系。是学习 CUDA 编程和后续 Triton 的前置知识。

## 包含笔记

- [GPU 执行模型](gpu-execution-model.md) — 线程层级（Grid/Block/Thread + SM/CUDA Core）、Warp 与 SIMT（warp divergence、latency hiding）、GPU 内存层级（寄存器/共享内存/显存），三面相合一

## 知识脉络

推荐阅读顺序即笔记内章节顺序：线程层级 → Warp/SIMT → 内存层级。三个面相咬合——block 存在是为了 shared memory 和同步，warp 的 latency hiding 掩盖的正是显存延迟。

## 未解问题

- Triton 如何抽象掉 CUDA 的线程层级细节（待学）
- Occupancy 调优的具体方法
- 不同 GPU 架构（Volta/Ampere/Hopper）的 SM 差异
