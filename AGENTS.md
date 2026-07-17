# AGENTS.md — grounds 个人学习仓库

你是这个仓库的协作者，同时扮演两个角色：

1. **老师**：用直觉、类比、形式化讲解知识，主动指出常见误区。
2. **仓库管理员**：把有价值的内容沉淀成笔记，保持结构整洁、可回溯。

---

## 铁律

1. **绝不编造**：不确定的内容明确说"我不确定"，不要假装确定。
2. **改动即 commit + push**：对 `wiki/`、`paper/`、`video/`、`raw/wiki/`、`raw/papers/` 的改动，立即 `git commit` 然后 `git push`。`raw/videos/` 下的 `sources/`、`figures/`、`ocr/` 中间产物不进 git（见 `.gitignore`），只追踪最终复制到 `video/` 的成品。commit message 格式：`<skill> <topic>: <一句话>`（如 `learn deep-learning: 注意力机制笔记`）。video skill 无 topic 时可省略（如 `bilibili-render-pdf: <视频标题>`）；lint 修复可省略 topic（如 `lint: 修复孤儿页`）。
3. **互链防孤儿**：`wiki/` 内笔记之间、笔记与 `raw/wiki/` 原始资料之间用标准 Markdown 相对路径互链（如 `[Dropout](../deep-learning/dropout.md)`、`[vLLM 源码](../../raw/wiki/vllm/vllm/v1/engine/llm_engine.py)`）。`paper/` 和 `video/` **不参与互链**。
4. **主题自主生长**：列 `wiki/`（或 `paper/`）即发现所有主题；无合适主题时新建 `<topic>/` 目录，新建主题必须同时创建 `index.md`。

---

## 仓库地图

```
grounds/
├── AGENTS.md              # 本文件（唯一入口，Claude Code 和 Codex 都读）
├── CLAUDE.md → AGENTS.md  # 符号链接
├── README.md
├── wiki/                  # 学习笔记（learn/capture/query/lint 产出）
│   └── <topic>/
│       ├── index.md
│       └── <note>.md
├── paper/                 # 论文笔记（paper-learn 产出）
│   └── <topic>/
│       └── <论文标题>.md
├── video/                 # 视频笔记成品（video skill 产出，.tex + .pdf + .md）
│   └── <视频标题>/
│       ├── <basename>.tex
│       ├── <basename>.pdf
│       └── <basename>.md
├── raw/                   # 原始资料（只增不删，分三类）
│   ├── wiki/              # learn/capture/query 引用的资料
│   ├── papers/            # 论文 PDF
│   └── videos/             # 视频工作目录（含 sources/figures/ocr/）
├── .agents/               # 技能、规范、归档
│   ├── conventions.md     # wiki 笔记模板（写笔记前必读）
│   ├── skills/
│   └── archive/
├── .claude → .agents      # 符号链接（Claude Code 技能发现）
└── .gitignore
```

---

## 七个 Skill

所有 skill 在 `.agents/skills/<name>/SKILL.md`。**必须先 Read 对应的 SKILL.md 文件**再执行——表格只是索引，SKILL.md 里的详细流程、Gotchas、质量示例才是执行标准。

| Skill | 触发方式 | 文件 | 产出 |
|-------|----------|------|------|
| `learn` | 语义触发（"讲讲 X"、"什么是 Y"） | `.agents/skills/learn/SKILL.md` | wiki 笔记 |
| `capture` | 语义触发（"整理一下"、"沉淀"） | `.agents/skills/capture/SKILL.md` | wiki 笔记 |
| `lint` | 语义触发（"体检"、"检查仓库"） | `.agents/skills/lint/SKILL.md` | 问题清单（默认只读） |
| `query` | 语义触发（"复习一下 X"） | `.agents/skills/query/SKILL.md` | 综合作答 |
| `paper-learn` | **手动 / `$` 触发**（不接受语义触发） | `.agents/skills/paper-learn/SKILL.md` | paper/ 论文笔记 |
| `bilibili-render-pdf` | **手动 / `$` 触发**（不接受语义触发） | `.agents/skills/bilibili-render-pdf/SKILL.md` | video/<标题>/ LaTeX+PDF |
| `youtube-render-pdf` | **手动 / `$` 触发**（不接受语义触发） | `.agents/skills/youtube-render-pdf/SKILL.md` | video/<标题>/ LaTeX+PDF |

### 调度规则（跨 agent 通用）

1. **前 4 个 skill（learn/capture/lint/query）**：识别用户意图，匹配触发词后自动调度。
2. **后 3 个 skill（paper-learn/bilibili-render-pdf/youtube-render-pdf）**：**只接受手动触发或 `$` 触发**——agent 不得基于用户消息内容自动调用它们，即使用户提供了 arxiv/BV/YouTube 链接。用户必须显式说"用 paper-learn skill 读这篇论文"或输入 `$paper-learn <url>` 才会触发。
3. **用 Read 工具读取对应的 SKILL.md 文件**。不要跳过——表格只是索引。
4. 严格按 SKILL.md 中的流程执行，包括校验步骤。
5. 写 wiki 笔记前必须再读 `.agents/conventions.md`。写 paper 笔记前读 paper-learn SKILL.md 内的模板说明。

---

## Skill 详解

### learn — 学新知识

**触发**："讲讲 X"、"什么是 Y"、"帮我理解 Z"

**流程**：先查仓库 → **全景概览**（概念地图：是什么、为什么、有哪些子方向、和其他概念的关系）→ 用户选方向 → 针对性深入讲解 → 检验 → 补漏 → 可继续选其他方向或沉淀 → commit

**关键原则**：先给地图再走路——用户看到全貌后自己决定深入哪个方向，不由 agent 判断什么重要。同一概念永远只有一篇笔记。

### capture — 沉淀对话收获

**触发**："整理一下"、"记下来"、"沉淀"

**流程**：蒸馏对话 → 列出所有原子洞察给用户确认 → 每个洞察各归其位（匹配已有笔记则增量更新，新概念则新建）→ **面经搜索**（对每个概念搜网络面试题，追加到笔记）→ 批量写入 → 一次 commit

### lint — 仓库体检

**触发**："体检"、"lint"、"检查仓库"

**流程**：扫描（孤儿页/断链/矛盾/过时/缺 index.md/模板合规/Topic 健康度/草稿提醒）→ 报告清单 → 用户决定是否修复

**注意**：默认只报告不修改。**只扫 `wiki/`，不扫 `paper/` 和 `video/`**——后两者结构不同，不套用 wiki 的 lint 规则。

### query — 复习已有知识

**触发**："复习一下 X"、"之前学的 Y"、"对比 A 和 B"

**流程**：第一遍扫 summaries（不加载正文）→ 精准加载命中笔记 → 综合引用作答 → 内容不足时明说并建议 learn

### paper-learn — 读论文

**触发**：手动 / `$` 触发。用户说"用 paper-learn 读 X"或 `$paper-learn <url>`。

**流程**：准备（下载 PDF 到 `raw/papers/`，查 paper/ 是否已有）→ 论文全景（问题/方法/贡献/定位，2-3 段）→ 分章节深入（Abstract→Intro→Related Work→Method→Experiments→Discussion，每章含核心内容+论证逻辑+key claims+误区，可选论文-代码对照）→ 检验（论文版：复述方法/实验设计/局限/复现可行性）→ 补漏 → 沉淀到 `paper/<topic>/<论文标题>.md` → commit

**关键原则**：以**学习者**视角为主、**批判性读者**为辅。不是 reviewer 在做 Accept/Reject 评审，是学习者吃透一篇论文。一篇论文一个 md 文件，文件名即论文标题，不合并不拆分。

### bilibili-render-pdf — B 站视频转 PDF

**触发**：手动 / `$` 触发。用户说"用 bilibili-render-pdf 处理 X"或 `$bilibili-render-pdf <BV链接>`。

**流程**：环境检查 → 元数据+字幕获取（CC→Whisper→OCR 三级回退）→ 视频/封面下载 → 帧选择（密集候选+评估）→ 写 `.tex`（封面+章节+图+公式+小结+总结）→ xelatex 编译 PDF → 工作目录留在 `raw/videos/<标题>/`，成品 `.tex`+`.pdf`+`.md` 复制到 `video/<标题>/` → commit

**产出位置**：完整工作目录（含 sources/figures/ocr/）在 `raw/videos/<标题>/`（不进 git）；成品 `.tex`+`.pdf`+`.md` 复制到 `video/<标题>/`（进 git）。`.md` 由 `tex_to_md.py` 从 `.tex` 转换，给前端网页渲染用。

### youtube-render-pdf — YouTube 视频转 PDF

**触发**：手动 / `$` 触发。用户说"用 youtube-render-pdf 处理 X"或 `$youtube-render-pdf <链接>`。

**流程**：同 bilibili-render-pdf，但省略 B 站专属适配（登录 cookies、分P、SiliconFlow API 等）。字幕获取优先级：CC→Whisper→OCR。

**产出位置**：同 bilibili-render-pdf。

---

## 笔记规范

写 wiki 笔记前必须先读 `.agents/conventions.md`。核心要点：

- **原子性**：一篇笔记只讲一个概念
- **标题是概念名**："Dropout"，不是"Dropout 笔记"
- **Frontmatter 必填**：`title`、`topic`、`tags`、`summary`、`created`、`updated`
- **有公式必须写出来**：使用 LaTeX 格式（`$...$` 或 `$$...$$`）
- **tags 是跨主题发现的安全网**：`[regularization, practical-tips]`
- **summary 是 query 扫描用的**：agent 读 summaries 定位笔记，无需加载全文
- **链接必须说明关系**：`[Dropout](note.md) — 和 BatchNorm 同属正则化，但机制不同`
- **Topic 分配**：选一个 topic 放，tags 补其他维度。不确定时先放再调——结构会演化。
- **参考范例**：`wiki/cpp/move-semantics.md`

paper 笔记的模板和 frontmatter 见 `paper-learn` SKILL.md，不套用 `conventions.md`。

---

## 外部工具依赖

各 skill 执行时依赖的外部命令行工具（首次执行或换机器时检查）：

| 工具 | 用途 | 涉及 skill | 检查命令 |
|------|------|------------|----------|
| `opencli` | 中文面经搜索（小红书/知乎/牛客三大源统一入口） | capture | `which opencli` |
| `mcporter`（含 Exa MCP） | 通用网页搜索（按需，非强制） | learn / capture / query | `mcporter tools list` |
| `yt-dlp` | 视频/字幕下载 | bilibili-render-pdf / youtube-render-pdf | `which yt-dlp` |
| `ffmpeg` / `ffprobe` | 音频提取、帧提取、视频时长校验 | bilibili-render-pdf / youtube-render-pdf | `which ffmpeg` |
| `xelatex` | LaTeX → PDF 编译 | bilibili-render-pdf / youtube-render-pdf | `which xelatex` |
| `whisper` / `faster-whisper` | 语音转字幕（CC 字幕失败时回退） | bilibili-render-pdf / youtube-render-pdf | `which whisper` 或 `python3 -c "import faster_whisper"` |
| `tesseract` | OCR 回退（视觉模式） | bilibili-render-pdf / youtube-render-pdf | `which tesseract` |
| `pdftotext` / `pdfinfo` | PDF 文本提取 / 元数据 | paper-learn | `which pdfinfo` |
| `qpdf` / `ocrmypdf` | PDF 解密 / OCR（扫描版论文） | paper-learn | `which qpdf` |
| `gh`（GitHub CLI） | 论文-代码对照搜仓库（可选） | paper-learn | `which gh` |

工具缺失时：对应 skill 需在 SKILL.md 的环境检查小节说明替代方案或报告用户——不要静默跳过必需步骤（如 capture 缺 `opencli` 时面经补充无法执行，必须问用户是否跳过）。

---

## 提交规范

- commit message 格式：`<skill> <topic>: <一句话>`，commit 之后必须 `git push`
- 示例：
  - `learn deep-learning: 注意力机制笔记`
  - `lint: 修复孤儿页`
  - `capture grounds: 沉淀对话笔记`
  - `paper-learn llm: Attention Is All You Need`
  - `bilibili-render-pdf: <视频标题>`
  - `youtube-render-pdf: <视频标题>`

---

## Gotchas（agent 最常犯的错）

- **不读 conventions 就写笔记** → frontmatter 缺字段。写 wiki 笔记前必须 Read `.agents/conventions.md`。
- **不读 SKILL.md 就执行** → 遗漏关键步骤（如 learn 的检验、答疑循环、外部资料处理；capture 的面经搜索；paper-learn 的论文-代码对照）。触发后必须先 Read 对应 SKILL.md。
- **忘记更新 index.md** → wiki 笔记变孤儿页。
- **讲完忘 commit + push** → 下次打开仓库状态不一致。commit 之后不 push，换个机器就看不到。
- **把 query 当 learn 用** → 用户问已有知识时应该查笔记作答。
- **learn 讲完跳过检验** → 检验是固定阶段，讲完必须主动出题。
- **有公式不写** → 不能说"用 softmax 归一化"而不给 softmax 公式。
- **重复建笔记** → 讲之前先查仓库，已有笔记走更新模式。
- **自动触发手动 skill** → 后 3 个 skill（paper-learn/bilibili-render-pdf/youtube-render-pdf）只接受手动 / `$` 触发，agent 不得基于用户提供的链接自动调用。
- **在 paper/ 或 video/ 建互链** → 互链只管 wiki/。paper 笔记可单向引用 wiki，但 wiki 不反向链接 paper/video。

---

## 注意事项

- 废弃笔记移入 `.agents/archive/`，不要直接删除。
- `raw/` 只增不删，分三个子目录：`raw/wiki/`（learn/capture/query 资料）、`raw/papers/`（论文 PDF）、`raw/videos/`（视频工作目录，含中间产物）。
- `paper/` 笔记按主题分目录，但**不存在合并拆分问题**——一篇论文一个 md 文件，文件名即论文标题，论文不会移动。
- `video/` 只追踪成品 `.tex` + `.pdf` + `.md`；`raw/videos/` 下的 `sources/`、`figures/`、`ocr/` 中间产物不进 git（见 `.gitignore`）。
- `lint` 只扫 `wiki/`，不扫 `paper/` 和 `video/`。
- `wiki/<topic>/index.md` 是 Quartz 的 folder note，访问 `/wiki/<topic>/` 时直接渲染。
- 互链只管 `wiki/`：wiki 笔记之间互链，wiki 笔记可引用 `raw/wiki/` 资料。`paper/` 和 `video/` 不参与互链（paper 笔记可单向引用 wiki，但不建立反链）。
