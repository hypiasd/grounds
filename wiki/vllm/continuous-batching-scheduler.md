---
title: Continuous Batching 与 vLLM 调度器
topic: vllm
tags: [llm-inference, serving, continuous-batching, scheduler, preemption]
summary: vLLM V1 调度器每步用 token_budget 驱动混合调度（running 队列优先 → waiting 队列），无 prefill/decode 阶段之分。抢占采用 recompute 策略（释放所有 block + 进度归零），waiting 队列不参与抢占。FCFS 保护 running 对吞吐公平，但对短请求造成尾部延迟。
created: 2026-07-14
updated: 2026-07-14
sources:
  - ../../raw/vllm/vllm/v1/core/sched/scheduler.py
---

# Continuous Batching 与 vLLM 调度器

## TL;DR

vLLM V1 调度器的核心是 `schedule()` 方法。每步用一笔 `token_budget`（`max_num_scheduled_tokens`）驱动混合调度：先给 running 队列的请求分预算，再有剩余给 waiting 队列的新请求。没有 prefill/decode 阶段之分——prefill 和 decode 请求在同一个调度步里混合跑。当显存不够时，running 请求之间互相抢占，采用 recompute 策略释放所有 KV block。抢占发生后 waiting 队列这一步直接跳过。

## 核心概念

### 调度循环：token budget 驱动

每个请求有两个关键计数器：
- `num_computed_tokens`：已经算完的 token 数
- `num_tokens_with_spec`：总共要算的 token 数（prompt + 已生成 + spec token）

调度的目标就是让 computed 追上 with_spec：

$$\text{num\_new\_tokens} = \text{num\_tokens\_with\_spec} - \text{num\_computed\_tokens}$$

这个值被 `token_budget` 剩余额度 cap 住，再被 `max_model_len` 约束。

### 调度顺序

1. **Running 队列优先**：按队列顺序遍历，每个请求分 `num_new_tokens`，从 budget 扣除。如果某个请求无法调度（`num_new_tokens == 0`），`continue` 跳过——不严格遵循 FCFS
2. **Waiting 队列**：仅当 running 阶段**没有发生抢占**时才处理。新请求需要 `allocate_slots` 分配 KV cache block，同时受 `max_num_running_reqs` 限制

```python
# scheduler.py L420-428 关键注释：
# "There's no 'decoding phase' nor 'prefill phase' in the scheduler."
# "Each request just has the num_computed_tokens and num_tokens_with_spec."
# "At each step, the scheduler tries to assign tokens to the requests
#  so that each request's num_computed_tokens can catch up its
#  num_tokens_with_spec."
```

### 抢占机制：recompute 非 swap

当 `allocate_slots()` 返回 None（显存不足），触发抢占：

- **牺牲品选择**：PRIORITY 策略选优先级最低且到达最晚的；FCFS 策略直接 `pop()` 队列末尾
- **抢占行为**（[scheduler.py:get_preempt_request](../../raw/vllm/vllm/v1/core/sched/scheduler.py)）：释放请求的**所有 KV block**，`num_computed_tokens` 重置为 0，塞回 waiting 队列头部
- **关键后果**：被抢占的请求需要**从头重新 prefill**（recompute），不是把 KV cache swap 到 CPU 内存再恢复
- **Waiting 队列被整体跳过**：`if not preempted_reqs` 条件（L656）保证抢占发生后新请求不进 running

### 公平性边界

FCFS + "running 优先" 在长短请求混合时有一个根本张力：

- **对吞吐公平**：不浪费 token budget 在上下文切换上，最大化 GPU 利用率
- **对等待时间不公平**：一个长 prefill 请求（如 10000 token）每步吃满 budget（如 1024 token），会连续阻塞 waiting 队列中的短请求约 10 步

缓解手段（源码参数）：
- `long_prefill_token_threshold`：限制单个请求每步 prefill 的 token 上限
- `throttle_prefills`：在非 cadence-aligned 步上推迟 prefill，优先保证 decode

## 直觉 / 类比

调度器像一个项目经理，每步手里有一笔固定预算（token_budget）。手头两组人——正在干活的（running）和新来等分配的（waiting）。每步先给干活的人分预算让他们继续，有剩余再从 waiting 招新人。如果有人申请额外资源（显存）时失败，就"牺牲"一个正在干活的人——没收他所有东西让他重新排队——但不会为了等在外面的新人去抢正在干活的人。

## 常见误区

- **误区**："抢占是把请求暂存到 CPU 内存里，等有显存了再恢复。" 实际上 V1 采用 recompute 策略——释放所有 KV block、进度归零、重头 prefill。代价不小（重新计算），但避免了 CPU-GPU 数据搬运的复杂度。
- **误区**："抢占时 scheduler 会主动选最不重要的请求让新请求进来。" 实际上抢占只在 running 内部发生（为其他 running 请求腾空间），waiting 请求不参与抢占——如果这步发生了抢占，waiting 队列整体跳过不处理。
- **误区**："调度是严格 FCFS。" 源码中当某个 running 请求无法调度时（`num_new_tokens == 0`），用的是 `continue` 而不是 `break`——跳过当前请求让后面有机会。这打破了严格的先来先服务。
- **误区**："Continuous Batching 只是 Dynamic Batching 的另一个名字。" Dynamic Batching 在请求级别等待凑够一个 batch 再执行；Continuous Batching 在 token 级别调度——每步动态决定哪些请求跑、跑多少，请求随时可以加入和退出 batch，不等整个 batch 完成。

## 面试常见问题

- **Q**: Continuous Batching 和传统 Static Batching 的本质区别是什么？
  **A**: Static Batching 以请求为粒度——一个 batch 里的请求要全部完成才释放槽位，新请求只能在 batch 结束后加入。LLM 推理中请求长度差异大（短的 10 token，长的 10000 token），Static Batching 会导致 GPU 大部分时间空转等慢请求。Continuous Batching 以 token 为粒度——每一步动态决定每个请求跑多少 token，请求随时可以加入 batch 也可以在完成后立即退出。prefill 和 decode 可以在同一步混合执行。

- **Q**: 调度期间来的新请求会被立即处理吗？什么时候被处理？
  **A**: 不会立即处理。新请求进入 waiting 队列，在 `schedule()` 的 waiting 阶段才被考虑——前提是这一步没有发生抢占（`not preempted_reqs`），且 running 队列未满（`num_running < max_num_running_reqs`），且有 token budget 剩余。如果这一步发生了抢占，waiting 队列整体跳过。

- **Q**: vLLM 调度器的抢占机制是怎么工作的？
  **A**: 当 `allocate_slots()` 无法为当前 running 请求分配 KV cache block 时触发。牺牲品从 `self.running` 队列中选出（FCFS 策略选队列末尾，PRIORITY 策略选优先级最低的），执行 `_preempt_request`：释放所有 block、`num_computed_tokens` 归零、回到 waiting 头部。这是 recompute 策略（重头 prefill），不是 swap。抢占后 waiting 队列整步跳过。

## 关联

- [vLLM V1 架构与 PagedAttention](vllm-v1-architecture.md) — 调度器依赖的 PagedAttention 机制和 KV cache 管理
- 源码：[scheduler.py](../../raw/vllm/vllm/v1/core/sched/scheduler.py) — `schedule()`（L420）和 `_preempt_request` 方法
