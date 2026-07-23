---
title: Triton 张量核限制：tl.dot 不会自动吃张量核
topic: cuda
tags: [triton, gpu, tensor-core, mma, gemm, kernel]
summary: 在 Triton 里 `tl.dot(fp16/int8)` 并不自动用到张量核——红利必须由编译器正确 lowering 成 `mma.sync` 才兑现。Triton 3.6 + Turing(sm_75) 下 fp16 dot 退回 CUDA core、int8 dot 编译崩溃，根因是上游 v2.x 起把 MMA 路径 gated 到 sm80+。如何确认 TC 是否生效，以及「换个 dtype 不会自动加速」的通用结论。
created: 2026-07-23
updated: 2026-07-23
---

## TL;DR

直觉「用 `tl.dot(fp16)` / `tl.dot(int8)` 写 GEMM，编译器自动派发张量核」是**错的**。张量核红利不是数据类型给的，而是**编译器把 `tl.dot` 正确 lowering 成 `mma.sync` 指令**才兑现。若编译器没做这一步（版本/架构不支持），fp16 会静默退回 CUDA core、int8 直接编译失败——kernel 写法再对也没用。验证是否吃到 TC 要看 PTX 里有没有 `mma`，不是看 dtype。

## 核心概念

### 1. 张量核红利来自 lowering，不来自 dtype

- `tl.dot` 是块级矩阵乘的**抽象**；它落到什么硬件指令，由 Triton 后端（NV 后端）决定。
- 只有后端把 `tl.dot` 的 `dot_op` 布局编译成 **MMA 编码**（`#ttg.mma` / `mma.sync`），才会真正走张量核。
- 若后端不支持该 dtype+架构组合，它会退化：
  - fp16 → 操作数被提升为 f32、用 `#blocked` 布局走 **CUDA core**（没有 MMA 加速，甚至比 fp32 还慢）。
  - int8 → 更低级 bug：MMA lowering 把整数操作数误当浮点（`arith.extf` on `i8`），**编译期直接崩溃**（`TritonGPUAccelerateMatmul` pass 失败）。

### 2. 实锤案例：Triton 3.6 + Turing (sm_75, T4)

- **fp16**：PTX dump **无 `mma` 指令**；`tl.dot` 进入共享内存 staging 时操作数被提升为 f32（`tensor<...xf32, #ttg.dot_op<...>>`，`inputPrecision=tf32`），布局 `#blocked` 非 MMA。
- **int8**：编译报错 `error: 'arith.extf' op operand #0 must be floating-point-like, but got 'tensor<128x64xi8, #ttg.dot_op<...>>'` → `PassManager::run failed`。`int8` 的 `tl.dot` 在此根本编译不过。

### 3. 根因：上游把 MMA 路径 gated 到 sm80+

不是 kernel 写法问题，是**编译器有意的设计取舍**。在 Triton 本机后端源码（`triton/backends/nvidia/compiler.py` 的 `make_ttgir`）可实证：

- `emuTF32 = (capability // 10 >= 8)` —— TF32 模拟只给 sm80+；
- `add_optimize_dot_operands(pm, capability >= 80)` —— dot 操作数优化按 sm80+ 开关，sm_75 传 `False`；
- `if capability // 10 in [8, 9]:` 才分配 MMA 编码与软件流水；sm_75 走 `else` 分支，dot 操作数保持 `#blocked` 非 MMA 布局 → 无 `mma.sync`。

上游在 **v2.x 之后** 把张量核 MMA 路径限定到 **sm80+（Ampere 及以后）**，Turing(sm_75, T4) 被排除。网络侧佐证：Triton issue #9349（Turing int8 dot 编译失败）、issue #1809（Turing int8 dot 不支持）、`triton-turing` fork README 明确「Upstream dropped Turing support after v2.x」。

### 4. 怎么确认 TC 是否真的生效（方法论）

不要靠 dtype 猜，要查编译产物：

```python
# 编译后 dump 汇编 / 中间表示
compiled = matmul_kernel  # triton 编译出的函数
asm = compiled.asm  # dict
print(asm['ptx'])    # 搜 "mma" —— 有 mma.sync 才真走张量核
print(asm['ttgir'])  # 看 dot_op 的布局是否为 MMA 编码（非 #blocked）
```

- **fp16 退回 CUDA core 的判据**：PTX 无 `mma`、ttgir 里 dot 操作数是 `xf32` + `#blocked`。
- **int8 编译崩溃的判据**：编译期 `arith.extf on i8` / `TritonGPUAccelerateMatmul` 失败。
- 对照：同一组形状下 `torch.matmul`（cuBLAS）能跑到张量核峰值 → 证明**硬件 TC 正常**，只是 Triton 没把红利交出来。

### 5. 一般结论：换 dtype ≠ 自动加速

路径 A 的 M3→M5 把一条硬道理串起来了：

- **数据类型 / 张量核红利不是「换个 dtype 就自动加速」**。它要求编译器正确 lowering 成 `mma.sync`，且即便库层做对了，实得吞吐也受 shape / layout / packing 强约束。
- 例：`torch._int_mm`（cuBLAS IGEMM，已走 int8 TC）在 T4 上仍只达 **4.5~17.4 TOPS**，远低于 T4 int8 峰值 ~130 TOPS（3~13%）——即便走对库，shape 没榨干 TC 也远低峰值。
- 推论：手写 / 库内核的**峰值效率由 lowering + 形状适配共同决定**，不是「数据精度一换就起飞」。这正是「手写 int8 慢于 cuBLAS bf16 → 须 INT4(Marlin) 级生产内核」从现象升级为机制的根。

## 直觉 / 类比

张量核像工厂里的专用重型机床（mma），`tl.dot` 是你写的「把这两块料焊起来」的工单。你写 `fp16` 工单 ≠ 自动派给重型机床——得有调度系统（编译器 lowering）把工单翻译成机床指令。调度系统不支持这台机床（sm_75 被上游弃用），工单就被降级成手工钳工（CUDA core），甚至因格式不对直接被打回（int8 编译崩溃）。机床本身没问题（torch/cuBLAS 能用），是调度系统没接上。

## 常见误区

- **误区：`tl.dot(fp16/int8)` 自动吃张量核。** 错——须编译器 lowering 成 `mma.sync`；不支持时 fp16 静默退回 CUDA core，int8 直接编译失败。
- **误区：硬件有 TC 就一定能用到。** 错——工具链（Triton 版本 × 架构）决定能否生成 `mma`；T4 硬件有 fp16/int8 TC，但 Triton 3.6 不为 sm_75 生成。
- **误区：int8 比 fp32 峰值高 ~16×，所以一定快 16×。** 错——实得吞吐受 shape/layout 强烈制约，即便走对库也常只到峰值 3~13%。
- **误区：编译过 = 吃到 TC。** 错——fp16 编译过但退回 CUDA core，根本没走 TC；要看 PTX 有没有 `mma`。

## 面试常见问题

- **Q**：为什么我写 `tl.dot(fp16)` 没比 fp32 快反而更慢？

  **A**：很可能编译器没把 `tl.dot` lowering 成 `mma.sync`，fp16 被提升回 f32 走 CUDA core（还多了转换开销）。dump PTX 搜 `mma` 验证；若没有，说明当前 Triton 版本/架构不支持该组合，需换 cuBLAS/CUTLASS、或换支持该架构生成 mma 的 Triton 版本（Turing 需 ≤ ~2.1 或 `triton-turing` fork）。

- **Q**：怎么判断一个 GEMM kernel 真用上了张量核？

  **A**：查编译产物——NV 后端 dump PTX 看是否有 `mma.sync` 指令，ttgir 看 `dot_op` 是否为 MMA 编码；光看输入 dtype 不算数。同时用 `torch.matmul`（cuBLAS）做对照，确认硬件 TC 本身可用。

## 关联

- [延迟隐藏与占用率](../../gpu/latency-hiding.md) — TC 是另一维加速，与 stages/warps 延迟隐藏正交
- [Roofline 模型与算术强度](../../gpu/roofline.md) — fp16/int8 张量核把算力天花板抬得更高，compute-bound 形状拐点右移
- [Triton matmul 拆解](triton-matmul.md) — `tl.dot` 第三参才是累加器；本篇讲 `tl.dot` 落到哪条硬件路径
- [权重量化内核效率](weight-quantization-kernel-efficiency.md) — 「手写内核峰值依赖 lowering」的同一结论在权重量化上的体现
- 项目实证：vllm-plus 路径 A·M4/M5/根因（`project_logs/vllm-plus/runbook.md` 节点 21/22/23）— Triton 3.6+sm_75 下 fp16 退回 CUDA core、int8 编译崩溃，根因定位为上游关闭 sm_75 MMA 路径
