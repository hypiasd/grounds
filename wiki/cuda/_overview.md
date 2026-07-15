# cuda 总览

## 这个主题是什么 / 学习目标

GPU 编程基础，涵盖执行模型（线程层级、warp/SIMT）和内存体系。是学习 CUDA 编程和 Triton 的前置知识。Triton 笔记已就位。

## 包含笔记

- [GPU 执行模型](gpu-execution-model.md) — 线程层级（Grid/Block/Thread + SM/CUDA Core）、Warp 与 SIMT（warp divergence、latency hiding）、GPU 内存层级（寄存器/共享内存/显存），三面相合一
- [Triton](triton.md) — 块级 GPU 编程语言/编译器，用 Python 风格语法写 kernel，编译器自动管理线程、共享内存和同步

## 知识脉络

推荐阅读顺序：GPU 执行模型（线程层级 → Warp/SIMT → 内存层级）→ Triton。三个面相咬合——block 存在是为了 shared memory 和同步，warp 的 latency hiding 掩盖的正是显存延迟；Triton 在此之上抽象掉线程管理，让你在块级别编程。

## 未解问题

- Occupancy 调优的具体方法
- 不同 GPU 架构（Volta/Ampere/Hopper）的 SM 差异
