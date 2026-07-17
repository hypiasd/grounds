---
title: vLLM 总览
topic: vllm
tags: [llm-inference, serving, pagedattention, continuous-batching]
summary: vLLM 源码学习笔记主题，覆盖 V1 架构、PagedAttention、Continuous Batching 与调度器。
created: 2026-07-14
updated: 2026-07-14
---

## 这个主题是什么 / 学习目标

vLLM 是一个高吞吐量的 LLM 推理服务引擎。核心创新是 PagedAttention（KV cache 分页管理）和 Continuous Batching（混合 prefill/decode 调度）。2025 年起 V1 架构全面替代 V0，调度器、KV cache 管理、引擎核心循环均重构。

## 包含笔记

- [vLLM V1 架构与 PagedAttention](vllm-v1-architecture.md) — 四层流水线架构、PagedAttention 分页机制、V1 vs V0 迁移、与 FlashAttention 的互补关系
- [Continuous Batching 与调度器](continuous-batching-scheduler.md) — schedule() 算法、token budget 驱动、抢占机制（recompute 非 swap）、FCFS 公平边界

## 知识脉络

建议先读架构笔记建立整体心智模型（四层流水线 + PagedAttention 核心思想），再深入调度器理解核心循环（token budget 驱动、running/waiting 队列调度、抢占与公平性）。后续可扩展的方向：GPUModelRunner 的 forward 流程、KV cache 管理的 block 分配细节、prefix caching 的 hash 机制。

## 未解问题

- KV cache 的 block 分配算法细节（BlockPool 内部机制）
- Prefix caching 的 block hash 匹配与复用流程
- GPUModelRunner 一次 forward 的完整数据流
- V1 的 async scheduling 与非阻塞设计
- speculative decoding 在调度器中的集成方式

## 关联

- 源码快照：[vLLM 仓库](../../raw/wiki/vllm/) — `vllm/v1/` 为核心目录
