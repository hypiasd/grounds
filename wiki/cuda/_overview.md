---
title: CUDA / GPU 编程总览
topic: cuda
tags: [gpu-programming, parallel-computing]
summary: GPU 编程的基础概念集合——线程模型、执行模型、内存层级，是学习 Triton 等高层 GPU 编程框架的前置知识。
created: 2026-07-14
updated: 2026-07-14
---

# CUDA / GPU 编程 总览

## 这个主题是什么 / 学习目标

GPU 编程的底层心智模型：理解 GPU 如何组织线程、如何执行指令、内存层级如何工作。这是写任何 GPU kernel（CUDA、Triton、HIP）的地基。

## 包含笔记

- [GPU 执行模型](gpu-execution-model.md) — kernel→grid→block→SM→warp→thread 的完整链路，软件组织与硬件执行的对接

## 知识脉络

1. 先学 GPU 执行模型，建立 grid/block/thread/warp/SM 的全局图景
2. （待补）CUDA 内存层级：global memory / shared memory / registers
3. （待补）Triton：基于 block-level 抽象的 GPU 编程框架

## 未解问题

- Triton 如何在 block-level 抽象上简化 GPU 编程？（用户最初想学的概念，待后续 learn）
- CUDA 优化核心手段：tiling、occupancy 调优的具体实践
