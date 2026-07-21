---
title: MiniCPM 项目入口（Ascend 910C 部署）
tags: [project, MiniCPM]
created: 2026-07-21
updated: 2026-07-21
publish: true
---

# MiniCPM · 项目入口

- **目标**：按《MiniCPM-o 4.5 昇腾 910C 部署上手指南》完成全部部署与测试（环境 → 权重 → 源码 → 编译 → 起服务 → API 测试 → 第 8 节验证）。
- **主线记录（决策 / 实施 / 问题 / 解决 时间线）**：[runbook.md](runbook.md)
- **技术栈**：2× Ascend 910C · openEuler 24.03 · CANN 9.1.0-beta.3 · llama.cpp-omni（GGML_CANN 后端）
- **现状**：✅ 环境 / 权重 / 源码 / 编译 / 起服务 / API 测试 / 指南第 8 节全部跑通（详见 runbook）
- **外部仓库**：源码 `https://github.com/tc-mb/llama.cpp-omni.git`（经 gh-proxy.com 代理）；权重 ModelScope `OpenBMB/MiniCPM-o-4_5-gguf`
