---
title: 改动记录（deployment artifacts 归位）
tags: [project, MiniCPM]
created: 2026-07-21
updated: 2026-07-21
publish: true
---


# 改动记录

> 每次改动一个小节：改了什么 / 为什么 / 影响面 / 验证结果。

### 2026-07-21 测试脚本从 llama.cpp-omni 源码树迁到 MiniCPM 项目目录

- **改了什么**：把上一轮"继续做第 8 节"时生成在 `/workspace/llama.cpp-omni/` 的测试脚本与资源，迁移到部署指南同目录 `/workspace/workBase/project/MiniCPM/`：
  - 脚本：`test_ws_text.py`、`test_ws_tts.py`、`test_ws_vision.py`、`test_ws_audio.py`、`test_http_audio.sh`
  - 资源：`test_image.png`、`test_image.b64`
  - 同步改写脚本内硬编码路径：`test_ws_tts.py` 的 WAV 输出、`test_ws_vision.py` 的图片读取改为基于 `__file__` 的相对路径（脚本同级落盘）；`test_ws_audio.py` / `test_http_audio.sh` 引用的样例音频资源仍在 `llama.cpp-omni/tools/omni/assets/...`，改为绝对路径引用。
  - 部署指南第 6.2 节"运行"由 `cd /workspace/llama.cpp-omni ... python3 test_ws_text.py` 改为 `cd /workspace/workBase/project/MiniCPM ... python3 test_ws_text.py`，并加注五套脚本与图片随文档同目录、`start_server.sh` 留原地。
  - 删除 `llama.cpp-omni/` 中的原文件（`rm test_ws_tts.py test_ws_vision.py test_ws_audio.py test_http_audio.sh`）。
- **为什么**：测试脚本/资源属于本项目部署产出，不该污染 `llama.cpp-omni` 上游源码树（该目录是第三方 fork 工作区，应只含源码/build）；与部署指南同目录便于归档与复用。
- **影响面**：
  - `llama.cpp-omni/` 已无残留测试文件，目录干净。
  - `start_server.sh` **故意保留**在 `llama.cpp-omni/`（其 `cd "$(dirname "$0")"` + `./build/bin/llama-omni-server` 依赖该目录，迁走即失效）。
  - `test_ws_audio.py` / `test_http_audio.sh` 仍依赖 `llama.cpp-omni/tools/omni/assets/...` 的样例 wav，需该源码树存在才能跑（已在脚本注释标明）。
- **验证结果**：`/workspace/workBase/project/MiniCPM/` 现含指南 + 五脚本 + 两图片；`llama.cpp-omni/` 列目录确认无 `test_ws*`/`test_http*`/`test_image*`。`test_ws_text.py` 等纯网络脚本可直接从新目录运行。
