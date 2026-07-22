---
title: 权重量化内核效率
topic: cuda
tags: [quantization, kernel, inference, marlin, gemm]
summary: 权重量化能否提速，取决于「省下的字节红利」能否覆盖「反量化/内核税」。W8 省 2× 不够（exp12 手写 Triton 48~56µs 仍慢于 cuBLAS bf16 40µs）；INT4 省 4× + 生产级内核（Marlin）才够。瓶颈是内核质量，不是访存次数。
created: 2026-07-22
updated: 2026-07-22
sources:
  - ../../project_logs/vllm-plus/runbook.md
---

## TL;DR

权重量化要真正提速，必须让「量化省下的权重字节红利」**大于**「反量化 + GEMM 内核带来的额外开销（内核税）」。在本项目实测（实验12）中：W8 只省 2× 字节，被手写 Triton 内核的 inefficiency 完全吃光，反而比 bf16 慢 1.35×；而 INT4（Marlin，W4A16）省 4× 字节 + 生产级内核效率，才足以净赚。关键修正：**瓶颈是内核质量，不是访存次数**——exp12 的 W8A16 已是「一次访存 + 寄存器反量化」，仍慢。

## 核心概念

### 比特组合与内核路径

权重量化的「比特组合」指权重/激活各自的比特数，决定走哪条 GEMM 内核路径：

| 组合 | 权重 | 激活 | 内核路径 | 权重访存缩减 | 备注 |
|---|---|---|---|---|---|
| **W4A16 (Marlin)** | INT4 | fp16 | fp16 TC + 融合 dequant | 1/4 | weight-only，本项目推荐 |
| W8A16 | INT8 | fp16 | fp16 TC + 寄存器反量化 | 1/2 | exp12 实测慢 1.2~1.3× |
| W8A8 | INT8 | INT8 | 整数 TC (IMMA) | 1/2 | exp12 实测最慢 1.4× |
| W4A4 | INT4 | INT4 | 整数 TC | 1/4 | 激活量化，精度风险大、收益小 |

- **weight-only（W4A16/W8A16）**：只压权重，激活保持 fp16。激活在 decode 时每步仅 1 列、字节极小，压它收益微、且需在线量化（round/clip 开销 + outlier 精度风险），故 weight-only 更稳。
- **Marlin = W4A16，不是 W4A4**：它在 fp16 Tensor Core 上算，把 INT4 权重「解包 + 乘 fp16 scale」融进寄存器预处理，激活 fp16 直接喂 TC。纯整数 W4A4 路径要求激活也量化、且 per-group 的 fp16 scale 无法在整数 TC 内施加，工程更复杂且更不稳。

### 字节红利 vs 内核税（形式化）

decode 单 token（$N{=}1$）时，线性层有效访存近似：

$$
\text{访存} = |W|_{\text{fmt}} + |X|_{\text{fp16}}, \quad |X| \ll |W|
$$

- bf16：$|W|_{\text{fp16}}$
- W8：$\tfrac12 |W|_{\text{fp16}}$（省 2×）
- INT4：$\tfrac14 |W|_{\text{fp16}}$（省 4×）

理论加速比 $\approx \frac{\text{字节红利}}{\text{内核效率因子}}$。若手写内核效率因子 $>1$（比 cuBLAS bf16 慢），则：

- W8：$\frac{2}{1.25} \approx 1.6\times$ 理论，但实测内核税更高 → **净亏**；
- INT4：$\frac{4}{1.1\sim1.2} \approx 3\sim 3.5\times$ → **净赚**（Marlin 实测）。

### exp12 实测（项目实证，深表见 runbook 节点 7）

decode 形状 `M=64, K=2560, N=11008` 的各 GEMM 路径耗时：

| GEMM 路径 | 耗时 (µs) | 备注 |
|---|---|---|
| cuBLAS bf16 `F.linear` | **40.4** | 最快（带宽受限天花板） |
| W8A16（int8 权重 + 寄存器反量化 + bf16 MMA） | 48~52 | 慢 1.2~1.3× |
| W8A8（真·INT8 张量核，Triton） | 55.6 | 慢 1.4× |
| `torch._int_mm`（cuBLAS int8） | 464.6 | 慢 11.5×，不可用 |

端到端：`WQUANT=int8` **601 tok/s** vs bf16 **812 tok/s** → 慢 **1.35×**。

> **关键修正**：上轮曾误判 exp12 慢是因为「dequant 回 fp16 落 HBM 读两次」。实测记录明确是「**寄存器反量化**」（一次访存、不落 HBM）。即「一次访存 + 融合反量化」的 W8A16 已做到，仍慢——根因是**手写 Triton 内核带宽效率 < cuBLAS bf16**，不是访存次数。

## 直觉 / 类比

像**搬货**：bf16 是大箱子，int8 是半箱，int4 是 1/4 箱。量化「省运费」靠装更小的箱子。但仓库门口要「拆箱」（反量化）才能上架，拆箱要工人（内核）。

- 若工人手脚慢（手写 Triton 内核税高），装半箱（W8，省 2×）省下的运费被工人工资吃光，反而亏本 → exp12 的 W8 困境。
- Marlin 是「专业搬运队（生产级内核，逼近峰值带宽）+ 最小箱子（int4，省 4×）」双保险，才稳赚 → 本项目剩余最高天花板杠杆。

## 常见误区

- **误区 1：量化变慢是因为「权重被读两次」**。错。exp12 的 W8A16 已是寄存器反量化、权重只读一次（int8），仍慢于 cuBLAS。瓶颈在内核效率，不在访存次数。
- **误区 2：Marlin 是 W4A4**。错。Marlin 是 **W4A16**（weight-only），激活保持 fp16，不在整数 TC 上算。
- **误区 3：只要「只读一次权重」就能提速**。错。exp12 亲手证伪：W8A16（一次访存 + 融合）和 W8A8（纯整数一次访存）都慢于 cuBLAS bf16。单纯「读一次」不够，内核质量才是关键。
- **误区 4：权重量化和 KV 量化提速机制相同**。不同。INT8 KV 只减半「被 GQA 削小的注意力块」，不动 decode 吞吐天花板；权重量化减半/减四「占主体的 4B matmul 权重」，才动天花板。

## 面试常见问题

- **Q**: 为什么权重量化在某些卡/某些实现上反而比 bf16 慢？

  **A**: decode 是 HBM 带宽受限，cuBLAS bf16 已把权重读到接近峰值带宽。量化省下的字节是「红利」，但反量化 + GEMM 内核有「内核税」。若手写内核效率比 cuBLAS 低（如本项目 Triton 48~56µs vs 40µs），W8 省的 2× 红利被税吃光甚至净亏。只有省 4× 的 INT4 + 生产级内核（Marlin）才足够覆盖内核税。

- **Q**: W4A16 和 W4A4 有什么区别？为什么 Marlin 选前者？

  **A**: W4A16 只压权重、激活保 fp16；W4A4 连激活也压成 INT4。激活在 decode 占比极小、且分布宽/outlier 多，量化它收益小、精度风险大。Marlin 在 fp16 TC 上算，把 INT4 解包+乘 fp16 scale 融进寄存器，绕开纯整数路径的 scale 难题，故选 W4A16。

- **Q**: 既然 Tensor Core 原生支持 INT4/INT8 MMA，为什么不直接用整数 TC 做权重量化？

  **A**: 纯整数 TC 要求激活也是低比特（又得量化激活），且 per-group 的 fp16 scale 无法在整数 TC 内施加。Marlin 故意用 fp16 TC，把反量化融进寄存器预处理，复用 fp16 TC 高吞吐，同时避开整数路径的 scale 难题。

## 关联

- [CUTLASS](cutlass.md) — INT8 GEMM 的生产级替代内核（runbook 节点 7 指出的 W8 出路之一），比手写 Triton 更接近峰值带宽
- [Triton](triton.md) — exp12 用手写 Triton `int8_gemm`，内核效率不如 cuBLAS bf16，是本误区「内核税」的实证来源
- [Float Formats](float-formats.md) — INT4 / INT8 / bf16 等数值格式基础，理解「字节红利」的前提
- 项目实证：[vllm-plus 运行手册 · 节点 7（实验12）与节点 9（INT4/Marlin 方向）](../../project_logs/vllm-plus/runbook.md) — exp12 实测数据与「INT4 + 生产内核才是出路」的决策推导
