---
title: vllm-plus 运行手册（时间线 / 决策 / 踩坑 / 能力账本）
tags: [project, vllm-plus]
created: 2026-07-22
updated: 2026-07-23
publish: true
---

# vllm-plus 运行手册（Runbook）

> 单一主线记录：按时间线串起「决策 / 实施 / 问题 / 解决 / 结果」。
> 深表（每次实验的原始测量数字）在代码仓 `project/vllm-plus/experiment_results.md`，本文件只内联**关键结论、决策与可复用认知**（SSOT 不重复造数）。
> 工作目录锁死：`project/vllm-plus/`（软链到真实仓库，独立 git）。

---

## 节点 0：基线搭建 + 小模型投机解码（实验 1–6）

- **状态**：✅ 完成（2026-06-24）
- **实施**：在 nano-vllm 上实现 Draft-Target 双模型投机解码（Qwen3-0.6B draft / Qwen3-4B target），CUDA graph replay + GPU 向量化比较 + 单次 CPU sync。
- **结果**（核心数据，深表见 repo）：
  - 实验1 K 消融：最优 **K=8 → 562.77 tok/s（2.15x）**；K=16 因接受率跌到 27.8% 反降至 1.97x。接受率随 K 递减（61%→28%）。
  - 实验2 延迟：TPOT 356→114ms（**-68%**），是吞吐提升核心；但 spec 的 TTFT 异常高（疑似 free block 不足触发频繁 preemption，标记为待复核）。
  - 实验3 batch：小 batch 收益最大（BS=1 → 2.07x），大 batch 收窄（BS=16 → 1.50x）；**BS≥64 因 draft KV 预分配过大 OOM**。
  - 实验4 真实 prompt：接受率 42%~66%（创意写作最差、翻译最好）；K=8 接受率全面降 13–21pp 但加速比全面升（数学 3.50x）。
  - 实验5 显存：+1.13GB（draft 权重 ~1.2GB），可控。
  - 实验6 profiling：**Target Verify 占 spec step 86.1%（59ms）**，是绝对瓶颈；Draft Forward 仅 13.9%（CUDA graph 已压到 ~10ms）。
- **学到了什么**：
  - 投机解码收益来自「每步产出更多 token 摊薄 target verify 成本」，与 batch 饱和度强相关。
  - 瓶颈是 target verify（大模型 forward），无法避免；优化方向只能「提接受率」或「降 verify 成本」。

---

## 节点 1：training-free 投机解码（Lookahead / 动态树 / 自适应 K）— 实验 7

- **状态**：⚠️ 部分完成（代码已实现，GPU 实测 0.02x 失败，2026-07-09）
- **决策**（非平凡选型）：要不要做「无草稿模型」方案？
  - 方案 A 小模型 draft（原）：+1.13GB 显存代价、接受率上限受 draft 能力限制。
  - 方案 B Lookahead/Jacobi + 动态树：零额外显存、复用 target 自身、解锁 chat。
  - **推荐**：B（training-free 更优雅），但实测证伪（见下）。
- **问题 / 解决**：
  - **现象**：lookahead 实测 **8 tok/s，比 plain 慢 50 倍（0.02x）**。
  - **根因**：为做到 temp=0 下逐 token 比特无损，验证用 `seqlen_q=1` 逐 token 前向，其前向次数与普通解码完全相同 → 无法获得多 token 批验证的加速。
  - **关键发现（数值特性）**：`flash_attn_with_kvcache` 对 **batch size 和 seqlen_q 都数值敏感**（bs=1 vs bs=2 差 ~0.5，seqlen_q=1 vs 2 差 ~0.4），但**固定 bs 下 per-seq 独立（diff=0）**。
  - **学到了什么**：「逐 token 比特精确无损」与「多 token 验证加速」**不可兼得**——加速来自 `seqlen_q>1` 的批前向，而它正是数值漂移源。bs=16 仍有残差发散（第 62 token 处）。
  - **状态**：作为正确但不可用的参考实现保留；根因在节点 3（ngram）被转化利用。

---

## 节点 2：Lookahead 无损性修复 — 实验 4（命名）

- **状态**：✅ 完成（2026-07-09，13 项检查全过）
- **实施**：`_verify_tree` 重写为「批量逐 token 多轮验证」（`bs=N, seqlen_q=1` 完全 match 普通贪心解码的每次前向），`_allocate_block` 清零 KV 区，`run_lookahead_spec_decode` 按 `max_tokens` 截断提交，`_draft_prefill_logits` 设 `is_spec_decode=True`。
- **结果**：temp=0 下与普通解码**逐 token 一致**（lossless），13/13 检查通过；但吞吐仍 0.02x（机理同节点 1）。

---

## 节点 3：纯 ngram / Prompt Lookup 投机解码 + 验证批 CUDA Graph — 实验 9

- **状态**：✅ 完成（2026-07-11）
- **决策**：lookahead 失败的根因是「逐 token 验证」，怎么绕开？
  - **推荐 + 理由**：ngram 改用**固定 `seqlen_q=K+1` 批验证**（复用 vLLM 的 uniform_decode spec 图），从根本上避开逐 token 瓶颈。
- **实施**：`capture_spec_cudagraph()` 捕获 `(bs, K+1)` 验证批图（`is_spec_decode=True`），`run_spec_verify_model()` 优先 replay 否则 eager；ngram 移除此前强制的 `enforce_eager`。
- **结果**（深表见 repo）：
  - 重复文本：**ngram-graph 3513 tok/s（1.48x baseline / 2.0x eager）**，零额外显存。
  - 随机文本：接受率 67%，不快于 baseline（Prompt Lookup 固有待复复模式的取舍）。
- **学到了什么**：
  - **从 0.02x 到 1.48~2.0x**：复用「固定 `seqlen_q=K+1` 批验证」路径是把 training-free 投机解码从不可用变可用的关键。
  - 图路径数值等价于 eager 验证（同 batch 同 seqlen_q），主要加速来自消除 Python/kernel-launch 开销。
  - 代价：验证批 shape 与 decode（`seqlen_q=1`）浮点路径不同，近平局处输出可能差 1 token（nano-vllm 既有跨 shape 数值非确定性，非回归）。

---

## 节点 4：KV Cache Swap 抢占机制 — 实验 8

- **状态**：✅ 完成（正确实现，但吞吐反劣，2026-07-11）
- **实施**：`swap_space`（GiB，默认 4.0）启用时把 GPU KV 拷到 CPU pinned 内存（swap-out/in），替代默认 recompute；修复 3 个既有 bug（前缀缓存关闭时挂起 / may_append 误分配 / 前缀 hash 未清理）。
- **结果**：swap **bit-identical** 且与 recompute 输出等价（15/16 条完全一致，偏差源于跨 batch 数值非确定性，非 swap 缺陷）；但**吞吐反而低于 recompute**（严重超卖场景 260 vs 362 tok/s，慢 ~28%）。
- **问题 / 解决**：
  - **根因**：`schedule()` 每步无条件尝试 swap-in，被换出序列下一步又被换回、又分不到块被换出，swap 反复横跳却无法结束任何序列（调度抖动）+ PCIe 拷贝反噬。
  - **学到了什么**：与上游 **vLLM V1 已移除 swap** 的方向一致——recompute（chunked prefill 摊薄重算）在 V1 架构下开销更低。swap 作为可选特性（`swap_space>0`）保留，但**推荐默认 recompute**。

---

## 节点 5：调度器 Watermark（KV 准入余量）— 实验 10

- **状态**：✅ 完成（2026-07-11）
- **决策**（关键澄清，本课核心）：watermark 的本职是「防止抢占抖动」还是「避免 OOM」？
  - **结论**：本实现是**固定 KV 池（不会 OOM）**，watermark 在此**只**体现为防抖动；vLLM 留它是因它还防 OOM（动态池）。二者不冲突。
- **实施**：余量**仅**挂在 `can_allocate`（对齐 vLLM `can_append_slots` 不带 watermark），`can_append`/`can_append_n` 改回只判 `>=0`；新增每序列抢占计数与抖动指标（`repreempt` / `max_seq_pre`）。
- **结果**（持续到达 + 钉死 KV 池，深表见 repo）：
  - 中等压力档 wm>0 把抢占 **18→0**；长输出饱和档把空转抢占 **-86%（29→4）**、最坏单序列被抢占 5→2，吞吐至多降 ~4%。
  - 无压力时 watermark 是 no-op（三种 wm 行为一致）。
- **问题 / 解决**：
  - **初版 bug**：把 watermark 也加到 `can_append`/`can_append_n` → decode 过早抢占、纯增代价、掩盖真实收益。对齐 vLLM 后收益才显现。
  - **取整归零陷阱**：`watermark_blocks = int(watermark * num_blocks)` 在钉死小池下归零（KV=48 时 wm=0.01/0.02 都算 0 块）；修复为 `wm>0` 下限置 1。默认 0.01 在大型自动分配池下 ≈ 数十~上百块，是近乎零成本优质默认值。
- **学到了什么**：实现前先想清「这个特性的本职收益是什么、在什么架构假设下成立」，否则会在错误的基准上测出相反结论。

---

## 节点 6：INT8 KV Cache 量化（融合反量化注意力）— 实验 11

- **状态**：✅ 完成（正确实现，真实 +4%~+13%，2026-07-12）
- **决策**：Ada（sm89）无 FP8，KV 量化唯一可行路径是 INT8。
- **实施**：per-token-per-head absmax/127 量化 + **融合反量化注意力 kernel**（寄存器内 int8×scale→fp32，不落 bf16 temp）→ KV 显存/带宽减半 → 2× KV 块数。
- **问题 / 解决**：
  - 迭代1 打通端到端：修 3 个阻塞 bug（`Attention.__init__` 缩进错误 / `o_buffer` 图安全泄漏 / 前缀 prefill bf16 temp 12GiB OOM → 改单层共享缓冲）。
  - 迭代2 kernel 优化：首版 fused kernel **逐 token 串行**从 HBM 加载 → 比 flash_attn bf16 慢 1.5–2×；重写为**分块（BLOCK=64）向量化** + online-softmax 后 int8 **全面反超 bf16**（+4%~+13%）。
- **结果**：数值对齐 flash_attn（max err 0.0078，cosine 0.99985）；容量墙场景 +19%、抢占 177→69（2× 容量真实生效）。
- **学到了什么（关键甄别）**：decode 瓶颈是 **4B 未量化 bf16 权重 matmul（HBM 带宽受限）**，KV 已被 GQA 削小；INT8 KV 只减半「很小的一块」+ 给 2× 容量，**不动吞吐天花板**，只换来容量更宽、尾延迟更稳。抢占只影响尾延迟/排队，不决定吞吐天花板。

---

## 节点 7：权重量化（W8A8 / INT8 权重）— 实验 12

- **状态**：✅ 完成（**假设被推翻**：本卡上无法提升吞吐，2026-07-12）
- **决策**：实验11 假设「W8A8→2×」是真正吞吐杠杆（减半占主体的 4B 权重读取）。本轮验证。
- **实施**：`quantize_weight` 逐输出通道对称 INT8 量化 + Triton `int8_gemm`；修 2 个内核 bug（反量化 scale 应用两次 / 步长用错 inner stride）；lm_head/embed 保持 bf16；数值正确（cosine 0.99995，首 token top1 全一致）。
- **结果**（**假设被推翻**）：
  | GEMM 路径 (decode 形状 M=64) | 耗时 | 备注 |
  |---|---|---|
  | cuBLAS bf16 `F.linear` | **40.4µs** | 最快（带宽受限天花板） |
  | weight-only int8 + 寄存器反量化 + bf16 MMA | 48~52µs | 慢 1.2~1.3× |
  | W8A8 真·INT8 张量核 (Triton) | 55.6µs | 慢 1.4× |
  | `torch._int_mm` (cuBLAS int8) | 464.6µs | 慢 11.5×，不可用 |
  - 端到端：`WQUANT=int8` **601 tok/s** vs bf16 **812 tok/s** → 慢 **1.35×**。
- **问题 / 解决**：
  - **根因**：cuBLAS bf16 已把权重读到接近峰值带宽；手写 Triton int8 内核带宽效率更低（48~56 vs 40µs），2× 省下的字节被内核低效吃光；INT8 张量核算力优势在带宽受限下无意义。
- **学到了什么**：在 Ada（无 FP8）+ 现有可用 GEMM 内核下，**权重量化无法提升 decode 吞吐**。真 2× 杠杆需 FP8（Hopper/Blackwell）或 CUTLASS 级 INT8 GEMM。**INT8 KV（实验11）是量化唯一吞吐收益**；W8A8 作为正确但偏慢的参考实现保留。

---

## 节点 8：整体结论与下一步（2026-07-22 复盘）

- **状态**：✅ 完成（阶段总结）
- **结果**（全局认知）：
  - 投机解码是**唯一稳定 2×+** 的吞吐杠杆（实验1 K=8 → 2.15x；实验9 ngram 重复文本 1.48~2.0x）。
  - 量化路线在本卡（Ada 无 FP8）吞吐收益封顶于 **INT8 KV 的 +4~13%**（容量/尾延迟改善），W8A8 反劣。
  - swap 正确但吞吐反劣（vLLM V1 已弃）；watermark 是零成本防抖动好默认；lookahead 无损验证正确但 0.02x 不可用。
- **需拍板点（下一步方向）**：
  - (a) 接受现状：量化封顶于 INT8 KV，转向吞吐的其他杠杆（kernel 融合 / 更优 batching / scheduler）。
  - (b) 若有 Hopper/Blackwell（FP8）卡，重做 W8A8→FP8 权重，预期真 2×。
  - (c) 把 12 项实验沉淀为简历数据 + 面经（代码仓已有 `interview_questions/answers.md`）。

---

## 节点 9：方向再评估 — INT4 权重量化（Marlin）作为剩余最高天花板杠杆（2026-07-22）

- **状态**：🔍 评估中（基于节点 7 exp12 失败的再思考，待拍板）
- **动机**：节点 7 结论写的是「W8A8 失败，真 2× 需 FP8 或 CUTLASS 级 INT8 GEMM」。但重新审视发现：**INT4（Marlin, W4A16）是比 W8A8 更优的权重量化路径**——它省 4× 字节（vs W8 的 2×）+ 用生产级内核，字节红利足以覆盖内核税。完整推导见 wiki：[权重量化内核效率](../../wiki/cuda/weight-quantization-kernel-efficiency.md)。
- **关键论证（修正节点 7 的归因）**：
  - 节点 7 实测：W8A16（int8 权重 + **寄存器反量化**，一次访存）48~52µs，W8A8（真·INT8 张量核）55.6µs，均慢于 cuBLAS bf16 40.4µs。
  - **修正**：exp12 失败根因**不是**「读两次」（已寄存器反量化），而是**手写 Triton 内核税 > 2× 字节红利**。「只读一次」不足以提速（项目实测证伪）。
  - 推论：W8 省 2× 不够覆盖内核税；**INT4 省 4× + Marlin 生产级内核**（逼近峰值 HBM 带宽）才可能净赚 ~2.5~3×。
  - Marlin = **W4A16（weight-only）**，非 W4A4：仅压权重、激活保 fp16，绕开纯整数路径的 fp16 scale 难题。
- **与现有优化正交可叠加**：INT4 权重 target + 现有 spec（2.15x，verify forward 也更快）+ INT8 KV（+13% 容量）三者组合上限最高。
- **两个边界**：① 只救 decode，不救 prefill（prefill 算力受限、权重每位置只读一次已摊薄）；② INT4 有质量风险（Qwen3-4B 上 AWQ/GPTQ 通常掉点小，须验 perplexity / 首 token 对齐）。
- **决策 / 下一步（待拍板）**：
  - 方案 A（推荐）：**Marlin INT4**（autoawq/auto-gptq 量化 → `LinearBase` 接 Marlin GEMM，lm_head/embed 保 bf16）→ 端到端验数值对齐 + 吞吐实测。
  - 方案 B：CUTLASS INT8（仍是 2× 字节，优于手写，但上限低于 INT4）。
  - 若 INT4 掉点不可接受，退回方案 B。
- **执行进展（2026-07-22）— α 手写 INT8 Triton GEMM 已落地**：用户选择先用手写 Triton 翻案（目标击败 cuBLAS bf16 40µs），不立刻上 Marlin。已落地：
  - `nanovllm/layers/quant_linear.py`：W8A16 INT8 Triton GEMM。**关键修正 exp12 两个 bug**——① scale 仅在累加后乘一次（exp12 是 scale²）；② `W.T` 用指针 strides 转置加载（`w_ptrs = w[n*wn + k*wk]`），无中间转置张量、无内外 stride 错配；③ 权重仅以 int8 读一次，反量化融进 MMA pipeline 不落 HBM。
  - **二次迭代（split-K + num_stages）**：「是否优化到极致」追问下发现初版仍非极致——缺 **split-K** 与 `num_stages` 调优。**根因洞察**：decode 时 M 极小（1~512），朴素 GEMM 只产生 ~86 个 CTA（M 维 1 block × N 维 86 block），128 SM 填不满、每 SM <3 warp，**藏不住 HBM 延迟 → 延迟受限而非带宽受限**，这几乎正是 exp12 卡在 48~52µs（~540GB/s，峰值 40%）的原因。修复：拆**双路径**——大 M（prefill）单核（scale 内核乘、存 bf16）；小 M（decode）**split-K 内核**（沿 K 切 8/4/2 段造更多 CTA，fp32 workspace 存部分和，torch `sum(0)*scale` 归约、scale 只乘一次）。autotune 补 `num_stages=3~4`。K 划分已 CPU 模拟验证「不重不漏」。
  - `linear.py`：`LinearBase` 加 `quantize()` + 各 `forward` 按 `use_int8` 派发；`int8_gemm_nd` 支持任意前导维。
  - `config.py` 加 `weight_quant`（`none`/`int8`）；`model_runner.py` 读 `WQUANT` 并在 `load_model` 后量化所有 `LinearBase`（lm_head/embed 非 `LinearBase` 保持 bf16）。
  - 新增 `bench_int8_gemm.py` 独立微基准（比对 cuBLAS bf16 40µs + 数值对齐）。
  - **待 4090D 验证**：`python bench_int8_gemm.py`（看 M=1/16/64/256/512 是否 < 40µs、cos≈1）与 `WQUANT=int8 python bench.py`（端到端 > 812 tok/s）。结果将决定节点 9 结论：若 α 胜 → 修正「W8 不够」为「W8 手写可赢」、Marlin 优先级下调；若 α 仍 ~48µs → 强化「W8 封顶、必须 INT4」。

---

## 节点 10：远程同步 α 实现到本地（2026-07-22）

- **状态**：✅ 完成（同步，非新决策）
- **实施**：`git pull --rebase origin main`（fast-forward `b963fc8..7cdea69`），本地工作树此前干净，无冲突。
- **结果**：远程提交 `7cdea69 alpha: W8A16 INT8 Triton GEMM with split-K` 已落到本地，含 `bench_int8_gemm.py`（新增）、`nanovllm/layers/quant_linear.py`（新增）、`config.py` / `model_runner.py` / `linear.py`（改）。即节点 9 的 α 手写 INT8 Triton GEMM 现已在本地工作树。
- **下一步（待拍板）**：在 4090D 上跑验证（命令见节点 9 末尾），据实测决定「W8 手写可赢」还是「仍须 INT4(Marlin)」。

---

## 节点 11：α 验证结果 — W8A16 INT8 Triton GEMM 微基准（2026-07-22，4090D 实测）

- **状态**：⚠️ α 假设被推翻（实测失败）
- **假设（来自节点 9）**：手写 split-K INT8 Triton GEMM 能在 decode 形状（M=64）跑进 40µs，击败 cuBLAS bf16，从而把「W8 不够」修正为「W8 手写可赢」。
- **方法**：`python bench_int8_gemm.py`（自包含随机张量，K=2560 / N=11008，对应 Qwen3-4B），比较 `int8_gemm` vs `F.linear`(bf16)，算 cos(ref) 与 µs。
- **度量**：latency(µs) 越低越好；cos(ref) 越接近 1 越正确。
- **结果**：

  | M | cos(ref) | int8 µs | bf16 µs | speedup | int8 BW(GB/s) |
  |---|---|---|---|---|---|
  | 1 | 0.35265 | 142.43 | 61.61 | 0.43x | 198.0 |
  | 16 | 0.35604 | 142.08 | 31.97 | 0.23x | 201.4 |
  | 64 | 0.61594 | 170.99 | 38.02 | 0.22x | 175.0 |
  | 256 | 1.00000 | 190.52 | 110.82 | 0.58x | 184.4 |
  | 512 | 1.00000 | 287.45 | 207.30 | 0.72x | 146.4 |

- **结论**：
  - **性能**：decode 形状（M=64）int8 = **171µs vs bf16 38µs → 0.22x（慢 4.5×）**，与「< 40µs」目标相反；比 exp12 的 48~52µs 还慢。手写 Triton 内核税 > 2× 字节红利，假设不成立。
  - **正确性（关键 bug）**：decode 形状 **cos 仅 0.35~0.62**（M=1/16/64），输出基本错误；只有 M≥256（prefill 单核路径）cos=1.0。**即 split-K（decode）路径数值损坏**，单核（prefill）路径正确。
  - **带宽**：~146~201 GB/s，仅 ~15~20% 峰值（4090 ~1008 GB/s），CTA 仍未填满 / 内核低效。
- **对节点 9 决策的影响**：α 失败 → 维持「W8 手写不可赢」结论，**Marlin INT4 优先级不变（仍是剩余最高天花板杠杆）**。split-K 的正确性 bug 即便修掉，大 M 路径仍 0.58~0.72x 慢于 cuBLAS bf16（与 exp12 一致：Triton 税吃光字节红利），故翻案不成立。
- **端到端未跑（非模型缺失）**：`WQUANT=int8 python bench.py` 的模型 `~/huggingface/Qwen3-4B/` **本地已存在**（仅 HF hub 网络不可达，但本地路径可读，不阻塞）。真正不跑的原因：(1) split-K decode 路径数值损坏（cos 0.35~0.62），端到端会吐错误 token，吞吐数字无意义；(2) 即便正确，decode GEMM 已实测 4.5× 慢于 bf16，不可能超过 812 tok/s。微基准已足以推翻 α，端到端交叉验证价值低。
- **关联**：节点 9（α 设计）、节点 7 / exp12（W8A8 失败）、wiki 权重量化内核效率。

---

## 节点 12：α 根因定位 + 修复 — Triton 分组调度漏钳位（2026-07-22）

- **状态**：✅ 完成（正确性 bug 修复并重验；α 性能仍失败，结论封口）
- **问题 / 解决**：
  - **现象**：节点 11 实测 decode 形状 cos 仅 0.35~0.62，初判为 split-K 路径数值损坏。
  - **根因**：非 split-K 专属——两个 kernel（`_int8_gemm_kernel` / `_int8_gemm_splitk_kernel`）的 **grouped pid swizzle 漏钳位**：`pid_m = first_pid_m + (pid % GROUP_M)` 未做 `min(num_pid_m - first_pid_m, GROUP_M)` 钳位。当 `num_pid_m < GROUP_M`（`M < BLOCK_M*GROUP_M = 128`，即整个 decode 区间）时 `pid_m/pid_n` 错算，部分输出 tile 被重复算、部分永远不算；输出 `torch.empty` 未初始化 → 未算区域是垃圾。佐证：强制单核跑小 M cos 掉到 0.0065（比 split-K 更糟）；M≥128（num_pid_m≥8=GROUP_M）天然不触发 → 「单核正确」是假象，bug 一直潜伏。
  - **解法**：两 kernel 分组调度改为 Triton tutorial 标准钳位写法：`group_size_m = tl.minimum(num_pid_m - first_pid_m, GROUP_M); pid_m = first_pid_m + ((pid % num_pid_in_group) % group_size_m); pid_n = (pid % num_pid_in_group) // group_size_m`。
  - **防复发**：手写 Triton grouped swizzle 必须钳位 `group_size_m`；正确性验收必须覆盖**最小 M（1/16/64）**，不能只看大 M。
  - **学到了什么**：decode 形状 bug 易被「大 M 正确」掩盖；grouped swizzle 是性能优化，但漏钳位会变成静默错误 tile——正确性优先于 swizzle 收益。
- **重验结果（修复后 `bench_int8_gemm.py`，cos 全 1.0）**：

  | M | cos | int8 µs | bf16 µs | speedup |
  |---|---|---|---|---|
  | 1 | 1.00000 | 140.76 | 61.48 | 0.44x |
  | 16 | 1.00000 | 142.07 | 30.01 | 0.21x |
  | 64 | 1.00000 | 140.83 | 38.00 | 0.27x |
  | 256 | 1.00000 | 192.07 | 110.78 | 0.58x |
  | 512 | 1.00000 | 288.24 | 208.06 | 0.72x |

- **结论**：正确性修复后 int8 仍全段慢于 cuBLAS bf16（decode M=64 慢 3.7×、prefill 慢 1.4~1.7×），**α 假设在「实现正确」前提下仍被证伪**——与 exp12 一致：Ada 上手写 Triton 内核税 > 2× 字节红利，**W8 手写不可赢，维持节点 9「须 INT4(Marlin)」结论**。
- **带宽**：仍 ~146~212 GB/s（~15~20% 峰值 ~1008）。split-K 虽补 CTA 数，但 torch 端 `ws.sum(dim=0)*scale` 引入额外 `(split_k,M,N)` fp32 读写 + 多次 kernel launch，小 M 时这部分开销占主导，反成新瓶颈。
- **关联**：节点 9（α 设计）、节点 11（初测）、`nanovllm/layers/quant_linear.py`。

---

## 节点 13：深挖「为什么慢 3.7×」— 分解与三个猜想证伪（2026-07-22）

- **状态**：✅ 完成（机理定位；结论：自身 bug 占大头，但 Triton 上限仍低于 cuBLAS bf16）
- **动机**：节点 12 重验后 int8 仍比 bf16 慢 3.7×（141 vs 38µs @M=64），质疑「没道理慢这么多」。
- **方法**：分路径 + 分组件 + 扫 block 配置实测（临时脚本，已清理）。
- **结果**：
  1. **split-K 是自找的净亏损**：强制单核 M=64 仅 84µs vs split-K 141µs。拆分：split-K kernel 68µs + torch 归约 38µs + workspace 分配/包装 ~35µs。「补 CTA」收益（68 vs 84，省 16µs）远抵不上归约 + workspace（~73µs）。且「小 M CTA 少」前提对 M=64 不成立（BLOCK_M=16 → 4×86=344 CTA，足够填 128 SM），仅 M≤16 才成立。
  2. **预转置 (K,N) 合并加载：无用（猜想证伪）**——coalesced kernel 与单核数字几乎一致（M=64 均 ~84µs）。瓶颈不是转置加载。
  3. **block 扫描（单核，BK=64）**：M=64 最优 BM=64 → **58µs**（vs repo 自调 84µs），仍慢于 bf16 40µs（1.45×）。机理张力：小 BM 并行度高但权重被 `num_pid_m` 重读（BM=16@M=64 → 读 4×=113MB，跑 1.8TB/s 贴 L2）；大 BM 一次读完（28MB）但并行度 / 延迟隐藏差（仅 486GB/s）。最优落在 58µs，两头不占优；且 int8→fp16 反量化 compute 吃掉部分字节红利。
  4. **重要基准陷阱**：微基准权重（int8 28MB / bf16 56MB）均 < 72MB L2，跨迭代驻留 L2 → 偏袒 bf16（搬 2× 字节但走快 L2）。真实 decode 模型全权重 ~8GB ≫ L2，走 HBM；HBM 下 int8 字节减半理论上 ~2× 占优。但 exp12 真实端到端（即便旧 bug kernel）`WQUANT=int8` 仍 601 < 812 tok/s，实际红利未兑现。
- **结论**：「慢 3.7×」里 **~2.4× 是自身可修问题**（split-K + 次优 block，141→58µs），但 **Triton W8A16 上限仍 ~1.45× 慢于 cuBLAS bf16**（58 vs 40µs @M=64）。cuBLAS 胜在 cp.async 软件流水 / 寄存器分块，Triton 朴素 loop 难企及。**战略结论不变：须 INT4(Marlin) 用生产级内核**。可选：把 repo kernel 修到 ~58µs（drop split-K + 补 BM=64 配置）作干净参考实现。
- **学到了什么**：手写 kernel 的「慢」要先分「自身 bug（可修）」与「架构上限（不可修）」；微基准的 L2 驻留会扭曲 decode 真实（HBM-bound）结论，端到端才是最终裁判。
- **关联**：节点 12（正确性修复）、节点 9 / 11、节点 7 / exp12。

---

## 节点 14：α 端到端实测 — int8 W8A16 仍慢于 bf16（2026-07-22，4090D 真实模型）

- **状态**：✅ 完成（端到端裁判落地；战略结论最终封口）
- **实施**：
  - 修 2 个 α 提交自带 bug：`model_runner.py` 缺 `import os`（WQUANT 读取 NameError）；`linear.py` `nn.Parameter(int8)` 默认 `requires_grad=True` 报错（int8 不能 require grad）→ 改 `requires_grad=False`。
  - kernel 优化落地：禁用 split-K（`_pick_split_k` 恒 `return 1`）+ 单核 autotune 改 BK=64 为主。微基准 M=64 从 141→83µs（未到手动扫描的 58µs，autotune 未选中最优 config）。
  - 端到端（NUM_SEQS=128，离线本地 Qwen3-4B）：`python bench.py`（bf16）vs `WQUANT=int8 python bench.py`。
- **结果**：

  | 配置 | 吞吐 | 备注 |
  |---|---|---|
  | bf16 baseline | **2187.30 tok/s** | preemptions=29，wm_blocks=3/337 |
  | int8 W8A16 | **1389.03 tok/s** | **0.63×（慢 37%）**；preemptions=0，wm_blocks=3/399（权重省显存 → KV 块更多） |

- **结论**：**端到端 int8 仍慢于 bf16（0.63×）**，与微基准、exp12 三方一致。机理：
  - int8 kernel 仅 ~340 GB/s（M=64 微基准），cuBLAS bf16 ~1484 GB/s（L2 有效）→ 效率差 4.4×；字节省 2× 抵不过效率差 → 净慢 ~2×。
  - 大 batch（M~128）decode 偏 compute/launch-bound，权重字节红利被摊薄，int8 的反量化 compute + 慢 kernel 直接体现为净慢。
  - **要赢需 int8 kernel ≥ ~750 GB/s**（≈ cuBLAS 一半效率，因字节减半），当前 340 GB/s 差 2.2×。
- **对手写 Triton 路线的诚实评估**：W8A16（2× 字节）已被微基准 + 端到端 + exp12 **三重证伪为「性能不可行」**。若目标是**学 kernel 工程**，追平 cuBLAS（340→750 GB/s：cp.async / 软件流水 / 向量化加载）是极佳练习；若目标是**实际推理提速**，答案是 INT4(Marlin) 生产内核或 FP8（Hopper/Blackwell）。
- **关联**：节点 12 / 13（正确性 + 慢速分解）、节点 9 / 11、节点 7 / exp12。

---

## 节点 15：路径 A 学习序列规划（从 0 打 kernel 地基，2026-07-22 规划）

- **状态**：🔍 规划中（白盒教学，未上 GPU 机执行）
- **动机**：节点 14 战略封口「须 INT4(Marlin) 或 FP8」；但路径 A（手写 int8 kernel 从 340 → ~750 GB/s）作为 **kernel 工程练习**仍极具学习价值，且学习序列与机器无关（数字随 GPU 变，方法不变）。当前 macOS 无 GPU，Triton+CUDA 的 M1 暂跑不了，故在 M1 前插入 **M0（纯 Python/NumPy 分块 GEMM，CPU 可跑）** 先打地基，建立「kernel 在算什么 / 数据怎么搬」的心智模型，再平移到 Triton。
- **概念地基（已讲，带宽游戏）**：
  - **算术强度 AI = 2·M / elem_bytes**（当权重 B 主导，decode 形状成立）。M=64、bf16(elem=2) → AI=64；int8(elem=1) → AI=128。
  - **Roofline 判据**：4090D 算力天花板 ~165 TFLOP/s、HBM 带宽 ~1008 GB/s → 算力受限阈值 AI\* ≈ 164 FLOP/byte。AI=64/128 均 < 164 → **decode GEMM 是带宽游戏，不是算力游戏**。
  - **推论（关键边界）**：AI 随 M 增大；仅当 M > ~164(bf16)/~82(int8) 才转算力受限。即 **prefill（大 M）算力受限 → 量化权重字节已摊薄、救不了；decode（小 M）带宽受限 → 量化（减半字节）是杠杆**。这正是节点 9「只救 decode 不救 prefill」的机理根。
  - **「赢」的判据**：时间 ∝ 字节/BW。int8 字节=½·bf16，故 int8 要快需 `BW_int8 > ½·BW_bf16`。cuBLAS bf16 近峰值 BW(~1008)；当前手写 int8 仅 340 < 504 → 输。目标 **~750 GB/s（>504）** 即翻盘。
  - **微基准陷阱（节点 13 复盘）**：小权重 < 72MB L2 会驻留 L2，偏袒 bf16 显快；真实 decode 全权重 ~8GB 走 HBM。**终验务必用 HBM 公平口径（大权重 / 强制 HBM），端到端才是最终裁判。**
- **里程碑（先懂 → 再对 → 再快；M0 在 Mac 可跑，M1–M4 需 GPU 机）**：
  - **M0 基础（macOS GPU-free，先于 M1）**：纯 Python/NumPy 实现「分块 GEMM」，结构**镜像 Triton matmul tile**——(1) 把 C 切成 `BLOCK_M × BLOCK_N` 的块网格，每个块由一个「程序」负责；(2) 该块沿 K 维分 `BLOCK_K` 小块，循环累加 `A_tile · B_tile` 进局部累加器；(3) 写回 C 块。CPU 可跑、对拍 `np.dot` 验证数值一致。配合精读 Triton 官方 matmul 教程，把 `program_id`↔块网格索引、`tl.load`↔块读取、`tl.dot`↔K 循环、`tl.store`↔写回 一一映射。目标：无 GPU 也建立「kernel 到底在算什么 / 数据怎么搬」的准确心智模型。
    - **实施（2026-07-22，Mac CPU 跑通）**：已建 `gemm_foundations.py`（naive + tiled + 对拍 + 块网格演示 + Triton 映射表）。`python3 gemm_foundations.py`：对拍 max abs err=9.5e-5 PASS、末块非对齐边界 PASS；块网格表显示 BLOCK 16→256 时输出块数 65536→256、K 循环 256→16。文件在代码仓 `project/vllm-plus/`（不进 grounds）。
    - **学到了什么**：分块 GEMM =「输出块网格 × 每块的 K 循环累加」，与 Triton kernel body 同构；`BLOCK_M/N/K` 同时决定并行度（块数）与每程序工作量（K 循环），是 M3 autotune 的核心旋钮。
    - **概念地基已迁出 wiki（通用知识，跨项目复用）**：M0 的 8 条核心洞察（为什么能分块 / 写回用 `=` / 怎么切 A·B / 数据复用 / HBM 流量 / 流量公式推导 / 取1次 vs 用多次 / 两级抽屉模型，含三张分块示意图）已从本项目 runbook 迁出，归入通用笔记：
      - [分块 GEMM 的原理与切法](../../wiki/gemm/tiled-gemm.md) — 两个可加性→可分块算对；A/B 各切两维、A_tile/B_tile 沿同一 K 段对齐；写回用 `=` 的语义根；输出块网格 / 单块数据流 / K 维累加三图。
      - [HBM 流量与数据复用](../../wiki/gpu/hbm-traffic.md) — 复用=取1次用多次；HBM 流量=从显存搬到计算的字节数（时间≈流量/带宽）；两级抽屉模型（寄存器装 tile、L2 装行/列块，decode B≈56MB<L2 72MB 容量可行）；流量 2·M·N·K→理想 M·K+K·N。
      > 原则：通用概念进 wiki 复用，runbook 只留项目专属的「里程碑 + 交付物 + 下一步」。
    - **用户理解达成（2026-07-22，M0 收口）**：经 7 轮追问（为什么能分块→写回为何=→怎么切→复用→HBM流量→取1次vs用多次→装得下才能取1次）用户完整建立 decode GEMM 心智模型（详细逻辑链见 [分块 GEMM 的原理与切法](../../wiki/gemm/tiled-gemm.md) 与 [HBM 流量与数据复用](../../wiki/gpu/hbm-traffic.md)）。下一步:上GPU机后M1把 tiled_gemm 翻译为 Triton bf16 matmul(先 cos=1.0),再 M2-M4 爬带宽。
  - **M1 第一个 Triton GEMM（先跑对，不追快）**：从 Triton 官方 matmul 教程起步，学 `program_id` / `tl.load` / `tl.dot` / `tl.store` / BLOCK 分块 / fp32 累加；纯 bf16 通用 matmul；验收 cos(ref)=1.0（大小 M 都验）。**不直接碰 int8**。
  - **M2 复现并定位 340 GB/s 瓶颈**：在我们的 int8 kernel 上跑微基准，逐项定位——naive K-loop 无流水、无向量化 128-bit 加载、反量化打断融合；建立「每次只改一处、测一处」的实验纪律（对应 M2 实验卡）。
  - **M3 带宽优化爬坡（一处一测）**：向量化加载(128-bit/16B) → K 循环软件流水/双缓冲(`tl.async_copy` 或 block ptr 流水) → 输出分块 + 累加器寄存器分块 → autotune 扫 BLOCK/num_stages/num_warps；目标 340 → 750 GB/s。
  - **M4 int8 专属 + 终验**：重引 int8 + 融合反量化，确认 M=64 `cos=1.0` 且微基准 < 38µs；端到端 `WQUANT=int8 python bench.py` > bf16 2187 tok/s（HBM 公平基准）。
- **需拍板点（上 GPU 机前确认）**：
  1. 起步选择：M1 从纯 bf16 通用 matmul 打地基，还是直接拿现有 int8 kernel 改？**推荐前者**（先建立正确 + 可调基，再上 int8 复杂度）。
  2. 目标口径：沿用现有微基准（L2 偏袒）还是改用 HBM 公平基准？**推荐 HBM 公平口径**，避免节点 13 的陷阱重演。
  3. 上机环境：回 4090D 还是换新 GPU 机？数字随卡变，但学习序列 A 与机器无关。
- **关联**：节点 9（α 设计）/ 11 / 12 / 13 / 14（α 三重证伪）、wiki 权重量化内核效率、跨机续做指引。

---

## 节点 16：本机 GPU 环境复查 — 当前机器为 2× Tesla T4（2026-07-23）

> 用户要求复查 GPU 环境。**澄清**：T4 是**新租来学 kernel（路径 A）的环境**；之前的 12 项实验确实在 **RTX 4090D（Ada）** 上跑，结论照旧有效，并未被推翻。本节点只记录「当前这台 T4 机器的环境事实 + 对路径 A 的影响」。

- **状态**：✅ 已澄清（环境事实记录完毕，路径 A 待启动）
- **问题 / 解决**（torch 看不到 GPU）：
  - **现象**：首次查 `torch.cuda.is_available()=False`、`device_count=0`、`nvidia-smi` 不在 PATH；但 `/dev/nvidia0` `/dev/nvidia1` `nvidiactl` `nvidia-uvm` 都在，`/proc/driver/nvidia` 已加载（内核驱动 580.159.04）。
  - **根因**：`ldconfig -p` 只认了 `/usr/local/cuda` 的 `libcudart`，**没把 `/usr/local/nvidia/lib64`（含 `libcuda.so.580.159.04`）加进库搜索路径** → torch 加载不到 `libcuda.so.1`。`nvidia-smi` 实际在 `/opt/bin/` 但报「找不到 `libnvidia-ml.so`」，同样因库路径缺失。
  - **解法（验证有效）**：运行前设 `LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH`，torch 即 `cuda_available=True`、识别到 2 张卡。`nvidia-smi` 同理需把 `/usr/local/nvidia/lib64` 加进 `LD_LIBRARY_PATH`（或直接 `/opt/bin/nvidia-smi` 配合库路径）。
  - **防复发**：本机每开新 shell 跑 GPU 任务都需先 `export LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH`（建议写进项目 `.venv` activate 或 `~/.bashrc`）。
- **概念 / 认知（当前机器架构）**：**本机 = 2× Tesla T4（Turing, cc=7.5, 14GB, 40 SM）**，是路径 A 的 kernel 学习机；**不是**跑之前 12 项实验的 4090D。
  - **关键架构差异（影响路径 A 基准，不影响 4090D 结论）**：T4（Turing）**有 INT8 张量核，但没有 BF16 张量核**；4090D（Ada）两者都有。
  - **陷阱**：`torch.cuda.is_bf16_supported()` 在 T4 上返回 `True`——这仅表示 bf16 *数据类型* 可存储/转换，**不表示有 bf16 张量核**。在 T4 上 bf16 matmul 走的是非张量核的 CUDA core 路径 → **人为偏慢**。
  - **对节点 9 / 14 结论的说明（非翻案）**：节点 9/14「手写 int8 慢于 **bf16** 3.7× → 须 INT4(Marlin)」建立在 4090D（bf16 有张量核）之上，**仍然成立、不受影响**。T4 上 bf16 偏慢只是 Turing 缺 BF16 张量核的机器特性；若在 T4 重测「int8 vs bf16」会得到不同数字，但那是**换机器后的新基准**、不构成对 4090D 结论的反驳。要复核节点 9 须回 4090D（Ada）做。
  - **附加缺口**：`flash_attn` 未安装 → `bench.py`（依赖 `flash_attn_with_kvcache`）端到端跑不了；路径 A 的微基准（纯 GEMM）不需要它，故暂可不装。
- **需拍板点（路径 A 在 T4 上的执行）**：① M1 首个 Triton matmul 应改用 **fp16**（T4 有 fp16 张量核）而非原计划的 bf16（T4 无 bf16 张量核，会人为偏慢）；int8 同理可用张量核；② 340/750 GB/s 等带宽数字会变（T4 HBM ~300 GB/s），但学习序列 A 与机器无关；③ 是否在 T4 上跑 4090D 那 12 项实验当「换机基准」——注意数字不可与 4090D 直接对比。
- **关联**：节点 15（路径 A 规划）、节点 9 / 11 / 12 / 13 / 14（int8 vs bf16 证伪，均在 4090D、仍有效）、wiki 权重量化内核效率、跨机续做指引。

---

## 节点 17：路径 A·M1 — 第一个 Triton matmul 跑通（fp32, T4, 2026-07-23）

- **状态**：✅ 完成（T4 上 `cos=1.0` 对拍 PASS）
- **决策**：用户明确「先不管张量核，只要 Triton 能跑起来」→ 选 **fp32** 最简路径（不追求 fp16/int8 张量核），目标是把 tiled_gemm 心智模型平移到 Triton 并跑对。
- **实施**：新建 `project/vllm-plus/gemm_triton_m1.py`——标准分块 matmul kernel：C[M,N] 切成 `(BLOCK_M,BLOCK_N)` 块网格（每 program 一输出块），沿 K 维分 `BLOCK_K` 小块循环 `tl.dot` 累加。`run` 前须 `export LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH`（否则 torch 找不到 libcuda）。
- **结果**（对拍 torch fp32，3 组形状）：
  - (128,128,128)：cos=1.000000，max_abs_err=2.67e-05 ✅
  - (200,256,160) 非整数倍边缘：cos=1.000000，max_abs_err=2.67e-05 ✅
  - (64,4096,4096) 小 M 宽 K：cos=1.000000，max_abs_err=8.24e-04 ✅
  - 结论：M1 跑通，正确性达标；下一步 M2 定位带宽瓶颈（当前固定 BLOCK=32、无 autotune，未优化）。
- **问题 / 解决**（首跑 FAIL，cos≈0.5）：
  - **现象**：首版 `acc = tl.dot(a, b)`，三组 cos 仅 0.09~0.50、err 数十~数百，全部 FAIL。
  - **根因**：`tl.dot(a, b)` 的**第三参才是累加器**；不传时每轮迭代**覆盖** `acc` 而非累加 → 等价于只算了最后一个 K 分块，前面全丢。这正是 tiled_gemm「内积分块必须累加」在 Triton 上的对应陷阱。
  - **解法**：改为 `acc = tl.dot(a, b, acc)`（把上一轮累加值传回去）。
  - **学到了什么**：Triton 的 `tl.dot` 不是「原地累加」，是「返回 product，可选 acc 加回」；循环累加的写法与手写 tiled_gemm 的 `acc += A_tile @ B_tile` 一一对应，漏传 acc 是最易犯的错。
- **概念 / 认知（已萃取到 wiki，2026-07-23）**：本节点 M1 的通用教学概念已迁出通用笔记，runbook 只留项目视角指向与要点：
  - **Roofline / 带宽游戏 / 算术强度 AI（通用）** → [Roofline 模型与算术强度](../../wiki/gpu/roofline.md)。项目视角：T4 算力 ~8.1 TFLOPS、HBM ~320 GB/s → 拐点 AI*≈25 FLOP/Byte；这正是 M1「既没喂饱 HBM 也没喂饱 SM」判据的来源，也是节点 9「量化只救 decode 不救 prefill」的机理根。
  - **如何读 Triton matmul / off·ptr·mask / 寻址手算（通用）** → [Triton matmul 拆解](../../wiki/cuda/triton-matmul.md)。项目视角：M1 首跑 `acc = tl.dot(a, b)` 不传累加器 → cos≈0.5，改 `tl.dot(a, b, acc)` 后才 cos=1.0，是该笔记「tl.dot 第三参才是累加器」误区的最佳实证；寻址手算示例（M=64,K=96,N=64,B=32,pid=0）也完整收录其中。
- **关联**：节点 15（路径 A 规划）、节点 16（T4 环境）、wiki 分块 GEMM 的原理与切法、wiki HBM 流量与数据复用、节点 9（量化只救 decode）。

---

## 节点 18：路径 A·M2 — benchmark，量实际 GB/s / TFLOPS，标到 roofline（T4, 2026-07-23）

- **状态**：✅ 完成（M1 离 T4 天花板还差很远 → 量化出 M3 优化空间）
- **实施**：新建 `project/vllm-plus/gemm_triton_m2.py`——复用 M1 kernel，加计时：warmup 10 次丢弃启动开销 → `torch.cuda.synchronize()` 包住 `start/end.record()`（kernel 异步发射，不等完会量到 0）→ 循环 20 次取均值。指标 `GB/s = 字节数/秒`、`TFLOPS = 2MNK/秒`、`AI = FLOPs/字节`；并与 `torch.matmul`(cuBLAS) 同形状对比；再对 (1024,1024,1024) 做 BLOCK∈{16,32,64,128} 扫描。
- **结果**（T4：HBM~320 GB/s，fp32~8.1 TFLOPS，roofline 拐点 AI≈25.3）：
  - 形状表（ours vs torch/cuBLAS）：
    | shape (M,N,K) | AI | ours GB/s | ours TFL | torch GB/s | torch TFL | bound |
    |---|---|---|---|---|---|---|
    | (1,4096,4096) | 0.50 | 61.2 | 0.031 | 196.3 | 0.098 | BW |
    | (64,4096,4096) | 31.0 | 35.4 | 1.097 | 87.9 | 2.729 | COMPUTE |
    | (2048,2048,2048) | 341 | 5.7 | 1.944 | 12.1 | 4.132 | COMPUTE |
  - HBM 利用率（ours/320）：(1)19% / (64)11% / (2048)1.8%；torch 同形状 61%/27%/3.8%。
  - 算力利用率（ours/8.1）：(1)0.4% / (64)13.5% / (2048)24%；torch 1.2%/33.7%/51%。
  - BLOCK 扫描 @(1024,1024,1024)：BLOCK=16→5.7 GB/s(0.97 TFL, 1.8%)；BLOCK=32→13.3(2.27, 4.1%)；BLOCK=64→22.8(3.90, 7.1%)；**BLOCK=128 → OutOfResources**（T4 shared mem 上限 64KB，128×128 fp32 两 Tile=128KB 放不下）。
- **概念 / 认知（已萃取到 wiki，2026-07-23）**：本节点 M2 的 roofline 解读与指标定义已并入通用笔记 [Roofline 模型与算术强度](../../wiki/gpu/roofline.md)（上方「结果」表与利用率行的 T4 实测数字原样保留，不丢）。项目视角：M1 在带宽轴≤19%、算力轴≤24%，两端都远低于屋顶 → M3 优化空间巨大；BLOCK 16→64 把 TFLOPS 从 0.97 拉到 3.90（4×），但 BLOCK=128 因 T4 shared mem 64KB 上限爆 `OutOfResources` → 块大小是强杠杆但受片上容量硬约束。
- **关联**：节点 15（路径 A 规划）、节点 16（T4 环境）、节点 17（M1 跑通 + roofline 概念 + 寻址）。

---

## 节点 19：路径 A·M3 — 带宽爬坡：autotune + double buffer（num_stages）+ num_warps（T4, 待跑）

- **状态**：✅ 完成（fp32 autotune 把带宽受限形状 HBM 利用率从 M2 ≤19% 爬到 ~42%；中途修一处 stride 推进 bug，见「问题 / 解决」）
- **需拍板点**：M3 是否同时上 **fp16 张量核**（T4 有 fp16 张量核，比 fp32 快很多）？还是先只在 fp32 上把「autotune + double buffer 如何逼近 HBM 峰值」的机制跑透、fp16 留作单独一轮（避免一次引入两个变量）？建议**先 fp32 跑透机制**，fp16 张量核单独成一轮。等你拍板。
- **假设**：在 M1 kernel（fp32）上加 `@triton.autotune`（BLOCK_M/N/K + num_warps + num_stages），T4 上 HBM 利用率可从 M2 的 ≤19%（BLOCK=64 实测 22.8 GB/s，约 7% 利用率）显著爬升，逼近 T4 HBM ~320 GB/s 的更高比例（目标 50%+，即 ~160+ GB/s on 带宽受限形状）；与 cuBLAS 差距大幅收敛。
- **方法**：
  - 新建 `project/vllm-plus/gemm_triton_m3.py`，在 M1 kernel 上加 `@triton.autotune`：
    - `BLOCK_M, BLOCK_N, BLOCK_K` ∈ {16,32,64,128（受 T4 64KB shared mem 约束，autotune 自动避开 OOM 组合）}；
    - `num_warps` ∈ {2,4,8}（更多并发 warp → 更好藏延迟，见 wiki 延迟隐藏与占用率）；
    - `num_stages` ∈ {2,3,4,5}（软件流水 / double~triple buffer：让下一 K 段 load 与当前段 compute overlap → 直接对应「延迟隐藏」笔记的"搬和算 overlap"）。
  - 计时与指标同 M2（warmup + `cuda.synchronize` + GB/s/TFLOPS/AI），重点测**带宽受限形状**（小 M：如 (1,4096,4096)、(64,4096,4096)、(256,4096,4096)）的爬升；对比 M2 固定 BLOCK=32 基线 vs M3 autotune 最优 vs cuBLAS。
- **度量指标**：各形状 GB/s、HBM 利用率（% of 320）、TFLOPS、AI；重点看带宽受限形状爬升幅度、与 cuBLAS 差距收敛比；记录 autotune 选中的最佳 (BLOCK, num_warps, num_stages) 组合。
- **预期**：
  - HBM 利用率从 ≤19% 爬到 50%+（~160+ GB/s on decode 形状）；
  - **num_stages（double buffer）是主杠杆**（把"搬"与"算" overlap，藏住 HBM 延迟），num_warps 次之；
  - BLOCK=128 仍受 T4 shared mem 64KB 约束，autotune 应避开或用单缓冲；
  - 这轮会直观验证刚写的「延迟隐藏」笔记：算力没变（fp32 同），只是把并发内存请求喂满 → 带宽利用率飙升。
- **结果**（T4 fp32，ours vs torch/cuBLAS SGEMM；autotune 选最佳 (BLOCK,num_warps,num_stages)）：

  | shape (M,N,K) | AI | ours GB/s | HBM% | torch GB/s | best_config | cos |
  |---|---|---|---|---|---|---|
  | (1,4096,4096) | 0.5 | 135.9 | 42% | 235.5 | BM64/BN128/BK32 w8 s4 | 1.0000 |
  | (64,4096,4096) | 31.0 | 132.5 | 41% | 197.8 | BM64/BN128/BK32 w8 s4 | 1.0000 |
  | (256,4096,4096) | 113.8 | 34.3 | 11% | 49.0 | BM128/BN128/BK16 w8 s2 | 1.0000 |
  | (1024,1024,1024) | 170.7 | 29.6 | 9% | 36.7 | BM64/BN64/BK32 w4 s3 | 1.0000 |
  | (4096,4096,4096) | 682.7 | 6.4 | 2% | 6.2 | BM128/BN128/BK16 w8 s2 | 1.0000 |

  - **对比 M2 基线（节点 18 固定 BLOCK=32）**：(1,4096,4096) 61.2→135.9 GB/s（**2.2×**）；(64,4096,4096) 35.4→132.5 GB/s（**3.7×**）。autotune（主要是 num_stages 双缓冲 + num_warps 提升占用率 + 更大 BN）把带宽利用率从 ≤19% 拉到 ~42%，验证「延迟隐藏」笔记机制生效：算力没变（同 fp32），只是把并发内存请求喂满。
  - **剩余差距**：cuBLAS fp32(SGEMM, 无张量核) 达 235 GB/s（74%），ours 42% → 约 1.7× 头room，来自 Triton 未用满 SMEM/寄存器排布；T4 fp32 无张量核，cuBLAS 也只靠 CUDA core，差距是 kernel 质量而非硬件。
  - autotune 偏好：带宽受限形状选 BN=128 + w8 s4（更大 tile 复用 + 更多并发 warp/stage 藏延迟），与「num_stages/num_warps 即延迟隐藏旋钮」一致。
- **问题 / 解决**（首跑 cos≈0.0068，全错）：
  - **现象**：autotune 跑通但 5 个形状 cos 全在 0.005~0.03（应≈1.0），结果完全不相关。
  - **根因**：K 循环里 B 的指针推进写错——`b_ptrs += BLOCK_K * stride_bn`（沿 N 轴）而非 `b_ptrs += BLOCK_K * stride_bk`（沿 K 轴）。A 的 K 维是第 2 维（stride=1）故 `ap += BLOCK_K*stride_ak` 正确；B 的 K 维是**第 1 维**（stride=N），推进必须用 `stride_bk`。误用 `stride_bn` 使每个 K 段都读错位的内存 → 结果噪声化。
  - **解法**：单块测试（无 K 循环，cos=1.0）隔离出 bug 在循环推进；改 `stride_bn`→`stride_bk` 后全形状 cos=1.0。
  - **防复发**：写 Triton GEMM 时 A/B 的 K 循环推进必须**各自用本张量的 K-stride**（`stride_ak` / `stride_bk`），绝不可两处都写 `stride_bn`；先在最小单块（K=BLOCK，无循环）验证 cos=1.0 再上完整循环。
  - **学到了什么**：这跟「tl.dot 第三参才是累加器」是同一类陷阱——分块 GEMM 的「K 维在 A/B 里是不同维度」决定了指针推进的 stride 不对称；对称性假设害死人。
- **概念 / 认知（形状选择 = 优化对象）**：(256,4096,4096) AI=114 > T4 拐点 AI*≈25 → 已**算力受限**（GB/s 仅 34 但 TFLOPS 53%），不是带宽游戏；真正带宽受限的是 **AI<AI\* 的小 M 形状**（(1,\*) AI0.5、(64,\*) AI31 近拐点）。印证 roofline：带宽优化要把精力放在 AI<AI\* 的形状，算力受限形状再怎么调带宽也救不了（受 8.1 TFLOPS 天花板锁死）。
- **关联**：节点 17/18（M1/M2 基线）、wiki 延迟隐藏与占用率（num_warps/num_stages 即延迟隐藏旋钮，本节点 2.2~3.7× 提升是其直接证据）、wiki Roofline 模型与算术强度（AI 拐点判定优化对象）、wiki HBM 流量与数据复用（autotune 提升 tile 复用）、wiki 分块 GEMM 的原理与切法（A/B 的 K 维分处不同维度 → 指针推进 stride 不对称）。

---

## 节点 20：路径 A·M3 ablation — num_stages 对带宽的实测影响（T4, fp32, 2026-07-23）

- **状态**：✅ 完成（固定 BLOCK_M=64/BN=128/BK=32、num_warps=8，扫 num_stages∈{2,3,4,5}，收口「stages 预取深度真能顶满带宽」）
- **背景**：节点 19 用 autotune 间接证明 num_stages 是延迟隐藏主杠杆（2.2~3.7× 提升），但 autotune 同时动了 BLOCK/num_warps，变量没隔离。本节点按用户「跑」指令做**单变量 ablation**：只动 num_stages，其余冻结，直接验证「stages 越深 → 在途 HBM 请求越多 → 带宽越顶满」。
- **方法**：新建 `project/vllm-plus/gemm_triton_m3_ablation.py`——去掉 `@triton.autotune`，开一个 `@triton.jit` kernel，launch 时显式传 `num_warps=8, num_stages=s`；测带宽受限形状（小 M）+ 算力受限形状（大 M），各算 cos 校验正确性。
- **结果**（T4 fp32，固定 BM64/BN128/BK32/w8，仅变 num_stages）：

  | shape (M,N,K) | AI≈ | s=2 GB/s | s=3 | s=4 | s=5 | cos |
  |---|---|---|---|---|---|---|
  | (1,4096,4096) | 2.0 | 53.9 | 54.0 | **100.8** | 100.8 | 1.0000 |
  | (64,4096,4096) | 124 | 106.9 | 107.0 | 108.3 | **111.2** | 1.0000 |
  | (256,4096,4096) | 455 | 31.7 | 31.4 | 31.9 | 31.8 | 1.0000 |
  | (1024,4096,4096) | 1365 | 11.5 | 11.5 | 11.5 | 11.5 | 1.0000 |

- **解读**：
  1. **stages 只在带宽受限区有效**：M=1（AI=2）s2→s4 从 53.9 跳到 100.8 GB/s（+87%），s5 平台；M=64（AI=124 近拐点）渐进 106.9→111.2。证明「更深预取 → 更多在途 load → HBM 更满」成立。
  2. **算力受限区 stages 完全无效**：M=256（AI=455）、M=1024（AI=1365）GB/s 在所有 stages 下恒定（~31 / ~11）。roofline 直接证据——形状已越过 T4 拐点 AI*≈25，被 8.1 TFLOPS 算力天花板锁死，藏延迟救不了带宽（此时 GB/s 低是 compute-bound 的标志，不是 kernel 差）。
  3. **M=1 即便 s5 也只到 32% HBM**：32 blocks / 40 SM ≈ 0.8 block/SM → 多数 SM 空闲、喂不饱 HBM，这是「grid 太小」惩罚（节点 19 已记），非 stages 之过；autotune 版 M=1 达 42% 是因它另选了更优 BLOCK/BN。
- **重要更正（诚实记录，推翻我先前口头预测）**：我在 Q1 里手算「单 stage SMEM=(BM·BK+BK·BN)·4=24KB，s3+ 超 T4 64KB/SM → 该配置不可用/occupancy 掉 0」。**实测全部 s2~s5 都编译跑通且 cos=1.0**——说明该 naive 上界严重高估了 Triton 实际流水缓冲占用（dot 很可能从寄存器而非全程常驻 SMEM、或 Triton 用了更紧凑布局）。**教训：SMEM 预算必须实测，不能只靠公式臆测**；T4 64KB 墙在这组配置下并未触发（虽节点 18 曾因 BLOCK=128 真实撞过 `OutOfResources`，那次是另一回事——块太大而非 stages 多）。
- **概念 / 认知**：本节点把节点 19 的「num_stages=延迟隐藏旋钮」从相关关系升级为**单变量因果**——且仅在 AI<AI* 的带宽受限形状上成立；越过拐点，旋钮失灵。这正是 roofline 划分优化对象的操作化证明。
- **关联**：节点 19（M3 autotune 间接证据 → 本节点单变量收口）、节点 16（T4 环境）、节点 18（BLOCK=128 真实撞 64KB SMEM 墙，对照本节点「stages 未撞墙」）、wiki 延迟隐藏与占用率、wiki Roofline 模型与算术强度（AI 拐点 = stages 旋钮生效边界）。

---

## 节点 21：路径 A·M4 — fp16 张量核终验（T4, 2026-07-23）

- **状态**：✅ 完成（终验结论：**T4 fp16 张量核硬件正常，但本机 Triton 3.6 + sm_75 不会为 fp16 `tl.dot` 生成 `mma.sync`**，故手写 Triton fp16 未吃到 TC；张量核红利由 torch/cuBLAS 实测确认存在）
- **背景**：节点 15/19 规划 M4「上 T4 张量核（fp16）终验」。T4(Turing cc7.5)有 fp16 张量核、无 bf16/fp32 张量核。预期 fp16 `tl.dot` 编译为 `mma.sync`，算力天花板从 fp32 CUDA core 8.1 TFLOPS → fp16 张量核 ~65 TFLOPS（约 8×）。
- **方法**：新建 `project/vllm-plus/gemm_triton_m4_fp16.py`：M3 kernel 改 fp16 输入 + fp32 累加（`tl.dot(fp16,fp16,fp32_acc)`）+ autotune；测 ours fp16 vs torch fp16(cuBLAS HGEMM/TC 天花板) vs M3 fp32 基线，各形状算 cos。
- **结果**（T4 fp16；ours=手写 Triton fp16，torch=cuBLAS HGEMM/TC）：

  | shape (M,N,K) | AI≈ | ours TFLOPS | TC% | torch TFLOPS | torch TC% | cos |
  |---|---|---|---|---|---|---|
  | (1,4096,4096) | 1.0 | 0.03 | 0% | 0.01 | 0% | 1.0000 |
  | (64,4096,4096) | 61 | 1.72 | 3% | 14.74 | 23% | 1.0000 |
  | (256,4096,4096) | 216 | 1.25 | 2% | 36.79 | 57% | 1.0000 |
  | (1024,4096,4096) | 585 | 1.22 | 2% | 29.44 | 45% | 1.0000 |
  | (4096,4096,4096) | 1024 | 1.21 | 2% | 21.44 | 33% | 1.0000 |

  - ours 全形状卡在 ~1.2 TFLOPS（甚至低于我们自己的 fp32 M3），cos=1.0（正确但慢）；torch fp16 在算力受限形状冲到 21~37 TFLOPS（达 fp16 张量核峰值 65 TFLOPS 的 33~57%）。→ **T4 张量核红利真实存在（~8× 于 fp32 天花板），但 Triton 没把它交给我们**。
- **根因（关键，经 PTX/ttgir 实锤）**：dump `comp.asm['ptx']` 与 `['ttgir']` 确认 ours fp16 kernel **PTX 中无 `mma` 指令**。逐变量排除：
  - 全局 `tl.load` 本身是 f16（`!tt.ptr<f16>` 正确）——不是加载上转的锅；
  - 进入 `tl.dot` 后，Triton 把操作数在共享内存 staging 时**提升为 f32**（`tensor<64x32xf32, #ttg.dot_op<...>>`）且布局是 `#blocked`（**非 MMA 编码**），`inputPrecision=tf32`；
  - 试过 mask / num_stages∈{1,2,3} / `input_precision='ieee'` / `out_dtype=tl.float16` 全部无效；`out_dtype=fp16` 时操作数虽为 f16 但仍 `#blocked2` 布局 + 误设 `tf32` 精度，且 cos 崩到 0.13（错误结果）。
  - **结论**：Triton 3.6 在 sm_75 上的 `tl.dot` fp16→MMA lowering 未生效（操作数提升 f32 或布局错配），退回 CUDA core。属**工具链/版本层限制**，非 kernel 写法问题。
- **概念 / 认知（本项目最重要的误区纠正）**：**「`tl.dot(fp16)` 自动吃到张量核」是个常见错觉**。张量核红利要由编译器正确 lowering 成 `mma.sync` 才兑现；本组合(Triton 3.6 + Turing sm_75)没做到。要真正吃到 TC，路径是 cuBLAS/CUTLASS，或换能正确为 sm_75 生成 fp16 `mma` 的 Triton 版本。这也呼应节点 9「手写 int8 慢于 bf16 → 须 INT4(Marlin)」——**手写内核的峰值效率高度依赖底层 lowering，不是数据类型一换就自动加速**。
- **关联**：节点 16（T4 有 fp16 TC / 无 bf16·fp32 TC）、节点 19（M3 fp32 基线 ~8 TFLOPS → 对照 M4 手写 fp16 仍 ~1.2 TFLOPS，证明非 TC）、节点 9（手写内核峰值依赖 lowering）、wiki 延迟隐藏与占用率（TC 是另一维加速，与本路径 stages/warps 正交）、wiki Roofline（fp16 张量核把算力天花板从 8.1 抬到 65 TFLOPS → compute-bound 形状拐点右移）。

---

## 节点 22：路径 A·M5 — int8 张量核终验（T4, 2026-07-23）

- **状态**：✅ 完成（终验结论：**Triton 3.6 + sm_75 编译 int8 `tl.dot` 直接失败**——lowering 把 `arith.extf`（浮点扩展）误用到 `i8` 操作数，`TritonGPUAccelerateMatmul` pass 崩溃；与 M4 fp16 同类编译器后端 bug。T4 int8 张量核硬件经 `torch._int_mm`（cuBLAS IGEMM）确认存在，但本路径仅达 4.5~17.4 TOPS）
- **背景**：M4 fp16 因 Triton 不生成 mma 翻车；M5 试 int8 张量核（T4 有 int8 TC ~130 TOPS），看是否绕开 fp16 的限制。吸取 M4 教训，本次**先强制 dump 编译确认**再下结论。
- **方法**：新建 `project/vllm-plus/gemm_triton_m5_int8.py`：对称 per-tensor 量化 A/B→int8，`tl.dot(int8,int8,out_dtype=tl.int32)` 累积 int32，输出反量化；`check_triton_int8()` 先编译一次确认 mma 是否生成。
- **结果**：
  - **Triton int8 编译：FAILED**。`matmul_int8_kernel` 编译报错：`error: 'arith.extf' op operand #0 must be floating-point-like, but got 'tensor<128x64xi8, #ttg.dot_op<...>>'`；`PassManager::run failed`（pipeline `TritonGPUAccelerateMatmul`）。即 int8 dot 的 MMA lowering 把整数操作数当浮点处理 → 编译期崩溃。→ **手写 Triton int8 kernel 在此工具链下彻底不可行**。
  - **torch int8（`torch._int_mm`，cuBLAS IGEMM/TC 天花板）**：cos~0.9998~0.9999（量化正确）；TOPS：

    | shape | TOPS | TC% | 备注 |
    |---|---|---|---|
    | (1,4096,4096) | N/A | - | `torch._int_mm` 要求 M≥16，decode 小 M 不支持 |
    | (64,4096,4096) | 4.5 | 3% | |
    | (256,4096,4096) | 9.5 | 7% | |
    | (1024,4096,4096) | 13.6 | 10% | |
    | (4096,4096,4096) | 17.4 | 13% | |

- **解读（重要，与 M4 同构）**：
  1. **Triton 3.6 在 sm_75 上 int8 / fp16 的 `tl.dot`→MMA lowering 双双损坏**：fp16 把操作数提升 f32 退回 CUDA core（M4）；int8 编译期 `extf`-on-`i8` 直接挂（M5）。结论：**该组合（Triton 3.6 + Turing sm_75）下"手写 Triton 张量核"不可行——不是 kernel 写法问题，是编译器后端 bug**。要真吃到张量核，须 cuBLAS/CUTLASS，或换能正确为 sm_75 生成 fp16/int8 `mma` 的 Triton 版本。
  2. **峰值 TOPS ≠ 实得吞吐**：`torch._int_mm` 实测仅 4.5~17.4 TOPS，远低于 T4 int8 峰值 130（3~13%）。说明 int8 张量核提取高度依赖 shape/layout/库（对齐、tile、packing）；即便走 cuBLAS，这些形状也没榨干 TC。但这 17.4 TOPS 仍约 **2× 我们 fp32 M3 的 ~8 TFLOPS（≈8 TOPS 等价）**——印证 int8 相对 fp32 仍有收益，只是远未到 16× 峰值比。
  3. **量化正确性扎实**：per-tensor 对称量化对 randn 即达 cos 0.9998~0.9999，证明量化方案本身没问题，瓶颈纯在 kernel/库层。
- **概念 / 认知**：路径 A 的 M3→M5 串起一条硬道理——**数据类型/张量核红利不是「换个 dtype 就自动加速」，它要求编译器正确 lowering 成 `mma.sync`（M4/M5 证明 Triton 3.6+sm_75 做不到），且即便库层做对了，实得吞吐也受 shape/layout 强烈制约**。这把节点 9「手写 int8 慢于 bf16 → 须 INT4(Marlin)」从"现象"升级为"机制"：手写/库内核的峰值效率由 lowering + 形状适配共同决定。
- **关联**：节点 21（M4 fp16 同族 lowering bug）、节点 16（T4 有 int8 TC 硬件）、节点 19（M3 fp32 基线 ~8 TFLOPS，对照 int8 ~2×）、节点 9（手写内核峰值依赖 lowering）、wiki Roofline（int8 张量核抬高算力天花板，但实得远低峰值）。

---

## 交付产物清单

| 产物 | 位置（项目相对） | 来源 | 状态 |
|------|----------------|------|------|
| 投机解码（小模型 draft）实现 | `nanovllm/engine/model_runner.py` `scheduler.py` | 实验1-6 | ✅ |
| ngram / Prompt Lookup + 验证批 CUDA Graph | `nanovllm/engine/model_runner.py` (`capture_spec_cudagraph`) | 实验9 | ✅ 重复文本 1.48~2.0x |
| Lookahead/Jacobi 树 + 自适应 K + 无损拒绝采样 | `nanovllm/engine/model_runner.py` `_verify_tree` | 实验7/4 | ✅ 正确但 0.02x（参考） |
| KV Cache Swap 抢占 | `nanovllm/engine/{model_runner,block_manager,scheduler}.py` + `config.swap_space` | 实验8 | ✅ 正确但吞吐反劣（可选） |
| 调度器 Watermark | `nanovllm/engine/block_manager.py` `can_allocate` + `config.watermark` | 实验10 | ✅ 默认开 |
| INT8 KV Cache 量化 | `nanovllm/layers/attention.py` `fused_int8_decode` + `config.kv_cache_dtype` | 实验11 | ✅ +4~13% |
| INT8 权重量化 (W8A8) | `nanovllm/layers/quant_linear.py` | 实验12 | ✅ 正确但偏慢（参考） |
| INT8 权重量化 (W8A16) 重写 α | `nanovllm/layers/{quant_linear,linear}.py` `config.py` `engine/model_runner.py` `bench_int8_gemm.py` | α 实验 | ✅ 修 3 bug（swizzle 漏钳位 / 缺 import os / int8 requires_grad）+ 禁 split-K；微基准 cos=1.0 但仍慢；端到端 1389 vs 2187 tok/s（0.63×）证伪 → 参考实现 |
| 实验原始记录 | `experiment_results.md` | 全 12 项 | ✅（机器本机，不进 grounds） |
| 实验方案 | `experiments_plan.md` | — | ✅ |
| 面经 | `interview_questions.md` / `interview_answers.md` | — | ✅ |
| bench 驱动（含 continuous / DTYPE / WQUANT / USE_LOOKAHEAD 开关） | `bench.py` | 全实验 | ✅ |
| 分块 GEMM 参考实现（GPU-free）：naive + tiled + 对拍 + 块网格 + Triton 映射 | `project/vllm-plus/gemm_foundations.py` | 路径 A·M0 | ✅ Mac CPU 跑通（对拍 err 9.5e-5）；GPU 机可作 M1→Triton 翻译基线 |
| 第一个 Triton matmul（fp32, 分块 + tl.dot 累加，先跑通） | `project/vllm-plus/gemm_triton_m1.py` | 路径 A·M1 | ✅ T4 上 3 组形状 cos=1.0 对拍 PASS（固定 BLOCK=32，未优化） |
| M1 benchmark（计时 + GB/s/TFLOPS/AI + roofline + block 扫描） | `project/vllm-plus/gemm_triton_m2.py` | 路径 A·M2 | ✅ 量出 M1 距 T4 天花板：HBM 利用率≤19%、算力≤24%；BLOCK 16→64 提速 4×；BLOCK=128 爆 shared mem(64KB) |
| M3 fp32 autotune benchmark（autotune BLOCK/num_warps/num_stages + 计时 + GB/s/TFLOPS/AI + 对照 cuBLAS） | `project/vllm-plus/gemm_triton_m3.py` | 路径 A·M3 | ✅ 带宽受限形状 HBM 利用率 ≤19%→~42%（2.2~3.7×）；修 B 的 K-stride 推进 bug |
| M3 ablation（单变量：固定 BLOCK_M64/BN128/BK32/num_warps8，扫 num_stages∈{2,3,4,5}，隔离 stages 对带宽的因果） | `project/vllm-plus/gemm_triton_m3_ablation.py` | 路径 A·M3 收口 | ✅ 实测证 num_stages 仅在 AI<AI*(带宽受限) 生效（M=1: s2→s4 53.9→100.8 GB/s +87%），算力受限形状 stages 失灵；cos 全 1.0 |
| M4 fp16 张量核终验（fp16 输入 + fp32 累加，autotune；ours Triton fp16 vs torch/cuBLAS HGEMM 天花板） | `project/vllm-plus/gemm_triton_m4_fp16.py` | 路径 A·M4 | ✅ **终验结论：Triton 3.6 + sm_75 不为 fp16 tl.dot 生成 mma.sync（PTX 实锤无 mma），ours 卡 ~1.2 TFLOPS；torch fp16(cuBLAS TC) 达 21~37 TFLOPS 证张量核硬件正常** |
| M5 int8 张量核终验（对称 per-tensor 量化→int8；tl.dot(int8,int8,int32_acc)；先 dump 编译确认） | `project/vllm-plus/gemm_triton_m5_int8.py` | 路径 A·M5 | ✅ **终验结论：Triton 3.6+sm_75 编译 int8 tl.dot 直接失败（extf on i8 lowering bug，与 M4 同族）；torch._int_mm 量化正确 cos~0.9999 但仅 4.5~17.4 TOPS（峰值 130 的 3~13%）** |

> ⚠️ **漂移**：`gemm_triton_m1.py` / `gemm_triton_m2.py` / `gemm_foundations.py` 在 runbook 记为已建，但**未进 vllm-plus 远程、本机工作树缺**；M3 为自包含重建（含 kernel）。如需 m1/m2 脚本应从此工作树补建并推 vllm-plus 远程。

---

## 能力账本 / 下一步

- **当前阶段**：阶段 3（熟练）——已能独立设计实验、定位根因、对「为什么某优化无效」给出结构性解释（如实验11/12 的「decode 瓶颈=权重访存」甄别）。
- **已掌握**：投机解码原理与 verify 瓶颈；CUDA graph 捕获/replay 收敛 Python 开销；KV 量化数值对齐；调度 watermark 本职（防抖动 vs 防 OOM）；`flash_attn` 跨 batch/seqlen_q 数值敏感性；手写 Triton GEMM 的 grouped swizzle 必须钳位 `group_size_m`（小 M 数值回归必要性）；split-K 补 CTA 的代价（torch 端归约开销）。**＋路径 A·M0：decode GEMM 分块心智模型**（详见 [分块 GEMM 的原理与切法](../../wiki/gemm/tiled-gemm.md) 与 [HBM 流量与数据复用](../../wiki/gpu/hbm-traffic.md)）；已在 Mac 上跑通 `gemm_foundations.py` 并对拍 PASS。
- **还不会 / 待补**：
  - FP8 权重量化（需 Hopper/Blackwell 卡，超出本机范围）。
  - CUTLASS 级 INT8 GEMM（手写 Triton 内核带宽效率不足）。
  - GPU kernel 级 profiling（当前靠 monkey-patch + `cuda.synchronize` 粗粒度计时）。
  - **路径 A 后段（T4 上推进中）**：M1 首个 Triton fp32 matmul 已跑通（cos=1.0，见节点 17）→ **M2 已完成**（节点 18：T4 上 HBM 利用率≤19%、算力≤24%、BLOCK 16→64 提速 4×）→ **M3 已完成**（节点 19：fp32 autotune 把带宽受限形状 HBM 利用率从 ≤19% 爬到 ~42%，修一处 B 的 K-stride 推进 bug）→ **M4 已完成**（节点 21：fp16 张量核终验——Triton 3.6+sm_75 不为 fp16 tl.dot 生成 mma.sync，手写 fp16 卡 ~1.2 TFLOPS；torch/cuBLAS HGEMM 实测 21~37 TFLOPS 证张量核硬件正常）→ **M5 已完成**（节点 22：int8 张量核终验——Triton 3.6+sm_75 编译 int8 tl.dot 直接失败（extf-on-i8 lowering bug，与 M4 同族）；torch._int_mm 量化正确 cos~0.9999 但仅 4.5~17.4 TOPS）。**路径 A 张量核线结论：Triton 3.6+sm_75 无法手写 fp16/int8 张量核（编译器后端 bug），张量核红利须走 cuBLAS/CUTLASS 或换 Triton 版本** → 下一步可选 **M6：换 Triton 版本（或 CUTLASS/cuBLAS 直连）复测 fp16/int8 mma，确认是版本问题并真正吃到 T4 张量核峰值**，或收尾路径 A（T4 上手写 Triton 内核的地基已打牢，张量核受工具链所限，结论清晰）。
- **下一步该练**：把 12 项实验转化为「可讲清楚取舍」的简历叙事与面试话术（强项在「能说清每个优化为什么有效/无效」，而非只会报数字）。

---

## 跨机续做指引（resume）

- **状态**：✅ 一切已推远程，换机零丢失（用户原先在租的 4090D 服务器，本轮选定路径 A 后需换机）。
- **两仓远程**：
  - 代码 `git@github.com:hypiasd/vllm-plus.git`（commit `e28d7e6`：swizzle 钳位 / 禁 split-K / import os / requires_grad 修复）。
  - 笔记 `git@github.com:hypiasd/grounds.git`（`project_logs/vllm-plus/`，本文件）。
- **新机恢复**：
  1. `git clone git@github.com:hypiasd/grounds.git && cd grounds && git clone git@github.com:hypiasd/vllm-plus.git <dir>`
  2. `$project <dir>/vllm-plus`（重建软链 + 进入项目模式）。
  3. `cd <dir>/vllm-plus && pip install -e .`（`.venv` 不进 git，需按机器重建）。
  4. 模型 `~/huggingface/Qwen3-4B` **不进 git（~8GB）**，新机需重下或拷贝。
- **当前线程**：路径 **A（从 0 打 kernel 地基）已规划**（见节点 15）：先懂带宽游戏 → M1 第一个 Triton GEMM（先跑对）→ M2 定位带宽瓶颈（已完成，节点 18；340 GB/s 为 4090D 专属，T4 实际峰值 ~320）→ M3 带宽优化爬坡（已完成，节点 19）→ M4 上 T4 张量核（fp16/int8）终验。学习序列与机器无关；上 GPU 机后按节点 15 里程碑逐站执行，每站用实验卡记录。
- **机器相关性**：340/750 GB/s 等数字是 4090D 专属；新机 GPU 不同则 autotune/数值会变，但**学习序列 A 与机器无关**。
- **2026-07-23 注**：当前 grounds 工作机**本身有 GPU（2× Tesla T4, cc 7.5）**，是**新租来学 kernel（路径 A）的环境**；之前 12 项实验在 **RTX 4090D（Ada）** 上跑、结论仍有效。T4 ≠ 4090D——T4 有 INT8 张量核、**无 BF16 张量核**（见节点 16），因此路径 A 的 M1 首个 Triton matmul 应改用 **fp16**（才有张量核加速）而非原计划 bf16；节点 9「int8 慢于 bf16 → 须 INT4」是 4090D 结论、不受影响。在 T4 上跑 GPU 任务前必须 `export LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda-12.8/lib64:$LD_LIBRARY_PATH`。
- **关联**：节点 12 / 13 / 14。

## 萃取记录（capture 历史）

- 2026-07-22：将「路径 A·M0：decode GEMM 分块心智模型」从 runbook（节点 15 能力账本「已掌握」）萃取至 wiki/gemm/tiled-gemm.md（分块 GEMM 的原理与切法）与 wiki/gpu/hbm-traffic.md（HBM 流量与数据复用）（原位留指针，正文迁出）。
- 2026-07-23：将「路径 A·M1/M2 通用教学概念」从 runbook（节点 17/18 概念块）萃取至 wiki/cuda/triton-matmul.md（Triton matmul 拆解：两层结构 / 1D program_id / off·ptr·mask / 寻址手算 / tl.dot 累加器误区）与 wiki/gpu/roofline.md（Roofline 模型 / AI / GB-s / TFLOPS / 指标定义）。节点 17/18 原位改为 2+1 行指针（各带 T4/M1/M2 项目视角注解），T4 实测数字（结果表、利用率、BLOCK 扫描）保留不丢。

