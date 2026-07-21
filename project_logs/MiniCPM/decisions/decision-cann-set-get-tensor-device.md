---
title: CANN 后端 set/get_tensor_async 补设备上下文（根因修复）
tags: [project, MiniCPM, decision, cann, bugfix]
created: 2026-07-21
updated: 2026-07-21
---

# 决策：CANN 后端 set/get_tensor_async 补设备上下文

## 背景
指南第 8 节开启 TTS（`use_tts_template=true`）后服务崩溃：
栈 `ggml_backend_cann_set_tensor_async → aclrtMemcpyAsync ... context is a null pointer / current device: -1`，
发生在 **Token2Wav 的 t2w 线程**。

## 选项
- A. 在这两个回调里 `aclrtGetDevice` 判 -1 则跳过（同前期 `cann_free` 的防御补丁思路）。
- B. 在入口补 `ggml_cann_set_device(cann_ctx->device);`（与 `graph_compute`/`synchronize`/`buffer` 等其它回调一致）。

## 决策
**选 B（根因修复）**。

## 理由
- CANN 设备上下文是**线程局部**的；其它所有会触碰 device 的 CANN 回调入口都已 `ggml_cann_set_device(...)`。唯独 `set_tensor_async` / `get_tensor_async` 漏了。
- 主线程推理前已被 set 过设备故不触发；**独立 T2W 线程从未 set 过设备**，于是 `current device=-1`、空上下文、`rtMemcpyAsync` 崩。
- 防御补丁（A）只掩盖，根因修复（B）让多线程后端（T2W）正确工作，且与既有代码风格一致。

## 改动位置
`ggml/src/ggml-cann/ggml-cann.cpp`
- `ggml_backend_cann_set_tensor_async`：入口加 `ggml_cann_set_device(cann_ctx->device);`
- `ggml_backend_cann_get_tensor_async`：同上。

## 影响 / 验证
- 修复后 TTS 不再崩溃，Token2Wav 在 CANN 上跑通并产出合法 WAV。
- 关联 pitfall：CANN 后端 set/get_tensor_async 缺设备上下文（已修，根因）。
