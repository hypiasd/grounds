---
title: 实验卡（指南第 8 节验证矩阵）
tags: [project, MiniCPM, experiment]
created: 2026-07-21
updated: 2026-07-21
---

# 实验卡：指南第 8 节"后续可继续测试的内容"

> 环境：昇腾 910C ×2，CANN 9.1.0-beta.3，openEuler 24.03，llama.cpp-omni（tc-mb/master），GGML_CANN 已编。

| 项 | 触发方式 | 结果 | 备注 |
|----|----------|------|------|
| TTS 语音输出 | WS `session.init.payload.use_tts=true` + `input.use_tts_template=true` | ✅ 产出 `wav_0..N.wav` | 24kHz/16bit/单声道；客户端不收 audio delta（T2W 线程 ws.send 竞态），但落盘合法。修复 2 个 CANN 后端 bug 后才通。 |
| 视觉输入 | WS `input.image.data=<base64>` | ✅ 模型给出图像描述 | vision 后端自动 CANN0，无需改 metal。 |
| 多卡 `--split-mode tensor` | 启动加 `--split-mode tensor` | ✅ 双卡各 ~10.9G/~10.7G，AICore 双活跃，文本正确 | 默认 LAYER 切分也双卡；已固化进 `start_server.sh`。 |
| systemd 服务化 | 写 `/etc/systemd/system/llama-omni.service` | 📄 文件就绪 | 本容器 PID1=bash 无 systemd init，仅宿主机可用 `systemctl enable`。 |
| MiniCPM-o-Demo 前端 | 需 GitHub 拉取 | ⏭️ 跳过 | 本环境 GitHub 代码传输被停流（见早期 pitfall）。 |

## 修复记录（CANN 后端，影响 TTS/视觉）
1. `set/get_tensor_async` 缺 `ggml_cann_set_device` → T2W 线程空上下文崩溃。→ 根因修复。
2. `GGML_OP_SQR` 严格 `src[1]==nullptr` 断言 → Token2Mel 图重复 compute 失败。→ 去掉断言，直接 x*x。
（均在 `ggml/src/ggml-cann/ggml-cann.cpp`，已增量重编 `llama-omni-server`。）

## 复现命令
```bash
# 服务（多卡）
cd /workspace/llama.cpp-omni && ./start_server.sh   # 含 --split-mode tensor
# TTS
python3 test_ws_tts.py          # use_tts_template=true，WAV 落 /tmp/omni_ws/<sid>/.../tts_wav/wav_*.wav
# 视觉
python3 test_ws_vision.py       # 传 test_image.b64
# 文本
python3 test_ws_text.py
```
