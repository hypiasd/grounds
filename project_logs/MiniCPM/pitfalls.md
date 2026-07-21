---
title: 踩坑 / 知识点账本
tags: [project, MiniCPM]
created: 2026-07-21
updated: 2026-07-21
publish: true
---


### 2026-07-21 实测环境与指南偏差
- **现象**：指南写 CANN=`cann-9.1.0-beta.1`、系统 Ubuntu 22.04；实测 `cann-9.1.0-beta.3`、openEuler 24.03。
- **根因**：指南基于特定验证机，真实机固件 / 系统不同。
- **解法**：以实测为准，CMake 用 `ASCEND_TOOLKIT_HOME`（已指向 beta.3），不盲抄指南路径。
- **防复发**：每步先 `echo $ASCEND_TOOLKIT_HOME` 与 `npu-smi info` 确认，再执行。
- **学到了什么**：部署文档是"意图"不是"脚本"，路径 / 版本必须本地核对。

### 2026-07-21 GitHub 源码拉取被限速/停流（关键坑）
- **现象**：`gh-proxy.org` 的 git clone 与 tarball 拉到 ~2MB 后**彻底停流**；`ghproxy.net` 仅 ~4KB/s；`gitee.com` 无 `llama.cpp-omni` 镜像（`[]`）；`kgithub/gitclone/atomgit` 不可达；ModelScope 无源码。
- **根因**：此环境对 GitHub 代码传输被**按 IP 硬限速 + 停流**（但 ModelScope CDN 权重可达 12MB/s，说明是 github 特定限流）。
- **解法（突破口）**：**`gh-proxy.com` 可用且稳定 ~818KB/s**（其他代理都废）。用它拉 `https://gh-proxy.com/https://github.com/tc-mb/llama.cpp-omni/archive/refs/heads/master.tar.gz` 解包即可。
- **防复发**：下次在此类环境拉 GitHub 源码，直接试 `gh-proxy.com`，别在 gh-proxy.org/ghproxy.net 上耗时间。
- **学到了什么**：代理可用性因环境而异，要实测多个代理并测"持续速率"而非一次突发。

### 2026-07-21 权重大小与指南不一致（ModelScope 版本漂移）
- **现象**：F16 主模型 16384959136 字节与指南**完全一致**；但 audio/vision/tts/projector/encoder/flow_matching 6 个文件大小与指南列出的不同（如 vision 指南 1.16G vs 实际 1.10G）。
- **核验**：10 个文件 GGUF 魔数 `47475546`(GGUF) 全部合法 → 下载无损坏，差异来自 **ModelScope 上模型自指南编写后已更新版本**。
- **影响**：不影响加载；服务正常起、推理正常。指南 2.3 的"与官方一致"应以 ModelScope 当前版本为准。
- **学到了什么**：权重版本会演进，校验魔数 + 主模型字节数比死磕旧快照大小更靠谱。

### 2026-07-21 CANN 后端空上下文崩溃（已修）
- **现象**：跑 HTTP 旧版 API 的 `omni_init` 时服务**直接崩溃退出**，日志 `CANN error: rtDeviceSynchronize ... context is a null pointer / current device: -1`，栈在 `ggml_backend_cann_free → aclrtSynchronizeDevice → vision_free → omni_free`。
- **根因**：`vision_backend` 默认 `metal`（Apple），在昇腾上视觉 CANN 后端上下文为空；HTTP `omni_init` 路径初始化视觉上下文后清理时，`aclrtSynchronizeDevice()` 因无设备而 `GGML_ABORT`。正是指南第 8 节说的"视觉后端适配是后续方向"。
- **修复**：在 `ggml/src/ggml-cann/ggml-cann.cpp` 的 `ggml_backend_cann_free` 加守卫——若本线程 `aclrtGetDevice` 拿到无效设备（-1）则跳过 synchronize/reset。属最小防御补丁（无设备本就不该同步）。
- **影响**：修复后 HTTP 三步骤全通且服务不崩；文本/音频 WS 测试本就不受影响。
- **关联**：[决策：CANN free 空上下文守卫](decisions/decision-ggml-cann-free-guard.md)
- **学到了什么**：跨后端（Apple metal → 昇腾 CANN）的"默认后端"假设是隐形雷；崩在服务端要会读 `ggml_abort` 栈定位到后端 free 路径。

### 2026-07-21 HTTP 旧版 API 有状态 + decode 产出短
- **现象**：HTTP `decode` 返回 SSE `data: {"content":"F",...}` 后 `end_of_turn:true` + `[DONE]`（仅 1 token）；而 WS 音频测试返回完整句子。连续第二次跑 `omni_init` 会卡住（rc=124 超时）——全局 omni 上下文有状态，前一次未干净结束会阻塞后续。
- **结论**：HTTP 旧版 API 三步（omni_init/prefill/decode）端点都能正常返回，**链路打通**；decode 只出 1 token 是该 legacy 路径的生成特性/上下文处理方式，非崩溃。生产建议走 WS `/backend`（已验证完整可用）。
- **学到了什么**：legacy HTTP 接口多有全局状态，测试要"每次起干净服务"跑一次；不稳定时优先用 WS 双工接口。

### 2026-07-21 CANN 后端 set/get_tensor_async 缺设备上下文（已修，根因）
- **现象**：开启 TTS（`use_tts_template=true`）后服务崩溃，栈在 `ggml_backend_cann_set_tensor_async → aclrtMemcpyAsync ... context is a null pointer / current device: -1`，发生在 **Token2Wav 的 t2w 线程**。
- **根因**：`ggml-cann.cpp` 里除 `set/get_tensor_async` 外的几乎所有回调（`graph_compute`/`synchronize`/`buffer` 分配等）入口都先 `ggml_cann_set_device(cann_ctx->device)` 绑定当前线程的 CANN 设备上下文；唯独这两个异步张量拷贝回调漏了。主线程推理前已被设过设备故不触发，但 **Token2Wav 的 t2w 线程是新线程、从未 set 过设备**，于是 `current device=-1`、空上下文、`rtMemcpyAsync` 崩。
- **修复**：在 `ggml_backend_cann_set_tensor_async` 与 `ggml_backend_cann_get_tensor_async` 入口补 `ggml_cann_set_device(cann_ctx->device);`（与同类回调一致）。这是**根因修复**而非防御补丁。
- **关联**：`decisions/decision-cann-set-get-tensor-device.md`
- **学到了什么**：CANN 设备上下文是**线程局部**的；任何会触碰 device 的回调都必须先 set device。多线程后端（如独立 T2W 线程）是这类漏网的放大镜。

### 2026-07-21 GGML_OP_SQR 断言在 Token2Mel 图下失败（已修）
- **现象**：TTS 修好设备上下文后又崩，栈 `ggml-cann.cpp:1925: GGML_ASSERT(dst->src[1]==nullptr) failed`，在 `Token2Mel::infer_one_chunk → ggml_backend_graph_compute`。
- **根因**：CANN 后端把 `GGML_OP_SQR` 用 `x*x`（aclnn_mul）实现，先 `assert(src[1]==nullptr)` 再 `src[1]=src[0]`。Token2Mel 计算图会把 SQR 节点的 `src[1]` 作为 view 复用为非空，导致重复 compute 时断言失败。
- **修复**：去掉严格断言，直接 `dst->src[1]=dst->src[0];` 保证 x*x 语义（与 SQR 定义一致，且对重复 compute 幂等）。
- **关联**：`decisions/decision-cann-sqr-assert.md`
- **学到了什么**：用二元 op 模拟一元 op 的 hack 若带 `src[1]==nullptr` 断言，在图复用/多模型下极易踩雷；应保证语义而非依赖调用方不填 src[1]。

### 2026-07-21 WS 协议实测要点（客户端写法坑）
- **session.init 必须包 `payload`**：`{"type":"session.init","payload":{"mode":"turn_based", ...}}`；顶层平铺字段会被判 `missing payload`。
- **input 是对象不是数组**：`{"type":"input.append","input":{"messages":[{"role":"user","content":"..."}],"streaming":true,"generation":{"max_new_tokens":N}}}`，messages 才是轮次列表。
- **完整文本在 `response.done.text`**：流式 `response.output.delta` 的 text 未必齐；最终要读 `response.done.text`（TTS 同理，音频在 `response.done.audio`）。
- **TTS 每轮要 `use_tts_template:true`**：session 级 `use_tts` 只负责加载 TTS 模型，**真正触发语音生成**靠 input 里的 `use_tts_template`（或 `input.tts.enabled`）。否则只出文本、不出音频。
- **TTS 音频落盘不回传**：fork 中 T2W 线程会 `ws.send` 音频 delta，但与主线程的文本 delta 发送**并发竞态**（httplib ws 非线程安全），客户端常收不到 audio delta；但服务会把每 chunk 的合法 WAV 写到 `tts_wav_output_dir`（默认 `/tmp/omni_ws/<sid>/round_*/tts_wav/wav_*.wav`），24kHz/16bit/单声道，可直接播放验证。
- **视觉输入字段**：`input.image.data` = base64（另可 `input.image.max_slice_nums`）；本 fork 视觉后端**自动选 CANN0**，无需把 `vision_backend` 从 metal 改成 CANN（指南第 8 节该条在本 fork 已默认满足）。

### 2026-07-21 本容器无 systemd init（部署注意）
- **现象**：`ps -p 1 -o comm=` 为 `bash`，不是 `systemd`；`systemctl` 无法 enable 当前容器的服务。
- **影响**：`/etc/systemd/system/llama-omni.service` 已写好，但**只能用于宿主机/真实系统**，容器内只能 `nohup ./start_server.sh &` 跑。
- **学到了什么**：容器形态决定 init 系统；写 systemd unit 要分清"给宿主机"还是"给容器"。

### 2026-07-21 把脚本/资源迁出上游源码树时的"路径三分法"（小坑）
- **现象**：想把测试脚本从 `llama.cpp-omni/`（第三方 fork 工作区）迁到本项目目录时，脚本里有几类路径，不能一刀切处理。
- **根因**：脚本"运行位置"会随迁移改变，硬编码的绝对/相对路径会失效。
- **解法（路径三分法）**：
  1. **自包含 → 相对路径**：脚本自己产出的文件（如 `test_ws_tts.py` 写出的 WAV、读同目录的 `test_image.b64`）改用 `os.path.join(os.path.dirname(os.path.abspath(__file__)), "xxx")` —— 迁到哪都能用。
  2. **引用外部资源 → 绝对路径**：脚本依赖别人目录里的资源（如 `test_ws_audio.py` 用的 `llama.cpp-omni/tools/omni/assets/...` 样例 wav）写死绝对路径，并在注释里标明依赖，迁走后仍能跑。
  3. **依赖 build 相对路径 → 原地不动**：`start_server.sh` 靠 `cd "$(dirname "$0")"` + `./build/bin/llama-omni-server`，必须留在源码树根，**不能迁**，否则找不到二进制。
- **防复发**：迁移任何脚本前，先 `grep` 里面的路径，按上面三类分别处理；凡带 `./build`、`$(dirname` 的启动/部署脚本一律留原地。
- **学到了什么**："把文件挪到项目目录"听起来简单，但路径语义（相对自身 / 相对第三方 / 相对构建）不同，分类处理才不破坏可运行性。
