---
title: MiniCPM 部署时间线（Runbook）
created: 2026-07-21
updated: 2026-07-21
tags: [project, MiniCPM]
publish: true
---

# MiniCPM 部署时间线（Runbook）

> 本文件是 MiniCPM 昇腾 910C 部署的**单一主线记录**：按时间线串起「决策 / 实施 / 问题 / 解决」。
> 不再另开 `decisions` / `pitfalls` / `experiments` / `changes` / `learning-journal` 等文件——它们各自的内容都已**内联到发生它的时间线节点**里（决策用「决策」块、踩坑用「问题 / 解决」块），避免同一件事在多个文件重复写。
> 指南：《MiniCPM-o 4.5 昇腾 910C 部署上手指南》。环境：2× Ascend 910C，CANN 9.1.0-beta.3，openEuler 24.03，llama.cpp-omni（tc-mb/master），GGML_CANN。

## 1. 环境检查
- **实施**：`npu-smi info` 确认双 910C 在线；`cat /usr/local/Ascend/version.cfg` 读 CANN；`cat /etc/os-release` 读 OS；`echo $ASCEND_TOOLKIT_HOME` 确认已指向 beta.3；磁盘 6.7T，gh-proxy 可达。
- **问题**：指南写 CANN=`cann-9.1.0-beta.1`、系统 Ubuntu 22.04；实测 `cann-9.1.0-beta.3`、openEuler 24.03。
- **解决**：以实测为准，CMake 用 `ASCEND_TOOLKIT_HOME`（已指向 beta.3），不盲抄指南路径；每步先 `echo $ASCEND_TOOLKIT_HOME` 与 `npu-smi info` 确认再执行。
- **决策**：CANN 版本用 beta.3 而非降级到 beta.1（见节点 4 编译决策）。
- **学到**：部署文档是"意图"不是"脚本"，路径 / 版本必须本地核对。

## 2. 模型权重下载
- **实施**：`modelscope download ...` 拉取 MiniCPM-o 2.6 全模态权重到本地；主模型 F16 字节 `16384959136`。
- **问题**：audio / vision / tts / projector / encoder / flow_matching 共 6 个文件大小与指南快照不同（如 vision 指南 1.16G vs 实际 1.10G）。
- **解决**：核验 10 个文件 GGUF 魔数 `47475546` 全部合法 → 下载无损坏；差异来自 **ModelScope 上模型自指南编写后已更新版本**。以 ModelScope 当前版本为准，不影响加载。
- **学到**：权重版本会演进，校验魔数 + 主模型字节数比死磕旧快照大小更靠谱。

## 3. 源码获取
- **实施**：获取带 CANN 适配的 llama.cpp-omni fork（tc-mb/master）并切 CANN 分支（源码树现物理内嵌于 `project/MiniCPM/llama.cpp-omni/`，属本项目工作目录内，非软链）。
- **问题**：`gh-proxy.org` 拉到 ~2MB 后彻底停流；`ghproxy.net` ~4KB/s；`gitee.com` 无镜像；`kgithub/gitclone/atomgit` 不可达；ModelScope 无源码。本环境对 GitHub 代码传输被按 IP 硬限速 + 停流（但 ModelScope CDN 权重可达 12MB/s）。
- **解决（突破口）**：**`gh-proxy.com` 可用且稳定 ~818KB/s**。用它拉 `https://gh-proxy.com/https://github.com/tc-mb/llama.cpp-omni/archive/refs/heads/master.tar.gz` 解包。
- **学到**：代理可用性因环境而异，要实测多个代理并测"持续速率"而非一次突发。

## 4. 编译
- **实施**：`export ASCEND_HOME=/usr/local/Ascend` 等 CANN 环境变量 → `cmake -B build -DGGML_CANN=ON ...` → `cmake --build build -j`；产出 `./build/bin/llama-omni`、`llama-server`（cli/tests 旁支目标失败无关）。
- **决策：CANN 版本用 beta.3**
  - 问题：指南 4.1 假设 beta.1，实测 beta.3；CMake 经 `ASCEND_TOOLKIT_HOME` 定位，错配会找不到 `libascendcl.so`。
  - 选项：A 直接用已装 beta.3（推荐，API 兼容）/ B 降级重装 beta.1（成本高无收益）。
  - 决策：选 A。**需拍板点**：是否接受 beta.3 替代 beta.1（默认接受，已确认环境变量指向它）。
- **问题 / 解决（编译期 3 个 CANN 适配 bug，均在 `ggml/src/ggml-cann/ggml-cann.cpp`，增量重编 `llama-omni-server`）**：
  1. **free 空设备上下文崩溃**（HTTP `omni_init` 触发，`ggml_backend_cann_free → aclrtSynchronizeDevice` 报空指针 / -1 → `GGML_ABORT`；根因 `vision_backend` 默认 `metal`，昇腾上视觉 CANN 上下文为空）。
     - **决策**：加守卫——`aclrtGetDevice` 拿到 -1 时跳过 synchronize/reset（最小防御补丁，不动推理主链路；真正 vision CANN 路径留后续）。**需拍板点**：是否接受以空上下文守卫绕过视觉后端缺失（默认接受已落地）。
  2. **set/get_tensor_async 缺设备上下文**（开启 TTS 后崩，栈在 `set_tensor_async → aclrtMemcpyAsync` 空指针 / -1，发生于 Token2W 的 t2w 线程）。
     - 根因：CANN 设备上下文是**线程局部**；除这两个异步回调外，其它回调入口都先 `ggml_cann_set_device`；独 t2w 线程从未 set 过设备。
     - **决策**：**根因修复**——在 `set_tensor_async` / `get_tensor_async` 入口补 `ggml_cann_set_device(cann_ctx->device);`（与同类回调一致）。**需拍板点**：根因修复 vs 仅防御（选根因修复）。
  3. **GGML_OP_SQR 断言在 Token2Mel 下失败**（栈 `GGML_ASSERT(dst->src[1]==nullptr) failed`，在 `Token2Mel::infer_one_chunk`）。
     - 根因：CANN 用 `x*x`(aclnn_mul) 实现 SQR，先 assert `src[1]==nullptr` 再 `src[1]=src[0]`；Token2Mel 图把 SQR 的 `src[1]` 作 view 复用为非空，重复 compute 时断言失败。
     - **决策**：去掉严格断言，直接 `dst->src[1]=dst->src[0];`（SQR 定义即 x*x，对重复 compute 幂等）。
  - **学到**：跨后端（Apple metal → CANN）的"默认后端"假设是隐形雷；CANN 设备上下文线程局部，任何触碰 device 的回调都须先 set device；用二元 op 模拟一元 op 的 hack 若带 `src[1]==nullptr` 断言在图复用下极易踩雷。

## 5. 起服务
- **实施**：`bash project/MiniCPM/llama.cpp-omni/start_server.sh`（脚本固化 `--split-mode tensor`），服务在 WS `10002` 起来；`curl http://127.0.0.1:28099/health` → `{"engine":"comni","status":"ok"}`。
- **决策：split-mode 选 tensor**（为绕开 L1 cache 桶广播 assertion 而选；双 910C 各承载约一半权重 / 激活，推理正确，已固化进 `start_server.sh`）。
- **问题**：本容器 `ps -p 1` = `bash`，**无 systemd init**，`systemctl` 无法 enable。
- **解决**：未用 systemd 单元托管，改用前台 / `nohup ./start_server.sh &`；已写好的 `/etc/systemd/system/llama-omni.service`（含 `LD_LIBRARY_PATH`、工作目录、`--split-mode tensor`）仅宿主机可用。
- **学到**：容器形态决定 init 系统；写 systemd unit 要分清"给宿主机"还是"给容器"。

## 6. API 测试
- **实施**：文本 / 视觉 / TTS 走 WS（`test_ws_text.py` / `test_ws_vision.py` / `test_ws_tts.py`）；音频走 `test_http_audio.sh`（HTTP `/completion`）。
- **问题 / 解决**：
  - **WS 音频路径有 `ws_(assert)` 卡点** → 改为 HTTP `/completion` 绕开（音频经 HTTP 跑通）。
  - **HTTP 旧版 API 有状态 + decode 产出短**：`decode` 返回 1 token 后 `[DONE]`（legacy 路径生成特性，非崩溃）；连续第二次 `omni_init` 会卡住（全局 omni 上下文有状态）。→ 结论：HTTP 三步链路打通；生产建议走 WS `/backend`（已验证完整）。
- **WS 协议实测要点（客户端写法坑）**：
  - `session.init` 必须包 `payload`（顶层平铺会被判 missing）；`input` 是对象不是数组（`messages` 才是轮次列表）；完整文本在 `response.done.text`（TTS 音频在 `response.done.audio`）。
  - TTS 每轮要 `use_tts_template:true`（session 级 `use_tts` 只加载模型，真正触发靠 input 里的 `use_tts_template`）。
  - TTS 音频落盘不回传：fork 中 T2W 线程 `ws.send` 音频 delta 与主线程文本 delta 并发竞态（httplib ws 非线程安全），客户端常收不到 audio delta；但服务把每 chunk 合法 WAV 写到 `tts_wav_output_dir`（默认 `/tmp/omni_ws/<sid>/round_*/tts_wav/wav_*.wav`，24kHz/16bit/单声道），可直接播放验证。
  - 视觉输入 `input.image.data` = base64；本 fork 视觉后端**自动选 CANN0**，无需把 `vision_backend` 从 metal 改成 CANN（指南第 8 节该条已默认满足）。

## 7. 指南第 8 节验证矩阵
- **TTS 语音输出** ✅：`use_tts_template=true` + 修复 2 个 CANN 后端 bug 后，Token2Wav 在 CANN 上产出合法 24kHz/16bit/单声道 WAV（落盘 `tts_wav_output_dir`）。客户端不收 audio delta（见节点 6），但落盘合法。
- **视觉输入** ✅：`input.image.data=<base64>`，模型给出图像描述；vision 后端自动 CANN0。
- **多卡 `--split-mode tensor`** ✅：双卡各 ~10.9G / ~10.7G，AICore 双活跃，文本正确；已固化进 `start_server.sh`。
- **systemd 服务化** 📄：文件就绪，本容器无 systemd init，仅宿主机可用 `systemctl enable`。
- **MiniCPM-o-Demo 前端** ⏭️：需 GitHub 拉取，本环境被停流，跳过。
- 复现命令：
  ```bash
  cd project/MiniCPM/llama.cpp-omni && ./start_server.sh   # 含 --split-mode tensor
  python3 test_ws_tts.py      # use_tts_template=true，WAV 落 /tmp/omni_ws/<sid>/.../tts_wav/wav_*.wav
  python3 test_ws_vision.py    # 传 test_image.b64
  python3 test_ws_text.py
  ```

## 8. 测试脚本归位
- **改动**：把测试脚本与资源从 `project/MiniCPM/llama.cpp-omni/`（上游 fork 工作区）迁到本项目根目录 `project/MiniCPM/`：`test_ws_text.py`、`test_ws_tts.py`、`test_ws_vision.py`、`test_ws_audio.py`、`test_http_audio.sh`、`test_image.png`、`test_image.b64`。
- **为什么**：脚本 / 资源属本项目部署产出，不该污染上游源码树（应只含源码 / build）；与指南同目录便于归档复用。
- **路径三分法**（迁移核心坑）：
  1. 自包含 → 相对路径（`__file__` 同级落盘 / 读取）；
  2. 引用外部资源 → 绝对路径（如 `project/MiniCPM/llama.cpp-omni/tools/omni/assets/...` 样例 wav，注释标明依赖）；
  3. 依赖 build 相对路径 → 原地不动：`start_server.sh` 靠 `cd "$(dirname "$0")"` + `./build/bin/...`，**必须留源码树根**，不能迁。
- **验证**：`project/MiniCPM/` 现含指南 + 五脚本 + 两图片；`project/MiniCPM/llama.cpp-omni/` 已无残留测试文件。

## 能力账本 / 下一步（收尾）
- **当前阶段**：4 全功能验证（指南第 8 节逐条跑通）。
- **已掌握**：NPU / CANN 自检；多代理实测选最快；`GGML_CANN` 编译；WS / HTTP 双协议；读 `ggml_abort` 栈定位 CANN bug 并区分"防御补丁 vs 根因修复"；TTS / 视觉 / 多卡在 CANN 上跑通。
- **还不会 / 待深入**：WS 实时音频回传（T2W 线程 ws.send 竞态，仅落盘）；接入 Demo 前端（需 GitHub，本环境不可达）。
- **下一步**：把 TTS 音频回传改线程安全（发送锁 / 队列）；试 `split-mode row` 对比吞吐；可访问 GitHub 时再拉 Demo。

## 交付产物清单
> 本项目产出的可复用文件（位置用项目相对 / 源码相对路径，不写本机绝对路径）。

### MiniCPM-o 4.5 昇腾 910C 部署上手指南（核心蓝图）
- **是什么**：贯穿全程的蓝图文档，1–8 节覆盖环境 / 权重 / 源码 / 编译 / 服务 / 测试 / 踩坑 / 后续。
- **位置**：`project/MiniCPM/MiniCPM-o 4.5 昇腾 910C 部署上手指南.md`
- **来源**：原创（按真实跑通步骤实测撰写）
- **与实测偏差**：CANN beta.1→beta.3、Ubuntu→openEuler（节点 1）；权重 6 文件漂移（节点 2）；第 8 节 vision 条已默认满足（节点 6）。
- **状态**：✅ 可用

### 测试脚本集（文本 / 音频 / 视觉 / TTS / HTTP 音频）
- **位置**：`project/MiniCPM/test_ws_text.py`、`test_ws_audio.py`、`test_ws_vision.py`、`test_ws_tts.py`、`test_http_audio.sh`、`test_image.png` / `test_image.b64`
- **来源**：改写自指南第 6 节（按路径三分法从 llama.cpp-omni 迁来，见节点 8）
- **状态**：✅ 可用

### 启动脚本 start_server.sh
- **位置**：`project/MiniCPM/llama.cpp-omni/start_server.sh`（故意留源码树，依赖 `./build/bin`，见节点 8 路径三分法第 3 条）
- **状态**：✅ 可用（固化 `--split-mode tensor`）

### systemd 服务单元
- **位置**：`/etc/systemd/system/llama-omni.service`（宿主机路径）
- **状态**：📄 就绪未验证（本容器无 systemd init，仅宿主机可用，见节点 5）
