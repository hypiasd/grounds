# bilibili-render-pdf Troubleshooting

本文件是主 `SKILL.md` 的附录，收录执行过程中可能遇到的常见问题和解决方案。执行失败时查这里，正常流程不需要阅读。

---

## Troubleshooting

### SSL 证书错误（下载模型时）

**症状**：`whisper` 或 `faster-whisper` 下载权重时 `SSL: CERTIFICATE_VERIFY_FAILED`。

**openai-whisper 修复**：
```bash
/Applications/Python\ 3.12/Install\ Certificates.command
```
按 Python 版本调路径。

**faster-whisper 修复**：faster-whisper 用 `huggingface_hub` 下载，证书链不同。仍失败时：
```bash
export HF_HUB_ENABLE_HF_TRANSFER=0
```

### faster-whisper 模型加载卡住（>60s 无输出）

**症状**：打印 "Loading model..." 后卡住，或脚本无输出（import/CTranslate2 原生库加载时静默崩溃）。

**提交长转录前跑 30 秒烟雾测试**（验证工具链能否加载并产出第一段转录，与上面"转录超时"是两个不同检查）：
```bash
python3 << 'PYEOF'
import time, os, sys
cache = os.path.expanduser("~/.cache/huggingface/hub/models--Systran--faster-whisper-medium/snapshots/<hash>")
print("import...", flush=True)
from faster_whisper import WhisperModel
print("load...", flush=True)
m = WhisperModel(cache, device="cpu", compute_type="int8", local_files_only=True)
print("transcribe...", flush=True)
segments, info = m.transcribe("sources/audio.wav", language="zh")
first = next(segments)
print(f"OK: {first.text[:60]}", flush=True)
PYEOF
```
30 秒内无输出 → 工具链坏（import/load 阶段就卡），直接走视觉模式，别花时间调 Python 环境。

> 区分：**烟雾测试**（30 秒）验证工具链能否启动并产出第一段；**转录超时**（预算窗口 + 每 30 秒增长检查）验证长转录是否健康推进。烟雾测试在正式转录前跑，转录超时在正式转录中跑。

**可能原因**：`faster-whisper` 尽管设了 `local_files_only=True` 仍试图连 HuggingFace Hub，或缓存快照损坏/不完整。

**修复——验证缓存并用显式路径**：
```bash
ls ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium/snapshots/*/

# 已缓存时记 hash 用显式路径：
python3 << 'PYEOF'
import os
cache = os.path.expanduser(
    "~/.cache/huggingface/hub/models--Systran--faster-whisper-medium/snapshots/<hash>"
)
from faster_whisper import WhisperModel
model = WhisperModel(cache, device="cpu", compute_type="int8", local_files_only=True)
PYEOF
```

**修复——未缓存时单独下载**：
```bash
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('Systran/faster-whisper-small')
"
```
然后用 `local_files_only=True` 重试。

### openai-whisper Medium 模型 CPU >20 分钟

CPU-only 机器预期行为。medium 模型 ~1.5GB，CPU FP32 推理慢。

**不要等**。kill 进程，任选：
- 用更小模型（`tiny` 或 `small`）
- 换 `faster-whisper`（int8 量化 CPU 显著更快）
- 走视觉模式（Priority 3）

### ImageMagick Montage macOS 字体错误

**症状**：`montage: unable to read font`。

**修复——显式指定系统字体**：
```bash
montage *.jpg -font /System/Library/Fonts/Helvetica.ttc -geometry 320x180+2+2 -tile 5x montage.jpg
```

**回退——Python/PIL**：
```python
from PIL import Image
import glob, os

files = sorted(glob.glob("candidates/*.jpg"))
cols, rows = 5, 4
thumb_w, thumb_h = 320, 180
canvas = Image.new("RGB", (cols*(thumb_w+2)+2, rows*(thumb_h+2)+2), (30,30,30))
for i, f in enumerate(files[:cols*rows]):
    img = Image.open(f).resize((thumb_w, thumb_h))
    r, c = i // cols, i % cols
    canvas.paste(img, (2+c*(thumb_w+2), 2+r*(thumb_h+2)))
canvas.save("figures/montage.jpg", quality=85)
```

### SRT 写入模板（faster-whisper）

用 `faster-whisper` Python API 时用此模板写 SRT：
```python
def fmt_ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

lines = []
for i, seg in enumerate(segments, 1):
    lines.append(f"{i}")
    lines.append(f"{fmt_ts(seg.start)} --> {fmt_ts(seg.end)}")
    lines.append(seg.text.strip())
    lines.append("")

with open("sources/subtitles.srt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
```

### 本地 Tesseract OCR 批量帧评估太慢

**症状**：CPU-only Mac 上 `tesseract frame.jpg stdout -l chi_sim+eng --psm 6` 每帧 60-120+ 秒。数百候选跨多片段批量 OCR 不可行。

**修复——改用 Visual API**：自带脚本调 `deepseek-ai/DeepSeek-OCR` 经 SiliconFlow API，~1.5s/帧。见 **Visual API 帧评估** 章节。

**备选——少提帧**：无 API 时每片段中点仅提 1 帧。无快速评估法时不要 1 fps 密集提取。

### 写大 LaTeX 文件（>400 行）

**症状**：`apply_patch` 加 `*** Add File` 每行需 `+` 前缀，500+ 行 LaTeX 不现实。

**首选——bash heredoc**：
```bash
cat > document.tex << 'LATEXEOF'
\documentclass[a4paper]{article}
... (整个 LaTeX 内容)
LATEXEOF
```
`LATEXEOF` 单引号防 shell 展开 LaTeX 反斜杠。

**备选——Python heredoc**（含特殊字符时）：
```python
python3 << 'PYEOF'
content = r''' ... '''
with open('document.tex', 'w') as f:
    f.write(content)
PYEOF
```

**拆分大文档**：700+ 行时分 2-3 部分拼接：
```bash
cat part1.tex part2.tex part3.tex > document.tex
```

### DeepSeek-OCR 返回原始文本而非 JSON

**症状**：`deepseek-ai/DeepSeek-OCR` 返回自然语言描述或带特殊 token 的 OCR 文本而非结构化 JSON。

**这是预期行为**：DeepSeek-OCR 是纯 OCR 引擎，非 chat 模型。擅长文字提取但不可靠地遵循 JSON 格式指令。

**修复——用自带脚本**：`.agents/skills/bilibili-render-pdf/scripts/frame_assess.py` 处理 API 调用和后处理（token 清理、字符计数、本地 info-score 计算）。不要裸调 API——用脚本。

**需要 JSON 格式评估时**：改用 `PaddlePaddle/PaddleOCR-VL-1.5`，有视觉语言能力能遵循结构化输出指令。代价：比 DeepSeek-OCR 慢 3-5×。

---

