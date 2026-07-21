---
title: 决策索引
tags: [project, MiniCPM, decision]
created: 2026-07-21
updated: 2026-07-21
---

# 决策索引

| # | 主题 | 链接 | 状态 |
|---|------|------|------|
| 1 | CANN 版本 beta.3 vs 指南 beta.1 | [decision-cann-version](decisions/decision-cann-version.md) | 已定：用 beta.3 |
| 2 | CANN 后端 free 空设备上下文崩溃 | [decision-ggml-cann-free-guard](decisions/decision-ggml-cann-free-guard.md) | 已定：加空上下文守卫（临时绕过视觉缺失） |
| 3 | CANN 后端 set/get_tensor_async 缺设备上下文 | [decision-cann-set-get-tensor-device](decisions/decision-cann-set-get-tensor-device.md) | 已定：入口补 `ggml_cann_set_device`（根因修复） |
| 4 | CANN 后端 GGML_OP_SQR 断言在 Token2Mel 下失败 | [decision-cann-sqr-assert](decisions/decision-cann-sqr-assert.md) | 已定：去掉严格断言，直接 x*x |
