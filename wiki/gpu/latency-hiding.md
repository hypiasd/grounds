---
title: 延迟隐藏与占用率
topic: gpu
tags: [gpu, latency-hiding, occupancy, bandwidth, memory-latency]
summary: HBM 带宽高但单次访存延迟几百 cycle；延迟隐藏=用足够多并发 warp 让计算 overlap 掉访存等待，使 HBM 流水线不空转。占用率=SM 上驻留 warp 数占比，决定能藏多少延迟，正是 roofline 里「block size 是占用率杠杆」的底层机制。类比：一群人接力用水管，水管始终有水在流才拉满吞吐。
created: 2026-07-23
updated: 2026-07-23
---

## TL;DR

HBM **带宽**高（T4 ~300 GB/s）但**单次访存延迟**要几百~上千 cycle——两者解耦。一个 warp 发一条 load 后要苦等数据，这段时间若没事做就空转、HBM 管子粗却没一直流水，于是**带宽受限的 kernel 也可能远低于峰值带宽**。延迟隐藏 = 靠大量并发的 active warp（调度器在等内存时切到别的 warp 算）把访存等待 overlap 掉；并发在飞的内存请求够多，HBM 就被喂满。**占用率（occupancy）= 一个 SM 上驻留 warp 数 / 上限**，决定能藏多少延迟，正是 roofline 里「block size 是占用率杠杆」的底层机制。

## 核心概念

### 1. 带宽与延迟是两个独立维度

- **带宽** = 管子多粗：每秒能搬多少字节（HBM 高，T4 ~300 GB/s、4090D ~1008 GB/s）。
- **延迟** = 拧开水龙头到水来要等多久：一次 global memory 访存要几百~上千 cycle。
- 高带宽 **≠** 低延迟。HBM 又粗又慢（相对算得快而言）。GPU 的设计哲学是「不赌单次快，只赌整体管子不空」。

### 2. 为什么「带宽受限」也可能跑不满带宽

朴素账：`时间 ≈ 流量 / 带宽`。但这只在**延迟被完全藏住、带宽跑满**时成立。

一个 warp 发一条 `tl.load`，要等几百 cycle 数据才回来。若这段时间这个 warp 没别的事做 → **空等** → HBM 流水线出现空档 → 实测 `GB/s << 峰值`。所以「带宽受限」只说明瓶颈在访存，不保证已经跑满访存带宽。

### 3. 延迟隐藏机制（warp 切换）

- 每个 SM 上驻留很多 warp；当某 warp 在等内存（被 scoreboard 卡住），**调度器立刻切到另一个 ready 的 warp** 做计算。
- 只要「在飞的内存请求数」足够多，HBM 的多个 channel / 事务一直被占用 → 带宽拉满。
- 本质：**以吞吐换延迟**——不在乎单次访存多慢，只在乎整体管子不空。

### 4. 占用率 occupancy

- 定义：`一个 SM 上实际驻留的 warp 数 / 该 SM 最大可驻留 warp 数`。
- 它决定能掩盖多少延迟（并发内存请求的上限）。
- 受三样东西约束：**block 大小**、**每线程 register 数**、**每 block shared mem**。
- 这正解释了 roofline 里「block size 是占用率杠杆」：
  - block 太小 → 每 SM warp 少 → 并发请求不够 → 藏不住延迟 → 带宽跑不满。
  - block 太大 → register / SMEM 撑爆 → 可驻留 warp 反而少 → occupancy 掉 → 延迟更藏不住。
  - **存在甜点**，不是越大越好。

### 5. 与 M2 的连接：定位瓶颈的两类根因

M2 测 `GB/s` 对照屋顶。若实测远低峰值，先分两类根因（不要一律当成「kernel 写错」）：

- **(a) 延迟没藏住（并发请求不够）**：调 `block size` / 增加并发 warp / double buffer（让搬和算 overlap）。
- **(b) 流量真算多了（复用差，HBM 该搬的没压下去）**：改切法、提升 tile 复用（见 HBM 流量与数据复用）。

**区分线索**：看 occupancy——若 occupancy 高仍慢 → 是 (b)；若 occupancy 低 → 是 (a)。Triton 用 `num_warps`（每程序 warp 数）和 `num_stages`（double buffer 级数）直接暴露这两个旋钮，正是为延迟隐藏服务。

### 6. 延迟隐藏旋钮的生效边界（= roofline 拐点）

`num_stages`（double buffer / 软件流水）是延迟隐藏主旋钮、`num_warps` 次之，二者都靠喂满在飞 HBM 请求来藏延迟。但旋钮**只在 `AI < AI*` 的带宽受限形状生效**：更深预取 → 更多在途 load → HBM 更满。一旦形状越过 roofline 拐点（`AI > AI*`、算力受限），被算力天花板锁死，藏延迟救不了带宽——此时 GB/s 低是 compute-bound 的标志，不是 kernel 差。

- **单变量证据**（固定 BLOCK/num_warps，只扫 num_stages）：带宽受限形状（M=1, AI≈2）stages 2→4 带宽 +87%；算力受限形状（M≥256, AI≥455）各 stages 下 GB/s 恒定。
- 这是 roofline「划分优化对象」的操作化证明：延迟隐藏的优化精力要放在 `AI < AI*` 的形状；越过拐点，旋钮失灵。

### 7. SMEM 预算勿靠公式臆测

直觉上 num_stages 缓冲占用 ≈ `(BM·BK + BK·BN)·elem_bytes × num_stages`，会以为 stages 多了就撞 shared mem 上限。实测会**严重高估**：Triton 的 dot 操作数常驻**寄存器**而非全程 SMEM、或用更紧凑 staging 布局，故同款配置 `s2~s5` 全部编译跑通、cos=1.0。

- **正确做法**：SMEM 预算**实测**——编译跑通 + 用 occupancy / SMEM 占用工具确认，而非手算 naive 上界。
- **对照**：shared mem 墙**真实存在**，但不是被 stages 触发，而是被**块太大**触发（如 128×128 fp32 双 tile = 128KB > T4 64KB → `OutOfResources`）。块大小与 stages 是两个独立约束，别混为一谈。

## 直觉 / 类比

**水管接力模型**：水龙头出水快（带宽高），但拧开后要等 2 秒才来水（延迟）。

- **一个人接水**：拧开 → 干等 2 秒 → 接满 → 再拧下一个。水管大部分时间在空转（= 延迟没藏住的 kernel，带宽跑不满）。
- **一群人排队**：A 拧开在等水时，B 已经接满、C 在拧……水管始终有水在流（= 高 occupancy 藏住延迟，带宽拉满）。

warp 就是那群人，SM 调度器是喊「下一个」的工头。Occupancy 就是「同时排队的人数够不够多，让水管一刻不停」。

## 常见误区

- **误区：带宽受限 = 一定跑满带宽。** 错。还要藏住延迟；并发请求不够，管子粗也空转。
- **误区：block 越大越好。** 太大 → register / SMEM 撑爆 → 可驻留 warp 反而少 → occupancy 掉 → 延迟更藏不住。甜点存在。
- **误区：耗时永远 = 流量 / 带宽。** 只在延迟完全藏住、带宽跑满时成立；藏不住时 `实际时间 > 流量 / 带宽`。
- **误区：延迟隐藏只和 bandwidth-bound kernel 有关。** 算力受限 kernel 同样要藏延迟才能爬到算力屋顶，只是最终瓶颈在算力不在带宽。

## 面试常见问题

- **Q**：为什么 GEMM kernel 实测带宽远低于 HBM 峰值？

  **A**：大概率是延迟没藏住——并发在飞的内存请求数不够，HBM 流水线有空档。先确认 occupancy 是否够高；不够就调 `block size` / `num_warps`、增加并发 warp，或 double buffer 让搬和算 overlap。若 occupancy 已经很高仍慢，则是流量没压下去（复用差），该改切法而非调并发。

- **Q**：什么是 occupancy，为什么重要？

  **A**：SM 上同时驻留 warp 数占上限的比例，决定能掩盖多少内存延迟；太低则 HBM 流水线有空档、带宽跑不满。但过高也可能因 register / SMEM 压力反而降速，要在「足够藏延迟」和「每线程资源」之间找甜点。

## 关联

- [HBM 流量与数据复用](hbm-traffic.md) — 延迟藏住后「时间≈流量/带宽」才成立；流量是分子、延迟隐藏决定分母公式何时生效
- [Roofline 模型与算术强度](roofline.md) — 「block size 是占用率杠杆」的出处；屋顶给出带宽上限，本篇解释为何到不了上限
- [分块 GEMM 的原理与切法](../gemm/tiled-gemm.md) — tiling 提升复用压流量，与延迟隐藏是两条独立杠杆（一个减分子、一个保分母公式成立）
- [Triton matmul 拆解](../cuda/triton-matmul.md) — `num_warps` / `num_stages` 就是暴露延迟隐藏旋钮
- [Triton 张量核限制](../cuda/triton-tensor-core-limitations.md) — TC 是另一维加速，与本篇 stages/warps 延迟隐藏正交；M4/M5 翻车证明「换 dtype 不自动加速」
- 项目实践：vllm-plus 路径 A·M2（[runbook](../project_logs/vllm-plus/runbook.md) 节点 18）— 实测 GB/s 对照 T4 屋顶时据此区分两类根因
