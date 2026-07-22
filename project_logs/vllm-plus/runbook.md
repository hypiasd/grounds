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
    - **概念洞察（用户问「为什么可以分块」）**：分块合法性来自矩阵乘的**两个可加性**——①**输出元素独立**：`C[i,j]=Σ_k A[i,k]·B[k,j]` 只依赖 A 的第 i 行 + B 的第 j 列，C 的块之间无任何数据依赖 → 可任意切片、可并行；②**K 维求和可拆**：一个 C 块 = `Σ_{kk} A[I,kk:kk+BK]·B[kk:kk+BK,J]`，K 维只是普通加法，满足交换/结合律 → 可分段、可乱序、可并行累加。**分块"能算对"是因为加法可分组；分块"算得快"是因为数据复用**——朴素写法 A 的每行被重搬 K×N 次，分块把 (BM×BK) 小块搬进寄存器/缓冲后复用 BK 次，搬运次数骤降。这正是"带宽游戏"下打带宽墙的核心武器：分块把"可加性"转成了"复用率"。
    - **代码细节洞察（用户问「写回为何用 `=` 而非 `+=`」）**：`tiled_gemm` 第70行 `C[bi:i_end,bj:j_end] = acc` 正确。`=` 合法因两点——①块间不重叠：外层按 M/N 切，每个 `(bi,bj)` 块对应 C 唯一子矩阵，无两程序写同址；②K 累加已在局部 `acc` 内完成（第67行 `acc += A_tile@B_tile` 是**矩阵级**逐 K 段累加，K 维全吃完才写回）。朴素版第28行 `acc += A[i,k]*B[k,j]` 的 `+=` 是**标量级**跨 k 累加、写回仍是 `C[i,j]=acc`——两种写法的 `+=` 都作用在 acc 自身，写回都是 `=`。真需 `+=`（GPU 上 `tl.atomic_add`）仅 split-K 场景：把 K 维也分给多程序、各算某块 C 的"一段 K"需合并到同址。Triton 官方 matmul 单程序吃完整 K → `=`。即便 NumPy 把 `=` 改 `+=` 也数值等价（C 初值0且每块只写一次），但 GPU 上 `+=` 暗示竞争同址需昂贵 atomic，故 `=` 才是正确语义。
    - **可视化（用户要「画个图」理解分块）**：三图见下。图1 输出块网格（C 按 M/N 切，块间互不重叠，每块一个程序）；图2 单块数据流（C 块 = A 行块 × B 列块）；图3 K 维分段累加（沿 K 切 BK 段逐段乘加进 acc，K 吃完写回 `=`）。数据复用（A 行块搬入后与 BK 个 B 列块复用）即"带宽游戏"的破墙点。
      ```
      图1 — 输出块网格：C 按 M/N 切，每块一个程序，互不重叠
              N 维（按 BN 切）
            ┌──────┬──────┬──────┐
            │0,0   │0,1   │0,2   │  每格 = C 的一个 (BM×BN) 块
        M   ├──────┼──────┼──────┤  一个"程序"独立负责，互不重叠
        │   │1,0   │1,1   │1,2   │
       (BM) ├──────┼──────┼──────┤
            │2,0   │2,1   │2,2   │
            └──────┴──────┴──────┘
              按 BM 切（行块）
        网格 = ⌈M/BM⌉ × ⌈N/BN⌉  （4096/64 → 64×64 = 4096 块）

      图2 — 单块 (bi,bj) 从哪来：A「行块」× B「列块」
              K 维（被切成 BK 段，见下图3）
         A[bi:i_end, :]        B[:, bj:j_end]        C[bi:i_end,bj:j_end]
         ┌──────────┐         ┌──────────┐          ┌────────┐
         │ 行块     │         │ 列块     │          │ 块     │
         │ BM × K   │    ×    │ K × BN   │    =     │ BM×BN  │
         └──────────┘         └──────────┘          └────────┘
            ↑ 第 bi 行段           ↑ 第 bj 列段           ↑ 落在 (bi,bj)

      图3 — K 维分段累加：长条切 BK 小段，逐段搬入乘、攒进 acc
         A 行块            B 列块            累加器 acc (BM×BN)
         ┌────┐  ×  ┌────┐
         │k:0 │     │0:BN│   →  acc += A[:,0:BK]   @ B[0:BK,:]     (第1段)
         └────┘      └────┘
         ┌────┐  ×  ┌────┐
         │BK  │     │0:BN│   →  acc += A[:,BK:2BK] @ B[BK:2BK,:]   (第2段)
         └────┘      └────┘
            ... (继续 BK 段，直到 K 吃完) ...
         acc 含全部 K 贡献 → C[bi:i_end,bj:j_end] = acc   (写回用 =)
      ```
      复用点：A 行块 [BM,BK] 搬入后，与 BK 个 B 列块分别相乘 → 复用 BK 次，搬运次数骤降（呼应"带宽游戏"）。
    - **概念精确化（用户把切分理解为「A 只按行、B 只按列」）**：用户的"外层按 M/N 切输出块、内层沿 K 切 tile"方向正确，但需补两点——①**A 与 B 各自都被切了两个维度**，不是 A 只按行、B 只按列：A 切 **M(行块, 由 bi 定) + K(K段, 由 bk 定)**；B 切 **K(K段, 由 bk 定) + N(列块, 由 bj 定)**。② **A_tile 与 B_tile 是从「已锁定的 A 行块 / B 列块」里沿同一段 K 对齐切出**，二者 K 范围必须相同（`A[bi:i_end, bk:k_end]` 的 `bk:k_end` 必须 = `B[bk:k_end, bj:j_end]` 的 `bk:k_end`）才能相乘（形状 [BM,BK]×[BK,BN]）。不是"先切 A 的行、再切 B 的列、再各自切 K"的串行，而是"外层 (bi,bj) 同时锁定行块/列块，内层 bk 滑动时同步取对齐 K 段"。
    - **概念：数据复用（reuse）**：复用 = 一块数据从慢内存(HBM)搬上来后，能在快存储器(寄存器/共享内存/L2/缓存)里被用多少次。朴素三层循环几乎零复用：每算一个乘加都回 HBM 重取 A[i,k]/B[k,j]，A 每元素被取 N 次、B 每元素被取 M 次（HBM 流量 ≈ 2·M·N·K 元素）。分块把 A[BM,BK]/B[BK,BN] 小块放进快存，块内乘加反复从快存取、不再回 HBM → A 每元素只取 1 次（访存 M·K）、B 每元素只取 1 次（访存 K·N），复用因子对 A=N、对 B=M。量化即「复用把 HBM 流量从 M·N·K 量级压到 M·K+K·N 量级」。接 decode 数字(M=64,N=11008)：权重 B 朴素要搬 64 遍、分块只搬 1 遍 → 正是打带宽墙的武器；复用↑ → 有效算术强度↑ → 每字节产生更多计算 → 更易打满带宽/逼近算力墙。类比：仓库(HBM,慢) vs 工作台抽屉(快存)；朴素每拧一颗螺丝都跑仓库取料，分块一次搬一大盒到抽屉连拧一整块、料反复用。
    - **HBM 流量直白版（用户仍困惑）**：HBM 流量 = 这次计算**实际从显存(HBM)搬到计算单元(抽屉)的字节数**，类比"从仓库搬了多少货"。关心它因为带宽固定(4090D~1008GB/s)，时间≈流量/带宽——流量越大越慢。朴素流量大的根因：抽屉(寄存器/缓存)太小，装不下整个 A/B，只能装"当前两个数"，算完即丢，下次用只能重取 → 同一 A[i,k] 对 N 个 j 各取一次(共 N 次)、B[k,j] 对 M 个 i 各取一次(共 M 次) → 流量≈2·M·N·K 元素。分块把 A/B 切小块塞进抽屉，块内乘加都在抽屉完成、不回 HBM → 每元素只取 1 次 → 流量≈M·K+K·N。decode 数字(M=64,N=11008)：权重 B 朴素流量 M·K·N、分块 K·N，比值=M=64 倍——即"权重朴素搬 64 遍、分块搬 1 遍"的量化来源。
    - **推导细化（用户追问公式怎么来）+ 诚实边界**：朴素推导干净——固定 A[i,k] 被外层 j 的 N 个值各取一次→取 N 次，A 共 M·K 元素→M·K·N；B[k,j] 被外层 i 的 M 个值各取一次→M·K·N；合计 2·M·N·K。分块 `M·K+K·N` 是**理想上限**：假设 A 整行块[BM,K]与 B 整列块[K,BN]都能完整留缓存被所有 bj/bi 复用(每元素仅取 1 次)，则 A 切块数(M/BM)×(K/BK)×块大小 BM×BK=M·K、B 同理 K·N。但标准三循环 bi,bj,bk 下若缓存装不下整块，A[BM,BK] 子块会在 bj 循环被重复取 N/BN 次→实际流量 M·K·(N/BN)+K·N·(M/BM)，比理想大 N/BN、M/BM 倍。想逼近 M·K+K·N 上限须二级缓存分块(L2/共享内存分层)+合适遍历序——这正是 M3「输出分块+累加器寄存器分块+双缓冲」要解决的问题。结论方向不变：分块远优于朴素(差 N/M/BN/BM 倍)，只是"1 次"是上限而非必然。
    - **澄清「取 1 次」vs「用多次」（用户追问 A_tile 要和很多 B_tile 算，难道要取很多次）**：这是核心混淆点。"取"=从 HBM 搬到快存(寄存器/共享内存)的次数；"用"=在快存里做乘加的次数。**A_tile 从 HBM 只取 1 次，但在快存里被 N/BN 个 B_tile 复用(用 N/BN 次)**——这正是"复用"本身，是分块快的原因，不是多取的理由。理想=HBM─►A_tile─►抽屉─(和 B_tile_0/1/2...依次乘,不回HBM)─►取1次用N/BN次；现实若抽屉装不下A_tile、bj循环把它挤出─►每次重取─►取N/BN次(退化逼近朴素)。所以"取1次"=A_tile能跨bj循环留在缓存/寄存器里。标准三循环 bi,bj,bk 下 A_tile 在 bj 循环被取 N/BN 次(除非缓存保留或换遍历序如 bi,bk,bj 让 A_tile 在 bj 内层复用)；要让 A、B 都只取 1 次需二级缓存分块+好遍历序——正是 M3「输出分块+累加器寄存器分块+双缓冲」的目标。
    - **用户提炼「装得下才能取 1 次」的细化（两级抽屉模型）**：用户直觉正确——"抽屉装得下"是取 1 次的**必要条件**。但需两级看：小抽屉(寄存器/共享内存,~KB~百KB)装 A_tile[BM,BK]+B_tile[BK,BN] 做块内乘加；大抽屉(L2,4090D=72MB)装 A行块[BM,K]、B列块[K,BN] 跨 bj/bi 复用。"取 1 次"跨越哪层循环，取决于数据留在哪级抽屉(HBM→L2 取1次、L2→寄存器取1次)。decode 数字: A[64,2560]bf16≈320KB 能留 L2；B[2560,11008]bf16≈56MB < L2 72MB 容量上也能整体留 L2 → 理论 B 只从 HBM 取1次(硬件缓存不保证锁定,但容量可行)。补充两点:①光装得下不够,遍历序要配合——A_tile 要被 N/BN 个 B_tile 复用就得在 bj 循环内层留着(bi,bk,bj 比 bi,bj,bk 利于 A 复用,但 B 反之),故需权衡/二级分块;②真正逼近理想靠 外层tile进L2+内层tile进寄存器+双缓冲隐藏搬移延迟=M3 目标。
    - **用户理解达成（2026-07-22，M0 收口）**：经 7 轮追问（为什么能分块→写回为何=→怎么切→复用→HBM流量→取1次vs用多次→装得下才能取1次）用户完整建立 decode GEMM 心智模型。逻辑链封口：①矩阵乘加法可分组→可分块算对；②分块把"可加性"转成"数据复用"；③复用=小块从HBM取1次后在快存(寄存器/L2)被用多次；④"取1次"需两级抽屉装得下(寄存器装tile、L2装行/列块;decode A≈320KB、B≈56MB<L2 72MB 容量可行)+遍历序配合;⑤流量从朴素2·M·N·K 压到理想 M·K+K·N(实际介于其间),复用因子对B=M=64倍→这正是带宽游戏的破墙点;⑥写回用=因块间不重叠且K累加已在acc完成。下一步:上GPU机后M1把 tiled_gemm 翻译为 Triton bf16 matmul(先 cos=1.0),再 M2-M4 爬带宽。
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

---

## 能力账本 / 下一步

- **当前阶段**：阶段 3（熟练）——已能独立设计实验、定位根因、对「为什么某优化无效」给出结构性解释（如实验11/12 的「decode 瓶颈=权重访存」甄别）。
- **已掌握**：投机解码原理与 verify 瓶颈；CUDA graph 捕获/replay 收敛 Python 开销；KV 量化数值对齐；调度 watermark 本职（防抖动 vs 防 OOM）；`flash_attn` 跨 batch/seqlen_q 数值敏感性；手写 Triton GEMM 的 grouped swizzle 必须钳位 `group_size_m`（小 M 数值回归必要性）；split-K 补 CTA 的代价（torch 端归约开销）。**＋路径 A·M0：decode GEMM 分块心智模型全链**——矩阵乘两个可加性（输出独立 / K 维可拆）→ 分块算对；分块把「可加性」转成「数据复用」→ 算快；复用 = 小块从 HBM 取 1 次后在快存（寄存器/L2）被用多次；「取 1 次」需两级抽屉装得下（寄存器装 tile、L2 装行/列块；decode B≈56MB < L2 72MB 容量可行）+ 遍历序配合；HBM 流量从朴素 2·M·N·K 压到理想 M·K+K·N（实际介于其间，复用因子对 B = M = 64 倍）= 带宽游戏的破墙点；写回用 `=` 而非 `+=` 的语义根（块间不重叠 + K 累加已在 acc 完成）。已在 Mac 上跑通 `gemm_foundations.py` 并对拍 PASS。
- **还不会 / 待补**：
  - FP8 权重量化（需 Hopper/Blackwell 卡，超出本机范围）。
  - CUTLASS 级 INT8 GEMM（手写 Triton 内核带宽效率不足）。
  - GPU kernel 级 profiling（当前靠 monkey-patch + `cuda.synchronize` 粗粒度计时）。
  - **路径 A 后段（需 GPU 机，macOS 无 GPU，当前只完成 M0 GPU-free 基础）**：M1 翻译 Triton bf16 matmul（先 cos=1.0）→ M2 定位 340 GB/s 瓶颈 → M3 带宽爬坡 340→750 → M4 int8 终验。
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
- **当前线程**：路径 **A（从 0 打 kernel 地基）已规划**（见节点 15）：先懂带宽游戏 → M1 第一个 Triton GEMM（先跑对）→ M2 定位 340 GB/s 瓶颈 → M3 带宽优化爬坡(340→750) → M4 int8 终验。学习序列与机器无关；上 GPU 机后按节点 15 里程碑逐站执行，每站用实验卡记录。
- **机器相关性**：340/750 GB/s 等数字是 4090D 专属；新机 GPU 不同则 autotune/数值会变，但**学习序列 A 与机器无关**。
- **关联**：节点 12 / 13 / 14。

