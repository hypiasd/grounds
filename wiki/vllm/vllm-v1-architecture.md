---
title: vLLM V1 架构与 PagedAttention
topic: vllm
tags: [llm-inference, serving, pagedattention, gpu-memory, kv-cache]
summary: vLLM V1 采用四层流水线架构（LLMEngine → EngineCore → Scheduler → Worker/GPUModelRunner），PagedAttention 将 KV cache 按固定大小 block 分页管理，类比 OS 虚拟内存，BlockPool + KVCacheManager + block table 实现逻辑到物理 block 的映射。
created: 2026-07-14
updated: 2026-07-14
---


## TL;DR

vLLM 是一个高吞吐量的 LLM 推理服务引擎。V1 架构采用四层流水线：LLMEngine（API 入口）→ EngineCore（核心调度循环）→ Scheduler（每步决策）→ Worker/GPUModelRunner（GPU 执行）。其核心创新 PagedAttention 将 KV cache 分成固定大小 block（类似 OS 虚拟内存分页），解决传统 KV cache 的显存碎片化和利用率低的问题。

## 核心概念

### 四层架构

```
LLMEngine / AsyncLLM   ← API 入口，接收请求
    ↓
EngineCore             ← 核心循环：schedule → execute → 返回 token
    ↓
Scheduler              ← 决定这一步哪些请求跑、跑多少 token
    ↓
Worker / GPUModelRunner ← 实际在 GPU 上跑 forward
```

关键源码对应：
- [llm_engine.py](../../raw/vllm/vllm/v1/engine/llm_engine.py) — LLMEngine（V0 兼容外壳，实际 alias 到 V1）
- [core.py](../../raw/vllm/vllm/v1/engine/core.py) — EngineCore 核心循环
- [scheduler.py](../../raw/vllm/vllm/v1/core/sched/scheduler.py) — 调度器
- [gpu_model_runner.py](../../raw/vllm/vllm/v1/worker/gpu_model_runner.py) — GPU 执行

整个 V1 核心代码在 `vllm/v1/` 目录下，`vllm/engine/llm_engine.py` 只是一个向后兼容的别名：`LLMEngine = V1LLMEngine`。

### PagedAttention：KV Cache 分页管理

传统做法给每个请求预留一整块连续的 KV cache 显存——即使请求只需要很少 token，显存也被占满。PagedAttention 的解决思路：

1. KV cache 被切成固定大小的 **block**（通常是 16 个 token 一组）
2. **BlockPool**（[block_pool.py](../../raw/vllm/vllm/v1/core/block_pool.py)）管理所有 block 的分配和回收
3. **KVCacheManager**（[kv_cache_manager.py](../../raw/vllm/vllm/v1/core/kv_cache_manager.py)）为每个请求维护一个 **block table**——逻辑 block 到物理 block 的映射
4. 请求不需要连续显存，需要时分配 block，用完释放

这和操作系统的虚拟内存分页是同一思路：程序看到的是连续地址空间（逻辑 block），背后是离散的物理页（物理 block），通过页表（block table）做映射。

$$\text{BlockTable}[req] = [\text{physical\_block}_0, \text{physical\_block}_1, \ldots]$$

好处：零显存碎片、KV cache 利用率从 ~30% 提升到 ~96%、不同请求间共享相同前缀的 block（prefix caching）。

## 直觉 / 类比

把 GPU 显存想象成共享办公空间的工位。传统做法是给每个租客分配一整间私人办公室——即使他只用一个工位，整个房间也不能给别人。PagedAttention 把工位切成最小单位，租客来几个分几个，走了回收给别人。两个租客提交的前半部分一样的报表（prefix），后半部分可以共享已经写好的部分。

## 常见误区

- **误区**："vLLM 的调度是先 prefill 一批请求，等全部 prefill 完再统一 decode。" 实际上 V1 源码注释明确说 "There's no 'decoding phase' nor 'prefill phase'"——每步都是混合调度。
- **误区**："KV cache block 是 1 token 一个。" 实际上 block_size 通常为 16 token，是 batch 上的一个优化粒度。
- **误区**："PagedAttention 只是把 KV cache 按 token 切成小块。" 它不只是切块，关键是引入了 block table 映射层，物理 block 不连续、逻辑 block 连续。
- **误区**："PagedAttention 和 FlashAttention 是竞争关系。" 实际上两者互补——FlashAttention 优化 attention 计算时的 IO 瓶颈（tiling 减少 HBM 访问），PagedAttention 优化 KV cache 的存储和复用（分页消除碎片）。vLLM 内部两套机制同时使用。

## 面试常见问题

- **Q**: PagedAttention 如何优化 KV Cache？它与传统的预分配方式有什么本质不同？
  **A**: 传统方式为每个请求预分配一块最大长度的连续显存——实际生成的 token 数远小于最大值，造成大量内部碎片。PagedAttention 将 KV cache 切成固定大小 block，按需分配、物理不连续、通过 block table 映射。这类似 OS 虚拟内存分页——程序看到连续地址，背后是离散的物理页。收益：显存利用率从约 30% 提升到 96% 以上，消除了碎片化的吞吐瓶颈。

- **Q**: block_size 怎么选？影响什么？
  **A**: block_size 通常在 8-16 之间。大 block 减少 block table 大小和 lookup 开销，但增加内部碎片（最后一个 block 通常不满）；小 block 减少碎片但增加管理开销。16 是 vLLM 的默认值，是碎片率和开销之间的经验平衡点。

- **Q**: PagedAttention 和 FlashAttention 的关系是什么？能同时用吗？
  **A**: 两者解决不同问题、可以协同。FlashAttention 优化 attention 计算时的显存 IO（通过 tiling 减少 HBM 读写），PagedAttention 优化 KV cache 的存储管理（通过分页消除碎片）。vLLM 在 prefill 阶段用 FlashAttention 加速计算，decode 阶段用 PagedAttention 管理 cache，两者不冲突。

## 关联

- [Continuous Batching 与调度器](continuous-batching-scheduler.md) — 调度器如何利用 PagedAttention 的 block 分配机制做混合调度
- 源码：[vLLM 仓库](../../raw/vllm/) — `vllm/v1/core/` 和 `vllm/v1/worker/` 为核心目录
