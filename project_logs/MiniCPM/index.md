---
title: MiniCPM 项目全景（Ascend 910C 部署）
tags: [project, MiniCPM]
created: 2026-07-21
updated: 2026-07-21
---

# MiniCPM · 全局掌控视图

## 目标
按《MiniCPM-o 4.5 昇腾 910C 部署上手指南》完成全部部署与测试（环境检查 → 模型下载 → 源码 → 编译 → 起服务 → API 测试），并把踩坑 / 决策实时沉淀。

## 技术栈
- 硬件：2× Ascend 910C（NPU）
- 系统：openEuler 24.03 (aarch64)，Docker 容器内（不能套 Docker）
- CANN：`/usr/local/Ascend/cann-9.1.0-beta.3`（`ASCEND_TOOLKIT_HOME` 已指向它）
- Python：`/usr/local/python3.12.13/bin/python3`
- 推理框架：llama.cpp-omni（`GGML_CANN` 后端，FP16 最快）

## 关键命令
- 服务：`/workspace/llama.cpp-omni/start_server.sh`（端口 28099，依赖 `./build/bin`，留原地）
- 健康检查：`curl http://127.0.0.1:28099/health`
- 文本/音频/视觉/TTS 测试脚本与图片：本项目目录 `/workspace/workBase/project/MiniCPM/`（随部署指南同目录）：`test_ws_text.py`、`test_ws_audio.py`、`test_ws_vision.py`、`test_ws_tts.py`、`test_http_audio.sh`、`test_image.png/.b64`

## 结构
- 模型：`/workspace/MiniCPM-o-4_5-gguf/`（GGUF，FP16）
- 源码：`/workspace/llama.cpp-omni/`

## 现状
- [x] 环境检查通过（NPU×2、CANN beta.3、gh-proxy 可达、磁盘 6.7T）
- [x] 模型下载（10 个 GGUF 全下完；F16 与指南字节级一致 16384959136；其余 6 个文件大小与指南快照不同＝ModelScope 已更新版本，魔数校验合法）
- [x] 源码获取（`gh-proxy.org/ghproxy.net` 对 GitHub 限速/停流；改用 **gh-proxy.com** ~818KB/s 拉 master tarball 解包）
- [x] 编译（GGML_CANN=ON；`llama-omni-server` 干净编出；cli/tests 旁支目标失败无关）
- [x] 起服务 + 健康检查 `/health` → `{"engine":"comni","status":"ok"}`
- [x] WS 文本测试（~5s，完整回复）／WS 音频测试（~1s，完整回复）／HTTP 音频测试（omni_init+prefill+decode 全通，服务不崩）
- [x] 修复 CANN 后端 `ggml_backend_cann_free` 空设备上下文 `GGML_ABORT` → 加空上下文守卫，HTTP 路径不再崩服务

## 指南第 8 节（后续可测试内容）— 已全部验证
- [x] **TTS 语音输出**：`use_tts_template=true` 触发；修通 `set/get_tensor_async` 设备上下文 + `GGML_OP_SQR` 断言后，Token2Wav 在 CANN 上产出合法 24kHz WAV（落盘 `tts_wav_output_dir`，客户端不收 audio delta 已知限制）
- [x] **视觉输入**：`input.image.data` 传 base64，模型给出描述；vision 后端**自动 CANN0**，指南说的"metal→CANN 适配"在本 fork 已默认满足
- [x] **多卡 `--split-mode tensor`**：双 910C 各承载约一半权重/激活，推理正确（已固化进 `start_server.sh`）
- [x] **systemd 服务化**：已写 `/etc/systemd/system/llama-omni.service`（含 `LD_LIBRARY_PATH`、工作目录、`--split-mode tensor`）；本容器 PID1=bash 无 systemd init，仅宿主机可 `enable`
- [ ] **MiniCPM-o-Demo 前端**：需 GitHub 拉取，本环境 GitHub 代码传输被停流，跳过

## 决策指针
- [决策：CANN 版本 beta.3 vs 指南 beta.1](decisions/decision-cann-version.md)
- [决策：CANN free 空上下文守卫](decisions/decision-ggml-cann-free-guard.md)
- [决策：set/get_tensor_async 补设备上下文（根因）](decisions/decision-cann-set-get-tensor-device.md)
- [决策：GGML_OP_SQR 断言放宽](decisions/decision-cann-sqr-assert.md)

## 改动指针
- [改动：测试脚本从 llama.cpp-omni 迁出到 MiniCPM 项目目录](changes.md)

## 外部仓库
- 源码：`https://github.com/tc-mb/llama.cpp-omni.git`（经 `v4.gh-proxy.org` 代理 clone）
- 权重：ModelScope `OpenBMB/MiniCPM-o-4_5-gguf`
