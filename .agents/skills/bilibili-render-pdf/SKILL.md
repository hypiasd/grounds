---
name: bilibili-render-pdf
description: 用户手动或用 `$bilibili-render-pdf <BV链接>` 触发，把一个 Bilibili 视频（讲座/教程/技术演讲）转换成结构化中文 LaTeX 笔记并编译为 PDF。不接受语义触发——即使用户贴了 BV 链接，没有显式调用本 skill 也不得自动启动。工作目录与成品目录合一，都在 video/<标题>/，无复制步骤。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# bilibili-render-pdf

把一个 Bilibili 视频转成完整可编译的 `.tex` 笔记 + 渲染好的 PDF。

本 skill 是视频转 PDF 的完整版（B 站特化），`youtube-render-pdf` 是其 YouTube 简化版。针对 B 站的字幕稀缺、登录门控高清、分P 视频、平台特定非教学内容做了适配。

## 何时用（触发）

**只接受手动触发**：
- 用户明确说"用 bilibili-render-pdf 处理 X"、"走 bilibili-render-pdf"
- 用户输入 `$bilibili-render-pdf <BV链接>`

**不得自动触发**：即使用户贴了 BV/b23.tv 链接，没有显式调用本 skill，agent 不得自行启动。可以先问"要用 bilibili-render-pdf 处理吗？"。

## 目标（完成时仓库应处于的状态）

- `video/<视频标题>/` 是工作目录与成品目录合一的单一目录，最终保留（进 git）：`.tex` + `.pdf` + `index.md`。
- `cover.jpg`、`sources/`、`figures/`、`ocr/` 是**临时中间产物**（不进 git，由 `.gitignore` 排除）——仅在编译期存在，交付 commit 后由 skill 自动删除，不长期占用本地磁盘。
- 已 `git commit`（grounds 直接 push；临时派生仓 commit 后**自动 `$sync`** 推回），commit message：`bilibili-render-pdf: <视频标题>`

## Bilibili vs YouTube: 关键差异

| 方面 | 处理 |
|------|------|
| **字幕稀缺** | **始终**尝试 CC 字幕下载，即使 metadata 显示 `NA`。先 CC → 回退 Whisper → 视觉模式 OCR。B 站 metadata 经常误报 `NA` 但实际可下载 |
| **登录门控高清** | 1080P+ 需要 cookies；提示用户用 `yt-dlp --cookies-from-browser chrome` |
| **分P 视频** | 检测分P 并问用户处理哪些 P |
| **URL 格式** | 支持 `bilibili.com/video/BVxxxxxxx` 和 `b23.tv` 短链 |
| **弹幕** | 不用弹幕作教学内容源（噪声太大）；只用 CC 字幕或 Whisper 输出 |

---

## 环境检查（首先运行）

下载任何内容前，先确定最快的内容提取路径，避免在硬件不支持的方法上浪费 30+ 分钟。

### 1. 硬件检查

```bash
python3 -c "import torch; gpu = torch.cuda.is_available() or torch.backends.mps.is_available(); print('GPU available:', gpu)" 2>/dev/null || echo "torch not available"
sysctl -n hw.ncpu  # CPU 核心数
```

- **GPU 可用**（CUDA 或 MPS）：用更大更快的 Whisper 模型。Mac Apple Silicon 实测：**CPU + int8 是最优路径**（比 MPS + float32 快 ~45%）。MPS 后端只支持 float32 计算精度，不支持 int8 和 float16——`compute_type="int8"` 在 MPS 上会静默失败（模型加载正常但永远不产出 segment），`compute_type="float16"` 直接报 ValueError。MPS + float32 可工作但比 CPU + int8 慢，因为 int8 量化带来的模型压缩和计算加速（~4×）远超 MPS 的 GPU offload 收益。详见下行 benchmark 数据。
- **仅 CPU（Mac 常见）**：优先小模型或视觉模式

- **Mac faster-whisper Benchmark**（60s 中文音频，small 模型，Apple Silicon M-series）：

  | 配置 | 耗时 | 状态 |
  |------|------|------|
  | CPU + int8 | **12.3s** | ✅ 推荐（最快） |
  | MPS + float32 | 17.8s | ⚠️ 可用，慢 ~45% |
  | MPS + default | 18.0s | ⚠️ 自动回退 float32 |
  | MPS + int8 | N/A | ❌ 静默失败（0 segment） |
  | MPS + float16 | N/A | ❌ ValueError |
  | MPS + int8\_float16 | N/A | ❌ ValueError |

  Agent 可以用 60s 音频片段自行跑 benchmark 确认当前机器的排名。

### 2. 工具可用性检查

```bash
which whisper                                        # OpenAI Whisper CLI
python3 -c "import faster_whisper; print('ok')" 2>/dev/null   # faster-whisper: CTranslate2 后端，CPU 快 3-5×
which tesseract && tesseract --list-langs 2>&1 | grep chi_sim  # 视觉模式 OCR 回退
which montage || which magick                                   # ImageMagick 帧拼接（实际命令用 montage，只有 magick 时改用 `magick montage`）
which xelatex                                                   # LaTeX → PDF 编译
which ffmpeg && which ffprobe                                   # 视频/音频/帧提取 + 时长校验（同包安装）
which pdftotext                                                 # 成品 PDF 抽查（缺失时跳过抽查但需在交付时说明）
```

### 2b. Visual API 帧评估检查（盲模式环境推荐）

当 `view_image` 不可用时，本地 tesseract OCR 在 CPU 上批量评估太慢，远程视觉/OCR API 是可靠回退。

```bash
# 检查 SiliconFlow API key（或等价 OpenAI 兼容端点）
[ -f ~/.config/bilibili-render-pdf/siliconflow_key ] && echo "SiliconFlow key: FOUND" || echo "SiliconFlow key: MISSING"
python3 -c "from openai import OpenAI; print('openai package: ok')" 2>/dev/null || echo "openai package: MISSING (pip install openai)"
# 检查本 skill 自带的帧评估脚本
[ -f .agents/skills/bilibili-render-pdf/scripts/frame_assess.py ] && echo "frame_assess.py: FOUND" || echo "frame_assess.py: MISSING"
```

key 缺失时，请用户创建 `~/.config/bilibili-render-pdf/siliconflow_key`（一行纯文本 API key）。脚本用 OpenAI 兼容的 SiliconFlow 端点 + `deepseek-ai/DeepSeek-OCR` 做中文 OCR，~1.5s/帧。

### 3. 模型缓存检查

```bash
ls ~/.cache/whisper/                                                  # 缓存的 OpenAI Whisper 模型
ls ~/.cache/huggingface/hub/models--Systran--faster-whisper-*/        # 缓存的 faster-whisper 模型
```

### 4. 工作区状态检测（仅复用上次运行时执行）

> **前置条件**：本节仅在已存在工作目录时执行。首次运行（`video/` 下无匹配标题的目录）直接跳到「工作区设置」创建新目录。
>
> **如何知道上次运行的工作目录**：先 `ls video/` 列已有目录，匹配标题决定是否复用。同一视频重跑时直接复用同名目录，然后 `cd` 到该目录再执行本节检查。在仓库根目录执行时，这些相对路径全部不存在，检查恒为 MISSING。

```bash
for f in sources/video.mp4 sources/audio.wav sources/subtitles.srt cover.jpg; do
  [ -f "$f" ] && echo "EXISTS: $f ($(wc -c < "$f" | tr -d ' ') bytes)" || echo "MISSING: $f"
done
[ -f sources/subtitles.srt ] && python3 -c "
with open('sources/subtitles.srt') as f:
    lines = f.read().strip().split('\\n')
entries = [l for l in lines if '-->' in l]
print(f'{len(entries)} subtitle entries')
if entries:
    last_ts = entries[-1].split(' --> ')[1].replace(',',':').split(':')
    last_sec = int(last_ts[0])*3600 + int(last_ts[1])*60 + int(last_ts[2])
    print(f'Last timestamp: {last_sec}s')
"
```

有残留时根据质量决定复用或替换，不要盲删。

### 5. 转录策略选择

基于检查结果选**一个**策略并坚持，不要中途切换——每次重试都耗时数分钟。

| 条件 | 工具 | 模型 | 预期时间（10 分钟音频，CPU） |
|------|------|------|------------------------------|
| GPU 可用 | `faster-whisper` | `medium` 或 `large-v3` | ~30s |
| CPU + `faster-whisper` 可用 + medium 已缓存 | `faster-whisper` | `medium`, `int8`, `local_files_only=True` | 3-8 分钟 |
| CPU + `faster-whisper` 可用 | `faster-whisper` | `small`, `int8` | 1-3 分钟 |
| CPU + 只有 `openai-whisper` + medium 已缓存 | `whisper` CLI | `medium` | 20-40 分钟——**跳过，用 `small` 或视觉模式** |
| CPU + 只有 `openai-whisper` | `whisper` CLI | `tiny` 或 `small` | 2-5 分钟 |
| 5 分钟内无转录或无工具 | 视觉模式 + OCR | 无 | N/A |

**时间预算规则**：预算 = `max(5 分钟, 2 分钟 × 音频时长(分钟)/10)`。例如 25 分钟音频 → `max(5, 2×2.5) = 5` 分钟。但实际上 small 模型在 CPU 上转录 25 分钟中文约需 10--15 分钟——预算公式给出的是**最激进下限**，实际应给 2--3× 余量。从 `transcribe()` 调用起算（不含模型加载）。

> **macOS 注意**：`timeout` 命令在 macOS 上默认不存在，需 `brew install coreutils` 安装 GNU `gtimeout`。若未安装，用 Python 的 `subprocess.Popen` + `signal.SIGALRM` 实现超时（见下方模板）。

**进度判断的核心原则**：不要以"SRT 文件是否存在"判断转录是否在工作——如果 transcribe.py 把全部 segment 收集完才一次性写盘，SRT 会全程不存在。正确的做法是**流式写入 SRT**（每产出一个 segment 立刻追加并 flush），agent 用 `wc -l sources/subtitles.srt` 检查行数是否在持续增长。只要行数在涨，无论多慢都不要 kill——转录正在正常工作。

**模型加载超时**：`transcribe()` 调用后 2 分钟内 SRT 仍为 0 字节，模型加载可能卡死，kill 并回退。

> 注意：上面"预算"是总时长上限（如 30 分钟音频预算 6 分钟）。简单粗暴用 `timeout` 命令比"中途健康检查"更可靠——faster-whisper 的同步 API 不支持中途查询进度。

**CPU-only Mac 注意**：`medium` 模型在 CPU 上转 10 分钟中文音频要 20-40 分钟。Mac 无 GPU 时默认 `small`/`tiny` 或走视觉模式。

**SSL 变通**：模型下载报 `SSL: CERTIFICATE_VERIFY_FAILED` 时，运行 `/Applications/Python\ 3.12/Install\ Certificates.command`，或用 `faster-whisper`（依赖 `huggingface_hub`，SSL 路径不同）。

---

## 目标

从 Bilibili URL 产出专业中文讲义 PDF。

输出必须：
- 用视频的实际教学内容，而非纯字幕转录
- 把视频原始封面放在 `.tex` 和 PDF 首页（可用时）
- 包含所有必要的高价值关键帧作为图，不加冗余截图
- 以最终综合章节结尾，含讲者实质性的总结讨论 + 自己蒸馏的要点
- 用 `\section{...}` 和 `\subsection{...}` 组织结构
- 是从 `\documentclass` 到 `\end{document}` 的完整 `.tex` 文档
- 成功编译为 PDF

---

## 源获取

### 错误处理（视频不可用）

yt-dlp 下载/元数据获取失败时，先检查错误信息区分原因：
- **网络问题**（timeout / connection refused）→ 重试 1-2 次，仍失败时提示用户检查网络
- **cookies 缺失**（403 / login required）→ 提示用户在浏览器登录 B 站后用 `--cookies-from-browser chrome`
- **视频不可用**（404 / video unavailable / 私享 / 审核中）→ 报告用户并退出，不要重试
- **年龄限制**（B 站少见，YouTube 常见）→ 用 `--cookies-from-browser chrome`

### 元数据检查

1. 先检查视频元数据。优先标题、章节、时长、封面可用性、字幕可用性。

   ```bash
   yt-dlp --print "%(title)s|%(description)s|%(duration)s|%(thumbnail)s|%(chapters)s|%(subtitles)s" --skip-download "<URL>"
   ```

   **重要——B 站字幕元数据不可靠**：`--print subtitles` 经常返回 `NA` 即使 CC 字幕实际可下载（ai-zh 轨观察到）。**无论元数据结果如何，都要尝试 CC 字幕下载**（下方 Priority 1）。确认字幕缺失的唯一方法是尝试下载并检查 `.srt` 是否生成。

2. 检测分P 视频。列出所有 P 并问用户处理哪些 P。**多 P 时每个 P 独立工作目录** `video/<标题>-part<n>/`（与 youtube-render-pdf 统一命名），各自产出独立 PDF，互不干扰。单 P 时工作目录就是 `video/<标题>/`。

3. **下载后验证实际时长**（本步骤的执行时机在"视频和封面下载"小节之后，不是现在执行）。yt-dlp 元数据时长可能不准（观察到元数据报 59 分钟，实际 104 分钟）。视频下载完成后用 ffprobe 交叉检查：
   ```bash
   # 在工作目录下执行（sources/video.mp4 已存在时）
   ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 sources/video.mp4
   ```
   差超 10% 时用 ffprobe 值并重新评估内容结构。

### 工作区设置

检查元数据后，创建以视频标题命名的专用输出目录。所有后续工作在此目录内。

目录：`video/<视频标题>/`。标题含文件系统问题字符（`/`、`:`、`?`）时替换为 `-`。保留中文，不要音译。

```bash
# 从元数据取标题并清洗
TITLE="$(yt-dlp --print "%(title)s" --skip-download "<URL>" | sed 's/[/:?*"<>|]/-/g')"
mkdir -p "video/$TITLE"/{sources,figures,ocr}
cd "video/$TITLE"
```

**`<basename>` 约定**：整个 SKILL.md 中出现的 `<basename>` 指视频标题清洗后的字符串，与工作目录名（`$TITLE`）相同。`.tex` / `.pdf` 文件命名用 `<basename>.tex` / `<basename>.pdf`；但 `tex_to_md.py` 的输出文件名必须是 `index.md`（Quartz folder note 约定）。

必需内部结构：
```
video/<视频标题>/
├── cover.jpg              # 视频封面
├── <basename>.tex         # LaTeX 源文件
├── <basename>.pdf         # 编译后的 PDF
├── sources/               # 下载的原始素材
│   ├── video.mp4
│   ├── audio.wav
│   └── subtitles.srt
├── figures/               # 提取的帧和生成的图
│   ├── talk_05min.jpg
│   ├── candidates/        # 帧选择候选（用完可清理）
│   ├── dense/             # 视觉模式密集帧
│   └── scene/             # 视觉模式场景切换帧
└── ocr/                   # OCR 输出（视觉模式）
    └── frame_ocr.json
```

### 字幕获取

#### Priority 1: CC 字幕（平台内嵌）—— 目标 ≤ 30s

有手动字幕优先于自动生成。优先 `zh-Hans`、`zh-CN`、`zh`、`ai-zh` 轨。保留时间戳，图定位需要时不要过早扁平化。

```bash
yt-dlp --cookies-from-browser chrome --write-subs --sub-langs "zh-Hans,zh-CN,zh,ai-zh" --convert-subs srt \
  --skip-download -o "sources/subtitles.%(ext)s" "<URL>"
# 实际生成文件名带语言码（如 subtitles.ai-zh.srt），统一重命名：
mv sources/subtitles.*.srt sources/subtitles.srt 2>/dev/null
ls -la sources/subtitles.srt
```

`chrome` 失败时试 `safari` 或 `edge`。都失败时请用户先在浏览器登录 B 站再重试。cookies 路径几秒内成功并产出准确简体中文字幕——应在 Whisper 回退前始终尝试。

无 cookies 回退（B 站几乎必失败，但快）：
```bash
yt-dlp --write-subs --sub-langs "zh-Hans,zh-CN,zh,ai-zh" --convert-subs srt \
  --skip-download -o "sources/subtitles.%(ext)s" "<URL>"
mv sources/subtitles.*.srt sources/subtitles.srt 2>/dev/null
```

两种都试后仍无 `sources/subtitles.srt`（非空且 >100 字节）才走 Priority 2。放弃 CC 前确认下载确实失败：
```bash
# 用 wc -l 比 ls -la 更有用——能看到行数是否在增长，而不只是"文件是否存在"
wc -l sources/subtitles.srt 2>/dev/null && [ -s sources/subtitles.srt ] || echo "No non-empty SRT — CC subtitles unavailable"
```
不要用 `zh-Hans,zh-CN,zh,ai-zh` 之外的语言码重试。

**CC 成功后的退出条件**：`sources/subtitles.srt` 存在且非空（>100 字节）。

> **快捷出口**：CC 字幕到手后，**直接跳到「视频和封面下载」**，跳过 Priority 1.5/2/3 以及「环境检查」中的转录策略选择、模型缓存检查等步骤。此时字幕质量已足以支撑全部内容写作，继续检查 Whisper 模型是浪费时间。

CC 字幕质量通常优于 Whisper 转录，无需对比验证。


#### Priority 1.5: SiliconFlow ASR API 转录 —— 目标 ≤ 3 分钟总耗时

CC 字幕不可用时，优先尝试 SiliconFlow 的 ASR API（`FunAudioLLM/SenseVoiceSmall`），而非直接回退本地 Whisper。API 转录速度快、中文质量好（有标点），但时间戳精度为分块级别（5 分钟），不适合需要精确帧定位的教学视频。

**前置条件**：`~/.config/bilibili-render-pdf/siliconflow_key` 存在且有效（与 Visual API 帧评估共用同一 key）。

**工作流**：

1. 压缩音频为 MP3（32 kbps mono，降低上传大小）：
   ```bash
   ffmpeg -y -i sources/audio.wav -ac 1 -ar 16000 -b:a 32k sources/audio_compressed.mp3
   ```

2. 按自适应时长切段，逐段调用 API，组装 SRT（脚本 `.agents/skills/bilibili-render-pdf/scripts/api_transcribe.py`）。chunk size 自动计算：`min(10, max(3, duration_sec // 20))` 分钟——短视频 3 分钟/chunk 保留精细时间戳，长视频 10 分钟/chunk 减少 API 调用次数。也可手动指定：`python3 api_transcribe.py audio.wav out.srt 600`。

3. **质量对比——API vs 本地 Whisper**：

   | 维度 | SenseVoiceSmall API | 本地 Whisper (small) |
   |------|---------------------|----------------------|
   | 速度 | ~64× 实时（160 min → 2.5 min） | ~0.34× 实时（160 min → 55 min） |
   | 中文标点 | 有逗号和句号 | 无标点 |
   | 时间戳精度 | 分块级（5 min） | 逐句（毫秒级） |
   | 适用场景 | 播客/访谈/纯对话（图少） | 教学视频（幻灯片密集，需精确帧定位） |

4. **中止条件**：API key 缺失或 3 次重试均失败 → 回退 Priority 2（本地 Whisper）。不要用 `TeleAI/TeleSpeechASR` 模型——它比 SenseVoiceSmall 慢 ~10 倍且质量相当。

5. **SRT 写入完成后跳到「视频和封面下载」**，不进入 Priority 2/3。


#### Priority 2: Whisper 语音转文字 —— 目标 ≤ 5 分钟总耗时

1. 提取音频为 WAV：
   ```bash
   yt-dlp -x --audio-format wav -o "sources/audio.%(ext)s" "<URL>"
   ```

2. 按上面的[策略表](#4-转录策略选择)选工具和模型。

   **首选 `faster-whisper`**（用 Python API 而非 CLI，便于看进度）。把整个转录 + SRT 写入脚本保存为 `transcribe.py`。

   **关键：流式写入 SRT，每 segment 立刻追加 + flush**，不要收集到数组末尾再一次性写——否则转录全程 SRT 都不存在，agent 会误判为卡死。

   ```python
   # transcribe.py —— 流式写入 sources/subtitles.srt
   # 每产出一个 segment 立刻追加到 SRT 并 flush，同时打印进度到 stdout
   import sys, time
   from faster_whisper import WhisperModel

   audio_path = sys.argv[1]      # sources/audio.wav
   srt_path = sys.argv[2]        # sources/subtitles.srt
   model_size = sys.argv[3] if len(sys.argv) > 3 else "small"

   print(f"Loading {model_size} model (CPU, int8)...", flush=True)
   model = WhisperModel(model_size, device="cpu", compute_type="int8")
   print("Model loaded, starting transcription...", flush=True)
   segments, info = model.transcribe(audio_path, language="zh", beam_size=5)
   print(f"Language: {info.language} (p={info.language_probability:.3f})", flush=True)

   def fmt(ts):
       h = int(ts // 3600); m = int((ts % 3600) // 60)
       s = int(ts % 60); ms = int((ts - int(ts)) * 1000)
       return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

   start = time.time()
   # 流式写入：每 segment 立刻写盘 + flush，agent 可随时 wc -l 检查进度
   with open(srt_path, "w", encoding="utf-8") as f:
       for i, seg in enumerate(segments, 1):
           f.write(f"{i}\n{fmt(seg.start)} --> {fmt(seg.end)}\n{seg.text.strip()}\n\n")
           f.flush()  # 关键：确保 OS 立刻把数据写到磁盘
           if i % 50 == 0:
               print(f"  {i} segments, {time.time()-start:.0f}s elapsed", flush=True)

   elapsed = time.time() - start
   print(f"Done: {i} segments in {elapsed:.1f}s", flush=True)
   ```

   ```bash
   # 启动转录（不依赖 timeout——转录可能比预算公式预测的慢，见下方超时策略）
   python3 transcribe.py sources/audio.wav sources/subtitles.srt small
   ```

   **超时策略**：不要用外部 `timeout` 命令（macOS 上默认不存在，需 `brew install coreutils` 才有 `gtimeout`）。改用**观察 SRT 增长**的方式判断——在另一个终端周期性检查：

   ```bash
   # 每 30 秒检查一次 SRT 行数是否在增长
   # 只要 wc -l 的数值在涨，无论多慢都不要 kill
   while true; do
     lines=$(wc -l < sources/subtitles.srt 2>/dev/null || echo 0)
     echo "$(date +%H:%M:%S) SRT lines: $lines"
     sleep 30
   done
   ```

   **何时判定卡死**：满足以下全部条件才 kill：
   - SRT 行数连续 5 分钟没有任何增长
   - stdout 上超过 5 分钟没有新的 segment 计数输出
   - 总运行时间已经超过 `5 × 音频时长(分钟)` 秒（25 分钟音频 → 125 分钟上限）

   判定卡死后，清空 `sources/subtitles.srt` 走 Priority 3。

   **回退 `openai-whisper` CLI**（仅 `faster-whisper` 不可用时）：
   ```bash
   # 复用上面算好的 BUDGET（基于 sources/audio.wav 时长）
   timeout "$BUDGET" whisper sources/audio.wav --model small --language zh \
     --output_format srt --output_dir sources/
   # openai-whisper 输出 sources/audio.srt，统一改名
   [ -f sources/audio.srt ] && mv sources/audio.srt sources/subtitles.srt
   ```

3. **中止条件**：`timeout` 命令的退出码 124 表示超时已 kill；其他非零退出码表示转录失败。两种情况都清空 `sources/subtitles.srt` 走 Priority 3。

#### Priority 3: 视觉模式 + OCR

转录不可用或太慢时，跳过音频。用 Tesseract OCR 从视频帧提取屏幕文字。对讲者读幻灯片或注释幻灯片的讲座型视频有效。

1. **提取密集帧**（每 10 秒）：
   ```bash
   mkdir -p figures/dense
   ffmpeg -i sources/video.mp4 -vf "fps=1/10" -q:v 3 figures/dense/frame_%04d.jpg
   ```

2. **检测场景切换**找幻灯片过渡：
   ```bash
   mkdir -p figures/scene
   ffmpeg -i sources/video.mp4 -vf "select='gt(scene,0.15)'" -vsync vfr figures/scene/scene_%04d.jpg 2>&1 | grep "frame="
   ```
   `frame=0`（静态背景的 talking-head 视频常见）时回退到步骤 1 的密集帧。

3. **OCR 关键帧**——只对有实质文字内容的帧：
   ```python
   import subprocess, json, os, glob

   files = sorted(glob.glob("figures/dense/frame_*.jpg"))
   # 先每 3 帧取样评估内容密度
   for f in files[::3]:
       r = subprocess.run(["tesseract", f, "stdout", "-l", "chi_sim+eng", "--psm", "6"],
                          capture_output=True, text=True, timeout=15)
       text = r.stdout.strip()
       if len(text) > 20:  # 跳过近乎空白的帧
           # 存 {timestamp, text} 供内容组装
           pass
   ```
   - `--psm 6`：假设统一文本块（最适合幻灯片）
   - 跳过返回少于 20 字符的帧
   - 结果存 JSON 供后续内容组装

4. **组装内容时间线**：把 OCR 文字映射到近似时间戳（帧号 × 帧间隔）。用作章节边界。

5. **补充领域知识**：中文幻灯片 OCR 输出常碎片化。用视频标题、描述和你的领域知识填补语义空缺。目标是连贯讲义，不是幻灯片文字逐字转录。

### Visual API 帧评估（Priority 0.5——可用时）

`view_image` 不可用且本地 tesseract 批量评估太慢（CPU >30s/帧）时，用远程 OCR/视觉 API 评估帧质量。把帧选择从盲启发式变成数据驱动。

**前置条件**（见上面环境检查 2b）：
- `~/.config/bilibili-render-pdf/siliconflow_key` 含有效 SiliconFlow API key
- `openai` Python 包装好
- `.agents/skills/bilibili-render-pdf/scripts/frame_assess.py` 自带脚本

**帧评估模型选择**：

| 模型 | 速度 | 最适合 |
|------|------|--------|
| `deepseek-ai/DeepSeek-OCR` | ~1.5s/帧 | 纯中文幻灯片文字提取。返回原始 OCR 文本；info-score 本地从字符数算。**推荐默认。** |
| `PaddlePaddle/PaddleOCR-VL-1.5` | ~5-10s/帧 | 带 JSON 输出的结构化评估。能分类帧类型（幻灯片/代码/图表）。需要帧类型分类时用。 |
| `Qwen/Qwen3-VL-8B-Instruct` | ~3-5s/帧 | 通用视觉语言模型。混合内容（图+文+码）好。幻灯片含 OCR 会漏的图时用。 |

**工作流**：

1. 在字幕分析识别的每个关键片段内以 1 fps 提取候选帧。**关键片段** = 字幕 SRT 中讨论某个完整概念的连续时间区间，通过字幕文本的语义聚类识别（每片段 30 秒-3 分钟）。
   ```bash
   mkdir -p figures/candidates
   # 对每个片段（start_sec 到 end_sec）：
   ffmpeg -ss <start> -to <end> -i sources/video.mp4 -vf "fps=1" -q:v 2 figures/candidates/seg_N_%04d.jpg
   ```

2. 批量评估一个片段的所有候选，只保留 top-ranked 帧：
   ```bash
   # 按片段分组，每组选 Top-1（推荐：每个关键片段只留最佳帧）
   python3 "$(git rev-parse --show-toplevel)/.agents/skills/bilibili-render-pdf/scripts/frame_assess.py" \
     --batch "figures/candidates/*.jpg" --top 1 --group

   # 全局 Top-1（跨所有帧，单一片段时用）
   python3 "$(git rev-parse --show-toplevel)/.agents/skills/bilibili-render-pdf/scripts/frame_assess.py" \
     --batch "figures/candidates/seg_1_*.jpg" --top 1
   ```

   `--group` 按文件名前缀（去除 `_+N` / `_-N` 偏移后缀）自动分组，每组独立排序取 Top-N。输出为 `{"group_name": {...}, ...}` JSON 格式。

   脚本输出 JSON：`info_score` (1-5)、`char_count`、`suitable_for_notes`、提取的 `ocr_text`。score ≥3 且 `suitable_for_notes: true` 的帧适合纳入。

3. 最终 `.tex` 里，把每个片段的 top-ranked 帧复制到 `figures/`：
   ```bash
   cp figures/candidates/seg_1_0042.jpg figures/talk_arch.jpg
   ```

4. 片段 top 帧评分 <3 时跳过该片段的图（内容可能是纯 talking-head）。

**回退**：API 不可用或所有候选 <3 分时，提取片段中点的单帧继续，不做评估。帧可能非最优，但优先完成交付。

**限流**：片段多（>15）时按 5-10 个一批处理，避免 API 限流。

### 视频类型预判（CC 字幕到手后执行）

下载视频前，快速扫描字幕前 3 分钟内容，判断视频是否有幻灯片/屏幕共享：

- 搜索关键词：`PPT`、`幻灯片`、`这张图`、`如图所示`、`这个表`、`代码`、`公式` → 有则教学视频，正常走帧提取流程
- 无上述关键词 + 对话密度高 → **纯口头内容**（面试模拟、圆桌讨论、职业规划、播客访谈等）

**纯口头内容的处理捷径**：跳过 probe 帧提取、密集候选、场景检测。仅提取 1-2 张代表性场景帧（如开场/方法论阐述时点），教学内容优先用 TikZ 可视化呈现。详见「图处理」Step 0 的纯口头内容指南。

### 视频和封面下载

1. 写 `.tex` 前先获取视频原始封面，存为工作目录下的 `cover.jpg`，首页引用。

   ```bash
   # 从元数据提取封面 URL，然后：
   curl -L -o cover.jpg "<thumbnail_url>"
   ```

2. 优先最高可用视频源做图提取。探查格式选当前环境实际可下载的最高分辨率：
   ```bash
   yt-dlp -F "<URL>"  # 列格式
   ```
   B 站 1080P+ 通常需登录 cookies。720P 在 1920×1080 显示器上做图提取通常足够。

3. 下载视频用于帧提取：
   ```bash
   yt-dlp -f "bestvideo[height<=720]+bestaudio" --merge-output-format mp4 -o "sources/video.mp4" "<URL>"
   ```

   **纯口头内容捷径**：当「视频类型预判」判定为纯口头内容（访谈/播客/圆桌）时，完整视频下载性价比极低（120 分钟 ≈ 200MB 只为抽 2 帧）。改用按需下载：
   ```bash
   # 先拿音频（ASR 必需）和封面
   yt-dlp -f bestaudio -o "sources/audio.%(ext)s" "<URL>"
   curl -L -o cover.jpg "<thumbnail_url>"
   # 帧只下载需要的几秒（如开场 30s + 中点 5s），video.mp4 裁剪后留 sources/
   yt-dlp --download-sections "*30-35" -f "bestvideo[height<=720]+bestaudio" \
     --merge-output-format mp4 -o "sources/_scene_open.mp4" "<URL>"
   ffmpeg -i sources/_scene_open.mp4 -vframes 1 figures/talk_opening.jpg
   # 复用同样的 --download-sections 拿第二帧
   ```
   这样 120 分钟视频只需下载 ~5MB 而非 ~200MB。

4. 源文件留在 `video/<标题>/sources/`（不进 git，由 `.gitignore` 排除 `video/**/sources/`）。

---

## 教学内容规则

可用时从以下构建笔记：
- 视频标题和章节结构
- 视频原始封面和关键元数据
- 屏幕上的图、公式、表、图、架构幻灯片
- 字幕讲解、例子、口头强调
- 讲座中展示或描述的代码片段

跳过不贡献实际教学的内容：
- 问候、寒暄
- 赞助、频道运营（一键三连、关注投币等）
- 结束客套

讲者的结尾讨论有实际教学价值时保留（综合、局限、未来工作、权衡、建议、开放问题）。

---

## 写作规则

1. 除非用户明确要求其他语言，用中文写笔记。

2. **视频标题不做任何润色或改写**。`\notetitle` 必须原样使用 `yt-dlp --print "%(title)s"` 返回的标题，不得加空格、改标点、换说法、或缩写字句。

3. 用 `\section{...}` 和 `\subsection{...}` 组织。需要时重建教学流程，不盲目镜像字幕顺序。

4. 从 `.agents/skills/bilibili-render-pdf/assets/notes-template.tex` 开始。填元数据块（含本地封面路径），替换正文内容块。

5. 首页必须含视频原始封面（可用时）。放第一页而非埋在后面。与正文教学图视觉区分。

6. 图实质上改善讲解时使用。教学清晰需要多少图就放多少，即使整篇很多图。不优化图数量少，优化讲解覆盖和可读性。好图：关键公式、图、表、图、视觉对比、pipeline 调度、架构视图、分阶段视觉进展。

7. 不要把图片放在自定义消息框内。

8. 数学公式出现时：
   - 用 `$$...$$` 显示
   - 紧接一个扁平列表解释每个符号

9. 代码示例出现时：
   - 包在 `lstlisting` 内
   - 含描述性 `caption`

10. 内容值得时故意且反复高亮教学信号：
   - `importantbox` 用于读者必须带走的核心概念：形式定义、中心主张、关键机制总结、定理式陈述、关键算法步骤、密集讲解后的紧凑重述
   - `knowledgebox` 用于背景和旁知识：前置提醒、历史脉络、工程上下文、设计权衡、术语对比、直觉构建类比
   - `warningbox` 用于常见误解和失败点：符号重载、隐藏假设、误导启发式、易犯实现错误、因果混淆、off-by-one 推理错误、讲者对比错误直觉与正确直觉的地方
   - 不强制每节一个框；材料含多个不同教学信号时可多框
   - 每个框应带具体教学载荷而非通用强调
   - 优先放在激发它的段落、推导或例子之后
   - 常规阐述留在正常散文；框是高信号要点，不是装饰
   - 图必须留在 `importantbox`、`knowledgebox`、`warningbox` 外

11. **每个主要 `\section{...}` 以 `\subsection{本章小结}` 结尾**。
    有 1-2 个值得的外链时，在 `\section{总结与延伸}` 最后加 `\subsection{拓展阅读}`。

12. 文档以最终顶级章节 `\section{总结与延伸}` 结尾。该章节必须含：
    - 讲者实质性结尾讨论（排除例行告别）
    - 你自己结构化蒸馏的核心主张、机制、实践含义
    - 你的扩展综合：概念压缩、章节间交叉链接、忠实于视频的谨慎泛化
    - 具体要点、开放问题或下一步（材料支持时）

13. LaTeX 中不要发 `[cite]`-式占位符。

13. **LaTeX 中文标点**：`ctex` 包 UTF-8 原生处理中文标点，直接用标准中文标点。中文字符间不要用空格作词分隔（中文无词间空格）。不要用 regex 后处理注入中文标点——会在拉丁技术术语间产生尴尬结果（如逗号）。混排中英文时，中文和英文术语间放一个常规空格。

### 编译前必检结构清单

跑 `xelatex` 前确认以下**每一项**。缺一项降级输出质量：

- [ ] `\videocoverpath` 已设且 `cover.jpg` 存在
- [ ] 每个 `\section{...}`（除总结与延伸）以 `\subsection{本章小结}` 结尾
- [ ] 文档以 `\section{总结与延伸}` 结尾，含：讲者结尾 + 综合 + 具体要点
- [ ] 有外链时 `\subsection{拓展阅读}` 存在（在总结与延伸内）
- [ ] 每个 `\includegraphics` 来自视频帧的有 `\footnotetext{视频画面时间区间：HH:MM:SS--HH:MM:SS}` 在同页
- [ ] 图时间区间来自字幕对齐片段，非粗估或 ffmpeg `-ss` 值
- [ ] 无图在 `importantbox`、`knowledgebox`、`warningbox` 内
- [ ] 视频内容涉及架构/流程/流概念时，至少一个 TikZ 或脚本生成的可视化（非仅截图）；纯推导/纯代码视频可豁免
- [ ] 无 `[cite]` 占位符
- [ ] 所有 `\ref`、`\cite`、`\href` 引用已解析（PDF 无 `??`）

---

## 图处理

按必要性和教学价值选图，不按任意配额或偏稀疏的偏好。

定位候选帧时，偏召回高于精度。多看附近候选优于错过幻灯片/公式/表/图最终完整可读的那一帧。

### 帧选择工作流

0. **Probe 帧判断视频类型**（必做，控制候选密度的关键）：先提 5-6 个均匀分布的 probe 帧（如 0/20%/40%/60%/80%/100% 时长处），用 Visual API 或目视判断视频类型：
   ```bash
   # 假设时长 T 秒，提 6 个 probe 帧
   for t in 0 $((T/5)) $((2*T/5)) $((3*T/5)) $((4*T/5)) $((T-1)); do
     ffmpeg -ss $t -i sources/video.mp4 -vframes 1 -q:v 2 figures/probe_${t}.jpg 2>/dev/null
   done
   ```
   - **talking-head**（主讲人占大部分画面，PPT 偶尔出现）→ 候选密度降到 0.2-0.5 fps，只对 PPT 出现的片段做密集候选
   - **PPT/屏幕共享**（幻灯片或代码占大部分画面）→ 候选密度 1 fps，按字幕片段逐段提取
   - **混合型**（talking-head + 频繁切 PPT）→ 候选密度 1 fps，但优先选 PPT 帧

   - **纯口头内容**（模拟面试、圆桌讨论、职业规划课等无幻灯片的纯对话场景）→ 跳过密集帧提取，仅在中点提 1-2 个代表性场景帧（如开场、关键方法论阐述时刻）。教学内容主要来自字幕文字，TikZ 可视化比截图更适合承载结构化知识。


1. **定位内容跨度**：用带时间戳的字幕文件（CC 或 Whisper SRT）作主要定位器。识别对应讨论概念的片段。**关键片段识别方法**：按 60 秒窗口聚合字幕文本，agent 读聚合后的文本判断概念边界（每片段 30 秒-3 分钟）。可用 Python 脚本辅助：
   ```python
   import re
   with open('sources/subtitles.srt') as f:
       content = f.read()
   # 解析 SRT，按 60 秒窗口聚合
   blocks = re.split(r'\n\n+', content.strip())
   windows = {}
   for b in blocks:
       lines = b.split('\n')
       if len(lines) < 3: continue
       ts = lines[1]
       m = re.match(r'(\d+):(\d+):(\d+)', ts)
       sec = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3))
       window = sec // 60
       windows.setdefault(window, []).append(' '.join(lines[2:]))
   for w in sorted(windows):
       print(f"=== {w}:{(w+1):02d} ===")
       print(' '.join(windows[w])[:200])
   ```
   agent 读聚合输出后手动划分关键片段，记录 `[(start_sec, end_sec, topic), ...]`。

3. **生成密集候选**：在字幕对齐时间窗（两侧加小缓冲）内以 1-2 秒间隔提取帧。不要在猜的时间戳提单帧。
   ```bash
   ffmpeg -ss <start> -to <end> -i sources/video.mp4 -vf "fps=1" -q:v 2 figures/candidates/frame_%04d.jpg
   ```

4. **检查并下选**：用 contact sheet 或 montage 比较候选。
   ```bash
   # 首选：montage 显式字体路径（macOS）
   montage figures/candidates/*.jpg -font /System/Library/Fonts/Helvetica.ttc -geometry 320x180+2+2 -tile 5x figures/montage.jpg

   # 回退：Python/PIL montage（无字体依赖）
   ```

5. **选最有信息量的帧**：
   - 渐进 PPT 揭示：持续检查直到找到**最终完全填充状态**
   - 动画构建或白板累积：捕获端点；仅在教真正不同的步骤时加中间帧
   - 同窗内稀疏早帧 vs 密集晚帧犹豫时：晚帧实质更完整则偏好晚帧

6. **包含所有必要图**。一节内含多图可接受且常理想（视频分阶段构建想法时）。仅省略重复或低信息帧。

### 盲模式帧选择（无法看图时）

三层，按序试：

**Tier 1——Visual API 帧评估（首选）**：
用上面 **Visual API 帧评估** 的远程 OCR/视觉 API pipeline。~1.5s/帧，可靠数据驱动排名。SiliconFlow key 配置时始终用此。

**Tier 2——单帧中点提取（回退）**：
API 不可用时，每关键片段中点提一帧：
```bash
ffmpeg -ss <mid_sec> -i sources/video.mp4 -vframes 1 -q:v 2 figures/talk_topic.jpg
```
不要提 1 fps 密集候选——无快速评估法时，60-120 候选/片段是浪费（存了也不评估）。

**Tier 3——完全跳过帧（最后手段）**：
视频格式阻止帧提取或所有提取帧空白/损坏时，跳过该片段图。字幕单独可承载教学内容。无图笔记优于不完整笔记。

**本地 OCR 注意**：CPU-only Mac 上对单帧跑 `tesseract chi_sim` **不推荐**盲模式批量评估——2+ 分钟/帧，100+ 候选跨 8-10 片段 >3 小时。用 API（Tier 1）或中点提取（Tier 2）。

---

## 图时间溯源

`.tex` 或 PDF 引用具体视频帧或其裁剪时，在同页底部脚注记录源时间区间。

- 脚注显示具体时间区间，如 `00:12:31--00:12:46`
- 区间来自**字幕对齐片段**，非模糊章节估计或 ffmpeg `-ss` 参数
- 裁剪图脚注仍指源帧或片段的原始视频时间区间
- 同一字幕区间内多帧一个清晰脚注够
- 图和时间脚注锚同页；优先 `[H]` 放置：
  ```latex
  \begin{figure}[H]
  \centering
  \includegraphics[width=\textwidth]{figures/example.jpg}
  \caption{... \protect\footnotemark}
  \end{figure}
  \footnotetext{视频画面时间区间：00:12:31--00:12:46。}
  ```

---

## 可视化

仅截图和散文不足以讲清的概念，加准确可视化。截图对架构密集技术内容很少够用。

两条路：
- 用 TikZ 或 PGFPlots 生成 LaTeX 原生可视化
- 用 Python 脚本预生成图，作为图片纳入

可视化用于：
- 流程和 pipeline 阶段
- 架构层图（如推理引擎栈）
- scaling-law 图
- 总结图和决策树
- 作为图比散文更清晰的对比

不加不教学的装饰图。

### TikZ 速查模式

**架构层图**——展示系统栈有用（推理引擎、调度层等）：
```latex
\begin{figure}[H]
\centering
\begin{tikzpicture}[node distance=0.6cm, auto]
  \tikzstyle{layer}=[rectangle, draw, minimum width=10cm, minimum height=0.8cm,
                     align=center, font=\small, rounded corners=1pt]
  \node [layer, fill=blue!10] (api)    {API / 交互层};
  \node [layer, fill=green!10, below of=api] (sched) {动态调度器 (Scheduler)};
  \node [layer, fill=yellow!10, below of=sched] (vm) {VM 块管理器 (PagedAttention)};
  \node [layer, fill=red!10, below of=vm] (backend) {模型后端适配 (Backend)};
\end{tikzpicture}
\caption{推理框架架构层级}
\end{figure}
```

**流程图**——展示推理 pipeline、数据流、算法步骤有用：
```latex
\begin{figure}[H]
\centering
\begin{tikzpicture}[node distance=2.5cm, auto]
  \tikzstyle{block}=[rectangle, draw, minimum width=2.5cm, minimum height=1cm,
                     align=center, font=\small]
  \tikzstyle{arrow}=[thick,->,>=stealth]
  \node [block] (input)  {输入 Token};
  \node [block, right of=input] (prefill) {Prefill};
  \node [block, right of=prefill] (decode) {Decode};
  \node [block, right of=decode] (output) {输出 Token};
  \draw [arrow] (input) -- (prefill);
  \draw [arrow] (prefill) -- (decode);
  \draw [arrow] (decode) -- (output);
\end{tikzpicture}
\caption{LLM 推理流水线}
\end{figure}
```

---

## 交付

工作目录 `video/<视频标题>/` 同时是成品目录。产物分两类：

**进 git**（成品，由 git 直接追踪）：

| 产物 | 位置 | 描述 |
|------|------|------|
| `.tex` 文件 | `./<basename>.tex` | 完整 LaTeX 源，`xelatex` 可编译 |
| `.pdf` 文件 | `./<basename>.pdf` | 编译 PDF（跑两次 `xelatex` 出 TOC 和交叉引用） |
| `index.md` | `./index.md` | `tex_to_md.py` 转换的 markdown，Quartz folder note |

**不进 git（临时中间产物，由 `.gitignore` 排除；交付 commit 后由 skill 自动删除，不长期驻留）：**

| 产物 | 位置 | 描述 |
|------|------|------|
| `cover.jpg` | `./cover.jpg` | 首页视频封面（可选保留，看个人偏好；若想进 git 改 .gitignore） |
| `figures/` | `./figures/` | 所有提取帧和生成可视化 |
| `sources/` | `./sources/` | 原始下载：视频、音频、字幕 |
| `ocr/` | `./ocr/frame_ocr.json` | OCR 输出时间线（视觉模式时） |

**PDF 编译**（必做，跑两次出 TOC 和交叉引用）：
```bash
# 第一次生成 .aux，第二次用 .aux 出 TOC 和交叉引用
xelatex -interaction=nonstopmode "<basename>.tex" > /dev/null 2>&1
xelatex -interaction=nonstopmode "<basename>.tex" 2>&1 | tail -30
# 编译后确认 PDF 存在且 mtime 新于 .tex
ls -la "<basename>.pdf" && [ "<basename>.pdf" -nt "<basename>.tex" ] || echo "PDF 编译失败，检查 .log"
```

**PDF 编译失败检测**：`xelatex` 退出码非 0 时检查 `.log` 文件。**PDF 编译失败时不进入 tex_to_md 转换**——先修复 .tex 重编译，确认 PDF 生成后再继续：
```bash
# 失败时看 .log 末尾的错误
tail -50 "<basename>.log" | grep -E '^! |^l\.[0-9]+'
```

**PDF 编译后必检**（每次编译都跑）：
```bash
# 检查 Missing character——非零表示 PDF 中有 □ 缺字
missing=$(grep -c "Missing character" "<basename>.log")
if [ "$missing" -gt 0 ]; then
  echo "WARNING: $missing missing glyphs — check .log for details"
  grep "Missing character" "<basename>.log" | sort -u
fi
# 确认 PDF 存在且页数合理
ls -la "<basename>.pdf" && [ "<basename>.pdf" -nt "<basename>.tex" ] || echo "COMPILE FAILED"
```
有 Missing character 时，找到缺字字符并用 `{\fallbackhei <字符>}` 包裹（模板已预定义 `\fallbackhei` 字体族），重新编译。

**Overfull/Underfull 警告是正常的**：`Overfull \hbox` / `Underfull \hbox` 是 LaTeX 排版警告（行宽溢出几 pt），不影响 PDF 生成。只有 `.log` 里以 `! ` 开头的行（如 `! Undefined control sequence`）才是真错误。判断失败的标准是：PDF 未生成，或 PDF 生成但关键章节缺失（用 `pdftotext <file>.pdf - | head -50` 抽查）。

**tex → md 转换**（前端接入需要，PDF 编译成功后执行）：

video/ 下的 .tex 在网页上无法渲染，需要转成 .md 给前端渲染。用共享脚本 `.agents/skills/_shared/scripts/tex_to_md.py`：

```bash
# 在工作目录下执行；输出文件名必须是 index.md（Quartz folder note 约定）
python3 "$(git rev-parse --show-toplevel)/.agents/skills/_shared/scripts/tex_to_md.py" \
  "<basename>.tex" "index.md"
```

转换规则：
- `\section` → `##`，`\subsection` → `###`
- `itemize` → 无序列表（`-`），`enumerate` → 有序列表（`1.`）
- `importantbox/knowledgebox/warningbox` → blockquote（`> **[重要]** **标题**`，不依赖 GFM callout 扩展）
- `quote`/`quotation`/`verse` → markdown blockquote（`> `）
- `\includegraphics` → 占位符 `[图：path — 见 PDF]`
- TikZ 块 → 跳过（占位 `[图：TikZ 可视化 — 见 PDF]`）
- `lstlisting` → 代码块
- `$...$` 和 `$$...$$` 保留（remark-math 识别），转换过程中受保护不被误伤
- `\$` 保留为 `\$`（KaTeX 尊重为字面美元符号，不会被误判为公式定界符）
- `\rightarrow` `\leq` `\alpha` 等 90+ LaTeX 符号 → Unicode（`→` `≤` `α`）；数学模式内的符号保留给 KaTeX 渲染
- `%` 开头的注释行 + 行内注释（`%` 前为空白或行首）→ 删除（保护 `\%` 转义和 `50%` 这种字面百分号）
- 元数据 → frontmatter（含 `video_url`/`video_channel`/`video_duration`/`sources` 数组）；日期归一化为 ISO 8601
- `\href{url}{text}` → `[text](url)`
- 不在 .md 末尾加 H1 标题（布局组件会渲染 `data.title`）

**转换后校验**（必做）：
```bash
wc -l index.md  # 确认非空（应 > 20 行）
head -15 index.md  # 确认 frontmatter 完整（含 --- 分隔符和必填字段）
grep -c '^## ' index.md  # 确认章节标题存在（应 ≥ 1）
```
若 `index.md` 为空或 frontmatter 缺失，检查 `.tex` 文件是否完整，重跑转换。

注：figures/ 下的图片不进 git（见 .gitignore），所以 .md 里用占位符而非 `![]()`，读者看完整图请打开 PDF。

**提交**（工作目录即成品目录，无需复制）：
```bash
# 一键交付：进入工作目录后，从编译到推送一步完成
cd "$(git rev-parse --show-toplevel)/video/<视频标题>"

# 1. 编译 PDF（两次出 TOC）
xelatex -interaction=nonstopmode "<basename>.tex" > /dev/null 2>&1
xelatex -interaction=nonstopmode "<basename>.tex" > /dev/null 2>&1

# 2. 检查 Missing character（非零 = 有缺字，需修复）
missing=$(grep -c "Missing character" "<basename>.log")
[ "$missing" -gt 0 ] && echo "WARNING: $missing missing glyphs" && grep "Missing character" "<basename>.log" | sort -u

# 3. tex → md 转换
python3 "$(git rev-parse --show-toplevel)/.agents/skills/_shared/scripts/tex_to_md.py" \
  "<basename>.tex" "index.md"

# 4. 校验 index.md
wc -l index.md && grep -c '^## ' index.md

# 5. git add + commit（+ push 仅当是 grounds）
cd "$(git rev-parse --show-toplevel)"
git add "video/<视频标题>/<basename>.tex" \
        "video/<视频标题>/<basename>.pdf" \
        "video/<视频标题>/index.md"
git commit -m "bilibili-render-pdf: <视频标题>"
# 仓库名判定（与 sync 一致）：grounds 直接 push；临时派生仓无 origin 不 push，commit 后自动 $sync 推回
if [ "$(basename "$PWD")" = "grounds" ] || git remote -v 2>/dev/null | grep -qi grounds; then
  git push
fi
# 派生仓（非 grounds）：上方不 push，commit 完成后本 skill 自动运行 $sync 推回 grounds

# 6. 清理临时中间产物（不进 git，成品 .tex/.pdf/index.md 已 commit；删除回收本地磁盘空间）
#    注意：删除后 .tex 无法直接 xelatex 重编译，需重跑「源获取 + 帧提取」流程才能再编译
rm -rf "video/<视频标题>/sources" "video/<视频标题>/figures" "video/<视频标题>/ocr"
rm -f "video/<视频标题>/cover.jpg"
```

---


## Troubleshooting

遇到错误时查阅独立排障手册：`TROUBLESHOOTING.md`（与本 SKILL.md 同目录）。涵盖 SSL 证书、Whisper 模型加载卡死、medium 模型 CPU 超时、ImageMagick 字体、SRT 写入模板、Tesseract 批量评估太慢、大 LaTeX 文件写入、DeepSeek-OCR 返回格式等问题。


## 资产

- `.agents/skills/bilibili-render-pdf/assets/notes-template.tex`：默认 LaTeX 模板，复制并填充
- `.agents/skills/bilibili-render-pdf/scripts/frame_assess.py`：Visual API 帧评估脚本
- `.agents/skills/bilibili-render-pdf/scripts/api_transcribe.py`：SiliconFlow ASR API 转录脚本（CC 字幕缺失时 Priority 1.5 用）

## Gotchas

- **SRT 必须流式写入**：不要用"收集到数组末尾一次性写"的模式写 SRT。用 `f.flush()` 每 segment 立刻落盘。否则转录全程 SRT 都不存在，agent 会误以为卡死而错误地切到视觉模式。这是最常见的翻车原因——正在正常工作的转录被当成卡死 kill 掉。
- **不要仅凭"SRT 不存在"就判卡死**：用 `wc -l sources/subtitles.srt` 检查行数是否在持续增长。small + CPU + int8 转录 25 分钟中文音频约需 10--15 分钟——如果行数在涨，耐心等到结束。
- **Mac 最优路径是 CPU + int8**：MPS 后端只支持 float32，不支持 int8/float16。实测 CPU + int8 比 MPS + float32 快 ~45%（见上方 benchmark）。不要用 `device="auto"`——它选 MPS 后配 int8 会静默失败（0 segment）。MPS + float32 可作备选（当 CPU 路径因不明原因失败时），但性能不如 CPU + int8。
- **预算公式是下限不是上限**：`max(5min, 2min × dur/10)` 给出的是最激进的最短预算，实际耗时可能是 2--3×。不要在这个时间点 kill 还在正常增长的转录。
- **macOS 没有 `timeout` 命令**：需 `brew install coreutils` 才能用 `gtimeout`。建议不用外部 timeout，改用周期性 `wc -l` 检查 SRT 增长来判断转录是否存活。
- **不确定当前机器最优设置时跑 benchmark**：用 ffmpeg 切 60s 音频片段，分别测试 `(device="cpu", compute_type="int8")` 和 `(device="auto", compute_type="float32")`，选更快的那个。但不要用 `device="auto"` 配 `int8`——MPS + int8 必定失败。


- **不接受语义触发**：用户贴 BV 链接但没说"用 bilibili-render-pdf"→ 不得自动开跑。先问"要用 bilibili-render-pdf 处理吗？"。
- **不要改写视频标题**：`\notetitle` 和工作目录名必须原样使用 yt-dlp 返回的标题。不要润色、加空格、换说法、缩写字句。标题是视频的一部分，笔记只是转述者。
- **B 站字幕元数据不可靠**：`--print subtitles` 返回 `NA` 不代表没字幕，始终尝试 CC 下载。
- **CPU-only Mac 别用 medium 模型**：20-40 分钟/10 分钟音频。用 `small`/`tiny` 或走视觉模式。
- **转录卡住要 kill，不要等**：5 分钟预算内 SRT 不增长就 kill 走视觉模式，不重试同方法。
- **帧选择偏召回高于精度**：多看候选优于错过关键帧。
- **盲模式别用本地 tesseract 批量评估**：2+ 分钟/帧，用 API 或中点提取。
- **成品必须 commit 进 git**：`.tex`+`.pdf`+`index.md` 进 git；`sources/figures/ocr/cover.jpg` 是临时中间产物（.gitignore 自动排除），**commit 后 skill 自动删除**回收本地空间。换机器后如需重编译/重看源，需重跑「源获取 + 帧提取」流程重新下载。
- **commit 之后**：grounds 必须 `git push`（否则换机器看不到）；临时派生仓 commit 后**自动 `$sync`** 推回 grounds（不要再只 commit 留本地）。

- **字体缺字**：模板已自动检测平台（macOS 用 `fontset=mac`，其他用 `fandol`）并预定义 `\fallbackhei` 回退字体族（macOS: Heiti SC）。当 PDF 中出现 □ 时：① 跑 `grep "Missing character" .log | sort -u` 找到缺字字符；② 用 `{\fallbackhei <字符>}` 包裹。AI 芯片/华为/人名等话题容易出现生僻汉字。

- **TikZ `positioning` 库遗漏**：使用 `above=...cm of node` 语法时需 `\usetikzlibrary{positioning}`，否则报 `Unknown operator 'of'`。模板已带，但从旧模板分支建笔记时可能缺。

- **纯口头内容视频不要强求帧数量**：模拟面试、圆桌讨论、职业规划课等无幻灯片的视频，帧的信息密度极低。教学重点在字幕文字——放精力在文字结构和 TikZ 可视化上，帧仅作场景锚点即可。

- **Shell 变量传入单引号 heredoc**：`<< 'LATEXEOF'` 阻止所有 shell 变量展开（包括 `$TITLE`、`$BASENAME`）。写 Python/Shell 脚本时不要依赖 env var，改用 `sys.argv[1]` 或直接拼绝对路径。工作区设置中已给出 Python 清洗标题的正确模板。

- **Shell 管道截断视频标题**：`$(yt-dlp --print title ... | sed ...)` 中的 `|` 会被 Shell 解释为管道而非传给 sed。当标题含 `|` 时，用 Python 清洗标题更可靠：`TITLE=$(python3 -c "import sys; t=sys.argv[1]; print(''.join(c if c not in "/:?*\"<>|" else "-" for c in t))" "$(yt-dlp --print "%(title)s" --skip-download "<URL>")")`。
- **`\ifdefempty` 不在 `etoolbox` 中**：笔记模板 `notes-template.tex` 里的 `\ifdefempty{\cmd}{true}{false}` 不是标准 `etoolbox` 命令。模板已修正为 `\ifx\cmd\empty ... \else ... \fi`。如果从旧模板分支建笔记，务必用新模板。

## 注意

- 工作目录与成品目录合一：`video/<标题>/`。`.tex`+`.pdf`+`index.md` 进 git；`sources/figures/ocr/cover.jpg` 由 `.gitignore` 排除不进 git。
- 成品 `.pdf` 已进 git，即最终交付物。中间产物（`sources/figures/ocr/cover.jpg`）在 commit 后由 skill 自动删除——如需重编译 PDF，需先重跑「源获取 + 帧提取」流程重新生成这些文件，再 `xelatex`。
- 关联：`AGENTS.md`、`.agents/skills/youtube-render-pdf/SKILL.md`（YouTube 版，本 skill 的简化版）
