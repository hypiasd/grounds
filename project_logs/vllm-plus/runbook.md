---
title: vllm-plus 运行手册（时间线 / 决策 / 踩坑 / 能力账本）
tags: [project, vllm-plus]
created: 2026-07-22
updated: 2026-07-22
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
| INT8 权重量化 (W8A16) 重写 α | `nanovllm/layers/{quant_linear,linear}.py` `config.py` `engine/model_runner.py` `bench_int8_gemm.py` | α 实验 | 🔧 已实现，待 4090D 验证 |
| 实验原始记录 | `experiment_results.md` | 全 12 项 | ✅（机器本机，不进 grounds） |
| 实验方案 | `experiments_plan.md` | — | ✅ |
| 面经 | `interview_questions.md` / `interview_answers.md` | — | ✅ |
| bench 驱动（含 continuous / DTYPE / WQUANT / USE_LOOKAHEAD 开关） | `bench.py` | 全实验 | ✅ |

---

## 能力账本 / 下一步

- **当前阶段**：阶段 3（熟练）——已能独立设计实验、定位根因、对「为什么某优化无效」给出结构性解释（如实验11/12 的「decode 瓶颈=权重访存」甄别）。
- **已掌握**：投机解码原理与 verify 瓶颈；CUDA graph 捕获/replay 收敛 Python 开销；KV 量化数值对齐；调度 watermark 本职（防抖动 vs 防 OOM）；`flash_attn` 跨 batch/seqlen_q 数值敏感性。
- **还不会 / 待补**：
  - FP8 权重量化（需 Hopper/Blackwell 卡，超出本机范围）。
  - CUTLASS 级 INT8 GEMM（手写 Triton 内核带宽效率不足）。
  - GPU kernel 级 profiling（当前靠 monkey-patch + `cuda.synchronize` 粗粒度计时）。
- **下一步该练**：把 12 项实验转化为「可讲清楚取舍」的简历叙事与面试话术（强项在「能说清每个优化为什么有效/无效」，而非只会报数字）。
