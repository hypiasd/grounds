---
title: GPU 浮点格式
topic: cuda
tags: [hardware, precision, training, quantization]
summary: GPU 生态中的浮点格式体系：FP32/FP16/BF16/TF32/FP8/FP4。IEEE 754 结构（符号+指数+尾数），指数管范围、尾数管精度。BF16 保留 FP32 的指数范围但砍掉尾数精度，是深度学习训练的甜点格式。TF32 是 Ampere 的内部缝合格式。FP8 分 E4M3（前向）和 E5M2（反向）。FP4（E2M1）为 Blackwell 推理而生。
created: 2026-07-17
updated: 2026-07-17
---


## TL;DR

GPU 生态里出现了多种浮点格式，不是厂商在炫技——每种格式都是**范围（指数）vs 精度（尾数）vs 面积/功耗**的 tradeoff。核心规律：指数位越多、数值范围越大（防溢出/下溢）；尾数位越多、有效数字越多（算得准）；总位宽越小、芯片面积和功耗越低（便宜）。BF16 是训练的甜点（FP32 的范围 + 砍到极致的尾数），FP8/FP4 在 Hopper/Blackwell 把这条规律推到了极致。

## 核心概念

### IEEE 754 浮点数结构

一个浮点数 = 符号位 + 指数位 + 尾数位（mantissa）：

$$\text{value} = (-1)^{\text{sign}} \times 2^{\text{exponent} - \text{bias}} \times 1.\text{mantissa}$$

- **符号位**：0 正 1 负
- **指数位**：决定数值的量级范围。n 位指数 → 范围约 $2^{2^{n-1}}$。越大越不容易溢出/下溢
- **尾数位**：决定有效数字的精细程度。m 位尾数 → 约 $m \times \log_{10}2 \approx m \times 0.301$ 位十进制有效数字

### 格式对比表

| 格式 | 总位宽 | 符号 | 指数 | 尾数 | 范围 | 十进制有效位 | 代数 | 用途 |
|------|--------|------|------|------|------|-------------|------|------|
| FP32 | 32 | 1 | 8 | 23 | ~10⁻³⁸~10³⁸ | ~7 | — | 训练金标准、累加器 |
| TF32 | 19 | 1 | 8 | 10 | ~10⁻³⁸~10³⁸ | ~3 | Ampere | Tensor Core 内部格式 |
| BF16 | 16 | 1 | 8 | 7 | ~10⁻³⁸~10³⁸ | ~2 | Ampere | 训练主力（取代 FP16） |
| FP16 | 16 | 1 | 5 | 10 | ~10⁻⁵~65504 | ~3 | Volta | 推理、老训练方案 |
| FP8 E4M3 | 8 | 1 | 4 | 3 | ~10⁻²~448 | ~1 | Hopper | 前向传播 |
| FP8 E5M2 | 8 | 1 | 5 | 2 | ~10⁻⁵~57344 | ~0.5 | Hopper | 反向传播（梯度范围大） |
| FP4 E2M1 | 4 | 1 | 2 | 1 | ~10⁻¹~6 | ~0.3 | Blackwell | 推理、MoE 训练 |

> TF32 很特殊：它不是存储格式（不在显存中占用 19 位），而是 Ampere Tensor Core 的**内部计算格式**。输入是 FP32，Tensor Core 内部截断尾数到 10 位做乘法，累加仍用 FP32。对用户透明——代码不改，白嫖 Ampere 的 8× 吞吐提升。

### 为什么 BF16 是训练的甜点

FP16 在训练中有个致命问题：5 位指数，范围只到 65504。梯度值经常超过这个范围 → 溢出变 inf，或者太小 → 下溢变 0。需要 loss scaling 技巧来补救。

BF16 解决了这个问题：指数和 FP32 一样是 8 位（范围一样大），只是把尾数从 23 砍到 7。训练实践表明，7 位尾数（~2 位十进制）对梯度更新完全够用——**深度学习的梯度，需要的是 FP32 的量级范围，不是 FP32 的小数精度。**

### FP8：Hopper 的双格式策略

Hopper 引入 FP8，但设计了两种变体：

- **E4M3**（4 位指数 + 3 位尾数）：精度更高，范围较小。用于**前向传播**——激活值范围通常可控。
- **E5M2**（5 位指数 + 2 位尾数）：范围更大，精度更低。用于**反向传播**——梯度值的范围比激活值大得多。

两种格式用在不同阶段，这是 Hopper 比 Ampere 在 FP8 上有 2× 训练吞吐的硬件基础。

### FP4：Blackwell 的下一步

E2M1（2 位指数 + 1 位尾数），只有 4 位。能表示的数值极其有限，但在推理 + 量化感知训练的配合下，很多模型在 FP4 推理时精度损失可控。Blackwell 的 Tensor Core 在 FP4 上有 FP8 的 2× 吞吐。

## 直觉 / 类比

浮点格式的选择就像快递箱子——FP32 是大箱子（装什么都行但占地方），BF16 是刚好够用的中号箱（训练场景里东西没那么精细），FP8/FP4 是超小号箱（装特定形状的东西，得配合量化策略才能用）。核心是找到刚好够用的最小箱子——既不浪费空间，又不压坏货物。

## 常见误区

- **FP16 和 BF16 差不多** → 差很远。FP16 范围小（~65504），BF16 范围和 FP32 一样大（~10³⁸）。训练中 FP16 常溢出需要 loss scaling，BF16 不需要。
- **位宽越小越不准就是不好** → 在特定场景下"刚好够用的不准"是最优解。BF16 在训练中 loss 几乎不降但速度快一倍、省一半显存——这是工程上完美的 tradeoff。
- **TF32 是一种新的存储格式** → TF32 不存在于显存中。它是 Ampere Tensor Core 内部把 FP32 输入的尾数截断到 10 位的计算结果格式。对用户完全透明。
- **FP8 就是一种格式** → 是两种。E4M3（前向）和 E5M2（反向）精度和范围各有所长，分开用。

## 关联

- [GPU 执行模型](gpu-execution-model.md) — SM 内部的 Tensor Core 是这些浮点格式的硬件消费者；混合精度原理详见第四节
- [Triton](triton.md) — Triton 的 `tl.float8` 等类型直接映射到这些格式
- [CUTLASS](cutlass.md) — CUTLASS 的模板参数显式指定 MMA 指令的输入/输出精度

## 面试常见问题

- **Q**: FP16 和 BF16 的区别是什么？训练时怎么选？
  **A**: 都是 16 位浮点，但位分配策略不同。FP16 是 1+5+10（符号+指数+尾数），范围只到 65504，训练时梯度容易溢出需要 loss scaling；BF16 是 1+8+7，指数位和 FP32 相同，范围和 FP32 一样大（~10³⁸），训练更稳定通常不需要 loss scaling，代价是尾数位更少（~2 位十进制有效数字 vs FP16 的 ~3 位）。选择：硬件支持 BF16（A100/RTX 30 系+）则优先 BF16；V100/RTX 20 系只能用 FP16 + GradScaler。（来源：菜鸟教程 • runoob.com / Smarter's blog • smarter.xin）
- **Q**: TF32 是什么？为什么说它是"免费的性能提升"？
  **A**: TF32 是 Ampere 架构 Tensor Core 引入的内部计算格式（不是存储格式）。输入是标准 FP32，Tensor Core 内部把尾数从 23 位截断到 10 位做乘法，累加仍用 FP32。结果：精度介于 FP16 和 FP32 之间，但 Tensor Core 吞吐是 FP32 的 8 倍。对用户完全透明——代码不改，torch.matmul 自动受益。在 PyTorch 中通过 torch.backends.cuda.matmul.allow_tf32 = True 开启。（来源：NVIDIA Ampere 白皮书 • Smarter's blog • smarter.xin）
- **Q**: FP16 为什么需要 loss scaling？BF16 为什么不需要？
  **A**: FP16 的 5 位指数 → 可表示的最小规格化正数约 6×10⁻⁸，训练中很多小梯度低于这个值 → underflow 变 0 → 梯度消失、参数不更新。loss scaling 先把 loss 乘一个大数（如 1024），反向传播时梯度同比放大到 FP16 可表示范围，更新前再 unscale 回去。BF16 的 8 位指数和 FP32 相同 → 最小正数约 9×10⁻⁴¹，小梯度不会下溢 → 不需要 loss scaling。（来源：菜鸟教程 • runoob.com / PyTorch AMP 文档）
- **Q**: FP8 有两种变体 E4M3 和 E5M2，为什么需要两种？
  **A**: 两种格式解决不同阶段的精度需求。E4M3（4 指数+3 尾数）精度更高、范围较小，适合前向传播——激活值的范围通常可控。E5M2（5 指数+2 尾数）范围更大、精度更低，适合反向传播——梯度值的动态范围比激活值大得多，需要更大的指数位防溢出。这是 Hopper 架构的硬件设计决策——为不同计算阶段提供最优的精度/范围组合。（来源：NVIDIA Hopper 白皮书 • mianshidashi.cn）
- **Q**: 混合精度训练中，哪些算子必须保持 FP32？为什么？
  **A**: 数值敏感算子必须保持 FP32 或 FP32 累加：（1）LayerNorm/RMSNorm——规约操作涉及方差计算，低精度容易放大误差；（2）Softmax——涉及 exp 和规约，FP16 下容易溢出；（3）Loss 计算——直接影响梯度质量；（4）梯度累加——大量小值的累加，低精度尾数不够用；（5）Adam 的一阶/二阶动量——需要 FP32 保存优化器状态。PyTorch 的 autocast 已内置这些规则——matmul/conv 用低精度，norm/softmax/loss 自动回退 FP32。（来源：阿里巴巴 算法面经 • 面试大师 • mianshidashi.cn）
- **Q**: 为什么低精度不仅能加速计算，还能降低显存？
  **A**: 两方面收益。计算侧：Tensor Core 的低精度矩阵乘吞吐是 FP32 的数倍（如 A100 上 FP16/BF16 矩阵乘吞吐 312 TFLOPS vs FP32 的 156 TFLOPS）。显存侧：参数、梯度、激活值从 FP32（4 bytes）换成 FP16/BF16（2 bytes）后元素字节数减半——activation 尤其受益，随 batch size × 序列长度 × 层数线性增长。显存降低后可放大 batch size 或序列长度、减少 activation checkpointing。但不会严格减半——optimizer state、master weights、KV cache 等仍需高精度存储。（来源：菜鸟教程 • runoob.com / TensorFlow 混合精度指南）
- **Q**: autocast 和手动 .half() 有什么区别？为什么推荐 autocast？
  **A**: model.half() 把整个模型的所有参数和计算都转为 FP16 → LayerNorm、Softmax 等数值敏感算子被强制低精度 → 容易导致 NaN/INF、loss 发散。torch.autocast 按官方规则为每类算子自动选择精度——matmul/conv 用低精度加速，norm/softmax/loss 保留 FP32 保证数值稳定性。正确用法是模型保持 FP32 权重，在 forward 外套 autocast，不要预先 .half()。（来源：Smarter's blog • smarter.xin / PyTorch AMP 官方文档）
