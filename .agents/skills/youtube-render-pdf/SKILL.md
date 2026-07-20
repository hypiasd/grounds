---
name: youtube-render-pdf
description: 用户手动或用 `$youtube-render-pdf <链接>` 触发，把一个 YouTube 视频（讲座/教程/技术演讲）转换成结构化中文 LaTeX 笔记并编译为 PDF。不接受语义触发——即使用户贴了 YouTube 链接，没有显式调用本 skill 也不得自动启动。工作目录与成品目录合一，都在 video/<标题>/，无复制步骤。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# youtube-render-pdf

把一个 YouTube 视频转成完整可编译的 `.tex` 笔记 + 渲染好的 PDF。

本 skill 是 `bilibili-render-pdf` 的 YouTube 简化版，省略 B 站专属适配（登录 cookies、分P、SiliconFlow API 等）。字幕获取优先级：CC→Whisper→OCR。

## 何时用（触发）

**只接受手动触发**：
- 用户明确说"用 youtube-render-pdf 处理 X"、"走 youtube-render-pdf"
- 用户输入 `$youtube-render-pdf <链接>`

**不得自动触发**：即使用户贴了 YouTube 链接，没有显式调用本 skill，agent 不得自行启动。可以先问"要用 youtube-render-pdf 处理吗？"。

## 目标（完成时仓库应处于的状态）

- `video/<视频标题>/` 是工作目录与成品目录合一的单一目录，包含：
  - `.tex` + `.pdf` + `index.md`（进 git）
  - `cover.jpg`、`sources/`、`figures/`、`ocr/`（不进 git，由 `.gitignore` 排除）
- 已 `git commit`（**仅 grounds 才 push**），commit message：`youtube-render-pdf: <视频标题>`

---

## 环境检查（首先运行）

下载任何内容前，先确定最快的内容提取路径。

### 1. 硬件检查

```bash
python3 -c "import torch; gpu = torch.cuda.is_available() or torch.backends.mps.is_available(); print('GPU available:', gpu)" 2>/dev/null || echo "torch not available"
sysctl -n hw.ncpu  # CPU 核心数
```

- **GPU 可用**（CUDA 或 MPS）：用更大更快的 Whisper 模型。Mac Apple Silicon 上 MPS 对 faster-whisper 加速有限，仍优先 `small` 模型。
- **仅 CPU（Mac 常见）**：优先小模型或视觉模式

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

### 3. 模型缓存检查

```bash
ls ~/.cache/whisper/                                                  # 缓存的 OpenAI Whisper 模型
ls ~/.cache/huggingface/hub/models--Systran--faster-whisper-*/        # 缓存的 faster-whisper 模型
```

### 4. 转录策略选择

基于检查结果选**一个**策略并坚持。

| 条件 | 工具 | 模型 | 预期时间（10 分钟音频，CPU） |
|------|------|------|------------------------------|
| GPU 可用 | `faster-whisper` | `medium` 或 `large-v3` | ~30s |
| CPU + `faster-whisper` 可用 | `faster-whisper` | `small`, `int8` | 1-3 分钟 |
| CPU + 只有 `openai-whisper` | `whisper` CLI | `tiny` 或 `small` | 2-5 分钟 |
| 5 分钟内无转录或无工具 | 视觉模式 + OCR | 无 | N/A |

**时间预算规则**：预算 = `max(5 分钟, 2 分钟 × 音频时长/10)`。用 `timeout` 命令包裹 `transcribe.py` 调用，超时直接 kill 进程走视觉模式。faster-whisper 的 `transcribe()` 是同步阻塞 API（返回 generator，迭代才产出），不能"每 30 秒检查 SRT 增长"做中止条件。

**CPU-only Mac 注意**：`medium` 模型在 CPU 上转 10 分钟音频要 20-40 分钟。Mac 无 GPU 时默认 `small`/`tiny` 或走视觉模式。

---

## 目标

从 YouTube URL 产出专业中文讲义 PDF。

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

1. 先检查视频元数据。优先标题、章节、时长、封面可用性、字幕可用性。
   ```bash
   yt-dlp --print "%(title)s|%(description)s|%(duration)s|%(thumbnail)s|%(chapters)s|%(subtitles)s" --skip-download "<URL>"
   ```

2. 优先最高可用视频源做图提取。探查格式选当前环境实际可下载的最高分辨率：
   ```bash
   yt-dlp -F "<URL>"
   ```

3. 写 `.tex` 前先获取视频原始封面，存为工作目录下的 `cover.jpg`。
   ```bash
   curl -L -o cover.jpg "<thumbnail_url>"
   ```

4. 优先最佳匹配字幕轨。有手动字幕优先于自动生成。保留字幕时间戳。

### 工作区设置

创建以视频标题命名的专用输出目录。所有后续工作在此目录内。

目录：`video/<视频标题>/`。标题含文件系统问题字符时替换为 `-`。保留中文，不要音译。

```bash
TITLE="$(yt-dlp --print "%(title)s" --skip-download "<URL>" | sed 's/[/:?*"<>|]/-/g')"
mkdir -p "video/$TITLE"/{sources,figures,ocr}
cd "video/$TITLE"
```

内部结构：
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
│   ├── candidates/
│   ├── dense/
│   └── scene/
└── ocr/                   # OCR 输出（视觉模式）
    └── frame_ocr.json
```

### 字幕获取

#### Priority 1: CC 字幕（平台内嵌）—— 目标 ≤ 30s

YouTube 通常有自动字幕，手动字幕优先。

```bash
yt-dlp --write-subs --write-auto-subs --sub-langs "zh-Hans,zh-CN,zh,en" --convert-subs srt \
  --skip-download -o "%(title)s.%(ext)s" "<URL>"
```

说明：`--write-auto-subs` 单独启用自动字幕（YouTube 字幕语言码不含 `auto-generated`，自动字幕必须用此标志）。无 `.srt` 文件时走 Priority 2。

#### Priority 2: Whisper 语音转文字 —— 目标 ≤ 5 分钟总耗时

1. 提取音频为 WAV：
   ```bash
   yt-dlp -x --audio-format wav -o "sources/audio.%(ext)s" "<URL>"
   ```

2. 按上面的[策略表](#4-转录策略选择)选工具和模型。

   **首选 `faster-whisper`**（用 Python API 而非 CLI）。把完整转录 + SRT 写入脚本保存为 `transcribe.py`，用 `timeout` 命令包裹执行——faster-whisper 的 `model.transcribe()` 是同步阻塞 API（返回 generator，迭代才产出），无法用"每 30 秒检查 SRT 增长"做中止条件：

   ```python
   # transcribe.py —— 完整可执行，写入 sources/subtitles.srt
   import sys
   from faster_whisper import WhisperModel

   audio_path = sys.argv[1]      # sources/audio.wav
   srt_path = sys.argv[2]        # sources/subtitles.srt
   model_size = sys.argv[3] if len(sys.argv) > 3 else "small"

   model = WhisperModel(model_size, device="cpu", compute_type="int8")
   segments, info = model.transcribe(audio_path, language="zh", beam_size=5)

   def fmt(ts):
       h = int(ts // 3600); m = int((ts % 3600) // 60)
       s = int(ts % 60); ms = int((ts - int(ts)) * 1000)
       return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

   with open(srt_path, "w", encoding="utf-8") as f:
       for i, seg in enumerate(segments, 1):
           f.write(f"{i}\n{fmt(seg.start)} --> {fmt(seg.end)}\n{seg.text.strip()}\n\n")
   ```

   ```bash
   # 用 timeout 包裹，超时直接 kill 走 Priority 3
   # BUDGET 按预算规则 max(5min, 2min × 音频时长/10) 计算
   AUDIO_DUR=$(ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 sources/audio.wav)
   AUDIO_DUR_INT=${AUDIO_DUR%.*}
   BUDGET=$(( AUDIO_DUR_INT * 12 / 10 ))   # 2min × dur/10 = 12s × dur
   [ "$BUDGET" -lt 300 ] && BUDGET=300     # 下限 5 分钟
   timeout "$BUDGET" python3 transcribe.py sources/audio.wav sources/subtitles.srt small
   if [ $? -eq 124 ]; then
     echo "Whisper 超时，回退到 Priority 3"
     rm -f sources/subtitles.srt
   fi
   ```

   **回退 `openai-whisper` CLI**（仅 `faster-whisper` 不可用时，同样用 timeout 包裹）：
   ```bash
   # 复用上面算好的 BUDGET（基于 sources/audio.wav 时长）
   timeout "$BUDGET" whisper sources/audio.wav --model small --language zh \
     --output_format srt --output_dir sources/
   [ -f sources/audio.srt ] && mv sources/audio.srt sources/subtitles.srt
   ```

3. **中止条件**：`timeout` 命令退出码 124 表示超时已 kill；其他非零退出码表示转录失败。两种情况都清空 `sources/subtitles.srt` 走 Priority 3。

#### Priority 3: 视觉模式 + OCR

转录不可用或太慢时，跳过音频。用 Tesseract OCR 从视频帧提取屏幕文字。

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
   `frame=0` 时回退到步骤 1 的密集帧。

3. **OCR 关键帧**——只对有实质文字内容的帧。

### 视频下载

```bash
yt-dlp -f "bestvideo[height<=720]+bestaudio" --merge-output-format mp4 -o "sources/video.mp4" "<URL>"
```

源文件留在 `video/<标题>/sources/`（不进 git，由 `.gitignore` 排除 `video/**/sources/`）。

### 下载后验证实际时长

yt-dlp 元数据时长可能不准（YouTube 直播录像、首播后编辑、章节错位等情况）。视频下载完成后用 ffprobe 交叉检查（与 bilibili-render-pdf SKILL.md 一致）：

```bash
ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 sources/video.mp4
```

差超 10% 时用 ffprobe 值并重新评估内容结构（probe 帧位置、字幕窗口分配都依赖正确时长）。

---

## 教学内容规则

可用时从以下构建笔记：
- 视频标题和章节结构
- 视频原始封面和关键元数据
- 屏幕上的图、公式、表、图、架构幻灯片
- 字幕讲解、例子、口头强调
- 讲座中展示或描述的代码片段

跳过不贡献实际教学的内容：
- 问候、寒暄、赞助、频道运营、结束客套

讲者的结尾讨论有实际教学价值时保留（综合、局限、未来工作、权衡、建议、开放问题）。

---

## 写作规则

1. 除非用户明确要求其他语言，用中文写笔记。

2. 用 `\section{...}` 和 `\subsection{...}` 组织。需要时重建教学流程，不盲目镜像字幕顺序。

3. 从 `.agents/skills/youtube-render-pdf/assets/notes-template.tex` 开始。填元数据块（含本地封面路径），替换正文内容块。

4. 首页必须含视频原始封面（可用时）。放第一页而非埋在后面。与正文教学图视觉区分。

5. 图实质上改善讲解时使用。教学清晰需要多少图就放多少。好图：关键公式、图、表、图、视觉对比、pipeline 调度、架构视图、分阶段视觉进展。

6. 不要把图片放在自定义消息框内。

7. 数学公式出现时：
   - 用 `$$...$$` 显示
   - 紧接一个扁平列表解释每个符号

8. 代码示例出现时：
   - 包在 `lstlisting` 内
   - 含描述性 `caption`

9. 内容值得时故意且反复高亮教学信号：
   - `importantbox` 用于读者必须带走的核心概念：形式定义、中心主张、关键机制总结、定理式陈述、关键算法步骤、密集讲解后的紧凑重述
   - `knowledgebox` 用于背景和旁知识：前置提醒、历史脉络、工程上下文、设计权衡、术语对比、直觉构建类比
   - `warningbox` 用于常见误解和失败点：符号重载、隐藏假设、误导启发式、易犯实现错误、讲者对比错误直觉与正确直觉的地方
   - 不强制每节一个框；材料含多个不同教学信号时可多框
   - 图必须留在 `importantbox`、`knowledgebox`、`warningbox` 外

10. **每个主要 `\section{...}` 以 `\subsection{本章小结}` 结尾**。
    有 1-2 个值得的外链时，在 `\section{总结与延伸}` 最后加 `\subsection{拓展阅读}`。

11. 文档以最终顶级章节 `\section{总结与延伸}` 结尾。该章节必须含：
    - 讲者实质性结尾讨论（排除例行告别）
    - 你自己结构化蒸馏的核心主张、机制、实践含义
    - 你的扩展综合：概念压缩、章节间交叉链接、忠实于视频的谨慎泛化
    - 具体要点、开放问题或下一步（材料支持时）

12. LaTeX 中不要发 `[cite]`-式占位符。

13. **LaTeX 中文标点**：`ctex` 包 UTF-8 原生处理中文标点，直接用标准中文标点。中文字符间不要用空格作词分隔。混排中英文时，中文和英文术语间放一个常规空格。

### 编译前必检结构清单

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

按必要性和教学价值选图，不按任意配额或偏稀疏的偏好。定位候选帧时，偏召回高于精度。

### 帧选择工作流

1. **定位内容跨度**：用带时间戳的字幕文件作主要定位器。识别对应讨论概念的片段。

2. **生成密集候选**：在字幕对齐时间窗内以 1-2 秒间隔提取帧。
   ```bash
   ffmpeg -ss <start> -to <end> -i sources/video.mp4 -vf "fps=1" -q:v 2 figures/candidates/frame_%04d.jpg
   ```

3. **检查并下选**：用 contact sheet 或 montage 比较候选。
   ```bash
   montage figures/candidates/*.jpg -font /System/Library/Fonts/Helvetica.ttc -geometry 320x180+2+2 -tile 5x figures/montage.jpg
   ```

4. **选最有信息量的帧**：
   - 渐进 PPT 揭示：持续检查直到找到**最终完全填充状态**
   - 动画构建或白板累积：捕获端点；仅在教真正不同的步骤时加中间帧

5. **包含所有必要图**。一节内含多图可接受且常理想。

### 盲模式帧选择（无法看图时）

**Tier 1——单帧中点提取**：
```bash
ffmpeg -ss <mid_sec> -i sources/video.mp4 -vframes 1 -q:v 2 figures/talk_topic.jpg
```
不要提 1 fps 密集候选——无快速评估法时是浪费。

**Tier 2——完全跳过帧（最后手段）**：
视频格式阻止帧提取或所有提取帧空白/损坏时，跳过该片段图。字幕单独可承载教学内容。

**本地 OCR 注意**：CPU-only Mac 上对单帧跑 `tesseract chi_sim` 不推荐盲模式批量评估——2+ 分钟/帧。用中点提取。

---

## 图时间溯源

`.tex` 或 PDF 引用具体视频帧时，在同页底部脚注记录源时间区间。

- 脚注显示具体时间区间，如 `00:12:31--00:12:46`
- 区间来自**字幕对齐片段**，非模糊章节估计或 ffmpeg `-ss` 参数
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

仅截图和散文不足以讲清的概念，加准确可视化。两条路：
- 用 TikZ 或 PGFPlots 生成 LaTeX 原生可视化
- 用 Python 脚本预生成图，作为图片纳入

可视化用于：流程、架构层图、scaling-law 图、总结图、对比图。不加不教学的装饰图。

TikZ 速查模式见 `bilibili-render-pdf` SKILL.md。

---

## 交付

工作目录 `video/<视频标题>/` 同时是成品目录。产物分两类：

**进 git**（成品，由 git 直接追踪）：

| 产物 | 位置 | 描述 |
|------|------|------|
| `.tex` 文件 | `./<basename>.tex` | 完整 LaTeX 源，`xelatex` 可编译 |
| `.pdf` 文件 | `./<basename>.pdf` | 编译 PDF（跑两次 `xelatex`） |
| `index.md` | `./index.md` | `tex_to_md.py` 转换的 markdown，Quartz folder note |

**不进 git**（中间产物，由 `.gitignore` 排除 `video/**/sources/`、`video/**/figures/`、`video/**/ocr/`、`video/**/*.wav`、`video/**/*.mp4`、`video/**/*.srt`）：

| 产物 | 位置 | 描述 |
|------|------|------|
| `cover.jpg` | `./cover.jpg` | 首页视频封面（可选保留，看个人偏好；若想进 git 改 .gitignore） |
| `figures/` | `./figures/` | 所有提取帧和生成可视化 |
| `sources/` | `./sources/` | 原始下载：视频、音频、字幕 |
| `ocr/` | `./ocr/frame_ocr.json` | OCR 输出时间线（视觉模式时） |

**PDF 编译 + 失败检测**（必做，在 tex_to_md 转换前）：
```bash
# 跑两次出 TOC 和交叉引用
xelatex -interaction=nonstopmode "<basename>.tex" > /dev/null 2>&1
xelatex -interaction=nonstopmode "<basename>.tex" 2>&1 | tail -30
# 确认 PDF 存在且 mtime 新于 .tex；失败时不进入 tex_to_md 转换，先修 .tex 重编译
ls -la "<basename>.pdf" && [ "<basename>.pdf" -nt "<basename>.tex" ] || {
  echo "PDF 编译失败，检查 .log"
  tail -50 "<basename>.log" | grep -E '^! |^l\.[0-9]+'
  exit 1
}
```

**Overfull/Underfull 警告是正常的**：`Overfull \hbox` / `Underfull \hbox` 是 LaTeX 排版警告，不影响 PDF 生成。只有 `.log` 里以 `! ` 开头的行才是真错误。

**tex → md 转换**（前端接入需要，PDF 编译成功后执行）：

video/ 下的 .tex 在网页上无法渲染，需要转成 .md 给前端渲染。用共享脚本 `.agents/skills/_shared/scripts/tex_to_md.py`：

```bash
# 在工作目录下执行；输出文件名必须是 index.md（Quartz folder note 约定）
python3 "$(git rev-parse --show-toplevel)/.agents/skills/_shared/scripts/tex_to_md.py" \
  "<basename>.tex" "index.md"
```

转换规则同 bilibili-render-pdf（见其 SKILL.md）。注：figures/ 下的图片不进 git，.md 里用占位符，读者看完整图请打开 PDF。

**提交**（工作目录即成品目录，无需复制）：
```bash
# 显式 add 进 git 的文件（避免误带 sources/figures/ocr/cover.jpg）
cd "$(git rev-parse --show-toplevel)"
git add "video/<视频标题>/<basename>.tex" \
        "video/<视频标题>/<basename>.pdf" \
        "video/<视频标题>/index.md"
git commit -m "youtube-render-pdf: <视频标题>"
# 仓库名判定（与 sync 一致）：是 grounds 才 push；临时派生仓无 origin，不 push，靠 $sync 推回
if [ "$(basename "$PWD")" = "grounds" ] || git remote -v 2>/dev/null | grep -qi grounds; then
  git push
fi
```

---

## Troubleshooting

详细 Troubleshooting（SSL 错误、faster-whisper 卡住、montage 字体错误、SRT 写入模板等）见 `bilibili-render-pdf` SKILL.md 的 Troubleshooting 章节——本 skill 共用同一套工具链，故障处理相同。

YouTube 特定：
- **字幕语言**：YouTube 自动字幕质量通常优于 B 站，Priority 1 成功率高
- **区域限制**：某些视频区域限制导致 yt-dlp 失败时，提示用户用 VPN
- **年龄限制**：需登录 cookies，用 `--cookies-from-browser chrome`；私享视频无法下载，报告用户并退出
- **直播录像/超长视频（>2 小时）**：按 YouTube chapters 分段处理（无章节时按 30 分钟切），每段独立工作目录 `video/<标题>-part<n>/`，各自独立转录后合并 SRT，最终产出独立 PDF 或合并为一个 PDF

---

## 资产

- `.agents/skills/youtube-render-pdf/assets/notes-template.tex`：默认 LaTeX 模板，复制并填充

## Gotchas

- **不接受语义触发**：用户贴 YouTube 链接但没说"用 youtube-render-pdf"→ 不得自动开跑。先问"要用 youtube-render-pdf 处理吗？"。
- **CPU-only Mac 别用 medium 模型**：20-40 分钟/10 分钟音频。用 `small`/`tiny` 或走视觉模式。
- **转录卡住要 kill，不要等**：用 `timeout` 命令包裹 `transcribe.py`，超预算直接 kill 走视觉模式。
- **帧选择偏召回高于精度**：多看候选优于错过关键帧。
- **盲模式别用本地 tesseract 批量评估**：2+ 分钟/帧，用中点提取。
- **成品必须 commit 进 git**：`.tex`+`.pdf`+`index.md` 进 git，`sources/figures/ocr/cover.jpg` 不进 git（.gitignore 自动排除）。换机器后需要 `video/<标题>/sources/` 等中间产物需重新下载。
- **commit 之后**：是 grounds 必须 `git push`（否则换机器看不到）；临时派生仓只 commit，靠 `$sync` 推回 grounds。

## 注意

- 工作目录与成品目录合一：`video/<标题>/`。`.tex`+`.pdf`+`index.md` 进 git；`sources/figures/ocr/cover.jpg` 由 `.gitignore` 排除不进 git。
- 如需重新编译 PDF：直接在 `video/<标题>/` 下执行 `xelatex`（前提是 `sources/`、`figures/` 还在，否则需重新下载/提取）。
- 关联：`AGENTS.md`、`.agents/skills/bilibili-render-pdf/SKILL.md`（B 站版，本 skill 的扩展版，含完整 Troubleshooting 和 Visual API 帧评估）
