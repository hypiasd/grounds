---
title: 能力账本（淡出机制）
tags: [project, MiniCPM]
created: 2026-07-21
updated: 2026-07-21
publish: true
---


# 能力账本（M5 淡出）

- **当前阶段**：4 全功能验证（指南第 8 节"后续可测试内容"已逐条跑通）
- **已掌握**：
  - NPU / CANN 环境自检；多代理实测选最快（`gh-proxy.com`）；`GGML_CANN` 编译；`llama-omni-server` 双协议（WS `/backend`、HTTP SSE）。
  - 读 `ggml_abort` 栈定位 CANN 后端 bug，并区分"防御补丁"与"根因修复"。
  - **TTS 语音输出**：`use_tts_template=true` 触发，Token2Wav 在 CANN 上跑通，产出合法 24kHz/16bit 单声道 WAV（落盘 `tts_wav_output_dir`）。
  - **视觉输入**：图像经 `vision_ctx`（CANN0 后端）编码，embedding 注入 LLM 生成描述——vision 后端在昇腾上**自动走 CANN**（不需要 `metal`），指南说的"metal→CANN 适配"在本 fork 已默认成立。
  - **多卡负载均衡**：`--split-mode tensor` 双 910C 各承载约一半权重/激活，推理正确。
- **还不会 / 待深入**：WS 实时音频回传（fork 中 T2W 线程与主线程并发 `ws.send` 竞态，客户端收不到 audio delta，仅落盘）；接入 MiniCPM-o-Demo 前端（需 GitHub，本环境不可达）。
- **下一步练什么**：把 TTS 音频回传改成线程安全（加发送锁 / 队列）；尝试 `split-mode row` 对比吞吐；若需前端，待可访问 GitHub 时再拉 Demo。

### 阶段 4 记录（2026-07-21，指南第 8 节）
- 目标：把"后续可继续测试的内容"逐条验证，并修通在此过程中暴露的 CANN 后端缺陷。
- 验证清单：
  1. ✅ **TTS 语音输出**：`use_tts_template=true` + 修复 Token2Wav 线程的 CANN 设备上下文缺失 + `GGML_OP_SQR` 断言后，产出 `wav_0..N.wav`（24kHz 单声道，单 chunk≈0.84s）。客户端不收音频 delta（见 pitfall），但落盘 WAV 合法。
  2. ✅ **视觉输入**：`input.image.data` 传 base64，模型给出图像描述（本 fork vision 后端默认 CANN0，无需改 metal）。
  3. ✅ **多卡 `--split-mode tensor`**：双 910C 显存 ~10.9G / ~10.7G 同时占用，AICore 双卡活跃，文本回复正确。
  4. 📄 **systemd 服务化**：已写 `/etc/systemd/system/llama-omni.service`（含 `LD_LIBRARY_PATH`、工作目录、`--split-mode tensor`）；本容器 PID1=bash，**无 systemd init**，故只能在宿主机 `systemctl enable` 使用，容器内无法 enable。
  5. ⏭️ **MiniCPM-o-Demo 前端**：需 GitHub 拉取，本环境 GitHub 代码传输被停流，跳过（见阶段 1 GitHub 坑）。
