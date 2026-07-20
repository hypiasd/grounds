---
title: llaisys 总览
topic: llaisys
tags: [llm-inference, cpp, systems]
summary: 从零构建 LLM 推理引擎（InfiniTensor LLAISYS 教学项目），涵盖框架分层、Tensor 数据结构、LLM 算子实现、Qwen2 模型推理全链路。
created: 2026-07-20
updated: 2026-07-20
sources:
  - ../../raw/wiki/llaisys/
---

## 这个主题是什么 / 学习目标

LLAISYS（Let's Learn AI SYStem）是 InfiniTensor 的教学项目，用 C++ 从零实现一个完整的 LLM 推理引擎。本主题记录从零到跑通 Qwen2 模型推理的全部实现——框架设计、Tensor、算子、模型。

## 包含笔记

- [框架分层与设备抽象](framework-architecture.md) — 三层架构（Python→C API→C++）、Runtime API 函数指针表、Context/Runtime 设备管理、算子分发模式
- [Tensor 实现](tensor.md) — storage/offset/meta 三件套，view/permute/slice 零拷贝，完整 C++ 实现
- [算子实现](operators.md) — 7 个 LLM 核心算子的 CPU 实现（argmax/embedding/linear/rms_norm/rope/self_attention/swiglu）
- [Qwen2 模型推理](qwen2-model.md) — 完整 forward + KV Cache + Python 前端，从 token 到 token

## 知识脉络

推荐阅读顺序：框架架构（理解分层）→ Tensor（理解数据结构）→ 算子（理解计算）→ 模型（串联全链路）。

与已有知识的关联：
- [vLLM V1 架构](../vllm/vllm-v1-architecture.md) 是"站在调度层看引擎"，LLAISYS 是"站在算子层看引擎"
- [CUDA/GPU](../cuda/index.md) 的浮点格式和 GPU 执行模型对应 LLAISYS 的多 dtype 支持和设备抽象

## 未解问题

- Assignment #4（CUDA 集成）未实现——需要 NVIDIA GPU
- 算子性能优化（SIMD、tiling）未涉及
- KV Cache 的内存管理优化（PagedAttention 式分页）未涉及
