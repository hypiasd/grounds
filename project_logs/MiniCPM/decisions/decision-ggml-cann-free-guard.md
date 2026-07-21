---
title: 决策：CANN 后端 free 空设备上下文守卫
tags: [project, MiniCPM, decision]
created: 2026-07-21
updated: 2026-07-21
---

# 决策：CANN 后端 free 空设备上下文守卫

- **问题（what & why）**：HTTP 旧版 API 的 `omni_init` 触发服务崩溃，栈显示 `ggml_backend_cann_free` → `aclrtSynchronizeDevice()` 报 `context is a null pointer / current device: -1` → `GGML_ABORT`。根因：`vision_backend` 默认 `metal`（Apple），昇腾上视觉 CANN 后端上下文为空，清理时同步空设备触发 abort。
- **候选方案**：
  - 方案 A（采用）：在 `ggml_backend_cann_free` 加守卫——`aclrtGetDevice` 拿到无效设备（-1）时跳过 `aclrtSynchronizeDevice/ResetDevice`。这是正确行为（无设备本就不该同步），最小防御补丁，不动推理主链路。
  - 方案 B：实现 vision_backend 的 CANN 真正路径（让视觉可用）。成本高、超出本次测试范围。
  - 方案 C：禁用 HTTP 旧版 API、只用 WS。会丢掉指南 6.4 测试覆盖。
- **推荐 + 理由**：选 A。它让本就不需要视觉的音频/文本测试在 HTTP 路径也能跑通且不崩服务；真正的视觉适配留作后续（指南第 8 节也标明是"后续方向"）。
- **需要你拍板的点**：是否接受"以空上下文守卫绕过视觉后端缺失"作为临时修复？（默认接受并已落地）
- **关联**：[踩坑：CANN 后端空上下文崩溃](../../pitfalls.md)
