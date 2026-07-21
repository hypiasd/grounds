---
title: CANN 后端 GGML_OP_SQR 断言放宽（Token2Mel 兼容）
tags: [project, MiniCPM, decision, cann, bugfix]
created: 2026-07-21
updated: 2026-07-21
publish: true
---


# 决策：CANN 后端 GGML_OP_SQR 断言放宽

## 背景
TTS 修好设备上下文后又崩：
栈 `ggml-cann.cpp:1925: GGML_ASSERT(dst->src[1]==nullptr) failed`，
在 `Token2Mel::infer_one_chunk → flowGGUFModelRunner::inference_chunk → ggml_backend_graph_compute`。

## 根因
CANN 后端把 `GGML_OP_SQR` 用 `x*x`（`aclnn_mul`）实现，原代码先
`GGML_ASSERT(dst->src[1]==nullptr)` 再 `dst->src[1]=dst->src[0]`。
Token2Mel 计算图会把 SQR 节点的 `src[1]` 作为 view 复用为非空，导致重复 compute 时断言失败。

## 选项
- A. 保留断言，改为在图构建期规避（改 ggml 图，成本高、易漏）。
- B. 去掉严格断言，直接 `dst->src[1]=dst->src[0];` 保证 x*x 语义。

## 决策
**选 B**。

## 理由
- SQR 定义就是 `x*x`；令 `src[1]=src[0]` 后做 mul 完全正确，且对重复 compute 幂等（多次设成同一值无副作用）。
- 严格 `src[1]==nullptr` 断言假设调用方不填 src[1]，在多模型/图复用下不成立，是脆弱设计。

## 改动位置
`ggml/src/ggml-cann/ggml-cann.cpp` → `case GGML_OP_SQR:` 去掉 `GGML_ASSERT(dst->src[1]==nullptr);`，保留 `dst->src[1]=dst->src[0]; ggml_cann_binary_op<aclnn_mul>(...)`.

## 影响 / 验证
- 修复后 Token2Mel 图可重复 compute，TTS 端到端产出 WAV。
- 关联 pitfall：GGML_OP_SQR 断言在 Token2Mel 图下失败（已修）。
