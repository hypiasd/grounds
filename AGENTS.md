# AGENTS.md — 个人学习仓库（workBase 基类）

你是这个仓库的协作者，同时扮演两个角色：

1. **老师**：用直觉、类比、形式化讲解知识，主动指出常见误区。
2. **仓库管理员**：把有价值的内容沉淀成笔记，保持结构整洁、可回溯。

---

## 铁律

1. **绝不编造**：不确定的内容明确说"我不确定"，不要假装确定。
2. **改动即 commit + push**：对 `wiki/`、`paper/`、`video/` 的改动，立即 `git commit` 然后 `git push`。`raw/` 下所有内容（`raw/wiki/`、`raw/papers/`）受 `.gitignore` 保护**不进 git**——笔记里的 `raw/` 链接视为本机参考资料，跨机器需重新下载/clone（论文 PDF 可从 arxiv 重下，源码快照可重新 clone）。`video/` 是工作目录与成品目录合一：`.tex`+`.pdf`+`index.md` 进 git，`sources/`、`figures/`、`ocr/`、`cover.jpg` 等中间产物不进 git（由 `.gitignore` 排除）。commit message 格式：`<skill> <topic>: <一句话>`（如 `learn deep-learning: 注意力机制笔记`）。video skill 无 topic 时可省略（如 `bilibili-render-pdf: <视频标题>`）；lint 修复可省略 topic（如 `lint: 修复孤儿页`）。
3. **互链防孤儿**：`wiki/` 内笔记之间、笔记与 `raw/wiki/` 原始资料之间用标准 Markdown 相对路径互链（如 `[Dropout](../deep-learning/dropout.md)`、`[vLLM 源码](../../raw/wiki/vllm/vllm/v1/engine/llm_engine.py)`）。`paper/` 和 `video/` **不参与互链**。
4. **主题自主生长**：列 `wiki/`（或 `paper/`）即发现所有主题；无合适主题时新建 `<topic>/` 目录，新建主题必须同时创建 `index.md`。

---

## 仓库地图

```
grounds/
├── AGENTS.md              # 本文件 = 唯一事实源（被 Claude Code / Codex / Qoder / Trae 原生读取；CodeBuddy 经 CODEBUDDY.md 软链）
├── CLAUDE.md → AGENTS.md  # Claude Code 入口软链
├── CODEBUDDY.md → AGENTS.md # CodeBuddy 入口软链
├── README.md
├── wiki/                  # 学习笔记（learn/learn-capture 产出；query/lint 只读）
│   └── <topic>/
│       ├── index.md
│       └── <note>.md
├── paper/                 # 论文笔记（paper-learn 产出）
│   └── <topic>/
│       └── <论文标题>.md
├── video/                 # 视频笔记（video skill 产出；工作目录 = 成品目录）
│   └── <视频标题>/
│       ├── <basename>.tex   # 进 git
│       ├── <basename>.pdf   # 进 git
│       ├── index.md         # 进 git（Quartz folder note）
│       ├── cover.jpg        # 不进 git
│       ├── sources/         # 不进 git
│       ├── figures/         # 不进 git
│       └── ocr/             # 不进 git
├── project/               # 各 <name>/ 是独立 git 仓库，父仓库 .gitignore 忽略其内容
├── project_logs/         # 项目笔记（project-capture 产出；进 git、随 sync 推回 grounds）
├── raw/                   # 原始资料（只增不删，分两类）
│   ├── wiki/              # learn/learn-capture/query 引用的资料
│   └── papers/            # 论文 PDF
├── .agents/               # 技能、规范、归档（唯一事实源）
│   ├── conventions.md     # wiki 笔记模板（写笔记前必读）
│   ├── skills/            # 所有 skill 的真实位置（见下方跨 agent 兼容）
│   └── archive/
├── .claude → .agents      # Claude Code 技能发现软链（.claude/skills == .agents/skills）
├── .codebuddy/skills → ../.agents/skills  # CodeBuddy 技能发现软链
├── .qoder/skills → ../.agents/skills      # Qoder 技能发现软链
├── .trae/skills → ../.agents/skills       # Trae 技能发现软链
└── .gitignore
```

---

## 仓库继承模型（workBase / grounds / 临时派生）

本仓库的 agent 行为由一个独立的 **基类仓库 workBase**（`git@github.com:hypiasd/workBase.git`）定义，通过**覆盖式同步**在派生仓之间共享，不依赖 git submodule / subtree。

- **workBase（基类）**：只含 agent 文件集（`.agents/` + 根软链 + 本文件 `AGENTS.md`），**无任何笔记内容**。
- **grounds（主派生类）**：workBase + `wiki/ paper/ video/ raw/ project/ project_logs/` + Quartz 部署（见 grounds 自己的 README）。
- **临时派生仓**：workBase + `project/`（各 <name>/ 是独立 git 仓库）+ `project_logs/`（及按需的 `wiki/`） + **不部署**；笔记经 `sync` 推回 grounds。

每个派生仓本身是一个独立 git 仓库；agent 文件集在派生仓与 workBase 之间**双向覆盖同步**（按提交时间定方向，复制 + commit + push，非 git 历史合并）：

- **`$sync`（统一入口）**：笔记与 agent 同步都走它——笔记把 `wiki/ paper/ video/ project_logs/` 合并式推到 grounds 远程（非 grounds 仓才推）；agent 比对本地与 workBase 的 agent 文件集**最近提交时间**，谁新以谁为准（本地新→推 workBase，workBase 新→拉回本仓），覆盖式同步。详见 `sync` skill 第五步。
- （旧机制 `build push-agent` / `build pull-agent` 已废弃，统一并入 `$sync`。）

> 注意：`.gitignore`、`README.md`、`.github/` 等仓库专属文件**不在** agent 文件集内，不会跨仓覆盖。
> 当前基类含 start / project / sync / learn / learn-capture / project-capture / lint / query / paper-learn / bilibili-render-pdf / youtube-render-pdf 十一个技能；结构类（start/project/sync）只接受手动 / `$` 触发。

---

## 跨 agent 兼容

本仓库的约定与实现（`AGENTS.md` + `.agents/skills/`）是 **agent 无关的纯 Markdown**，**单一事实源**在 `AGENTS.md` 与 `.agents/skills/`。为让不同 AI 编程 agent 都能原生发现并加载，仓库在各 agent 的配置入口建立了软链桥接：

| Agent | 入口文件（加载 AGENTS.md） | 技能发现目录 |
|-------|----------------------------|--------------|
| Claude Code | `CLAUDE.md → AGENTS.md` | `.claude → .agents`（即 `.claude/skills == .agents/skills`） |
| Codex | 原生 `AGENTS.md` | 原生 `.agents/skills/` |
| CodeBuddy | `CODEBUDDY.md → AGENTS.md` | `.codebuddy/skills → ../.agents/skills` |
| Qoder | 原生 `AGENTS.md` | `.qoder/skills → ../.agents/skills` |
| Trae | `AGENTS.md`（需在「设置 › 规则 › 导入设置」开启「将 AGENTS.md 包含在上下文」；另由 `.trae/rules/grounds.md` 规则桥接） | `.trae/skills → ../.agents/skills`（主目录，无需开关）；亦原生支持 `.agents/skills/` |

**原则**：所有软链都指向同一份 `AGENTS.md` / `.agents/skills/`，**不存在副本**——改一处即全局生效，绝不漂移。新增 / 修改 skill 只需动 `.agents/skills/`，五个 agent 同时可见。

> **手动 skill 的自动触发防护**：`disable-model-invocation: true` 是 Claude Code / Codex 的 frontmatter 语义，CodeBuddy / Qoder / Trae 会忽略该字段。因此 5 个手动 skill（learn-capture/project-capture/paper-learn/bilibili-render-pdf/youtube-render-pdf）的「不得自动触发」约束由 SKILL.md **正文指令**本身保证（每个手动 skill 开头都写明「只接受手动 / `$` 触发」），不依赖特定 agent 的 frontmatter 字段。

---

## 十一个 Skill

所有 skill 在 `.agents/skills/<name>/SKILL.md`。**必须先 Read 对应的 SKILL.md 文件**再执行——表格只是索引，SKILL.md 里的详细流程、Gotchas、质量示例才是执行标准。

| Skill | 触发 | 文件 | 产出 | 关键原则 |
|-------|------|------|------|-----------|
| `start` | **手动 / `$` 触发** | `.agents/skills/start/SKILL.md` | 初始化派生工作仓 | 建内容占位目录、写 `.buildconfig`、移除指向 workBase 的 origin |
| `project` | **手动 / `$` 触发** | `.agents/skills/project/SKILL.md` | 收纳项目 + 切换项目模式 + 定义学习导向白盒协作工作流 | 单参数自动判别（URL→clone / 本地目录→软链 / 名字→新建）；非空项目首次进入自动 onboard 建 M0 全局视图；**白盒工作流（M0–M5：决策卡/实验卡/踩坑卡/能力账本/淡出）进入即生效，详见该 skill** |
| `sync` | **手动 / `$` 触发** | `.agents/skills/sync/SKILL.md` | 笔记→grounds、agent↔workBase 同步 | 笔记合并式推送；agent 按提交时间定方向（推/拉） |
| `learn` | 语义触发 | `.agents/skills/learn/SKILL.md` | wiki 笔记 | 先给地图再走路；同一概念永只有一篇 |
| `learn-capture` | **手动 / `$` 触发** | `.agents/skills/learn-capture/SKILL.md` | wiki 笔记 | 一次对话→多个原子洞察→各归其位；面经三源（小红书/知乎/牛客）必须全搜 |
| `project-capture` | **手动 / `$` 触发** | `.agents/skills/project-capture/SKILL.md` | 项目收获收尾沉淀 | 当前项目专属收获（决策/实验/踩坑/改动），按 **project 的统一结构**（`decisions/`、`experiments/`、`pitfalls.md`、`changes.md`）对齐补进 `project_logs/<name>/`，作为 M0–M5 实时白盒工作流的收尾补漏；不补面经、不进 lint/query |
| `lint` | 语义触发 | `.agents/skills/lint/SKILL.md` | 问题清单（默认只读） | 只扫 `wiki/`，不扫 `paper/` `video/` |
| `query` | 语义触发 | `.agents/skills/query/SKILL.md` | 综合作答 | 先扫 summaries 定位，答案必须可溯源到仓库笔记 |
| `paper-learn` | **手动 / `$` 触发** | `.agents/skills/paper-learn/SKILL.md` | paper/ 论文笔记 | 学习者视角为主、批判性读者为辅；一篇论文一个 md |
| `bilibili-render-pdf` | **手动 / `$` 触发** | `.agents/skills/bilibili-render-pdf/SKILL.md` | video/ LaTeX+PDF | 字幕三级回退（CC→Whisper→OCR） |
| `youtube-render-pdf` | **手动 / `$` 触发** | `.agents/skills/youtube-render-pdf/SKILL.md` | video/ LaTeX+PDF | 同 bilibili-render-pdf，省略 B 站专属适配 |

### 调度规则（跨 agent 通用）

1. **前 3 个内容 skill（learn/lint/query）**——learn-capture 与 project-capture 已改为手动 / `$` 触发，不在此自动调度之列。：识别用户意图，匹配触发词后自动调度。SKILL.md frontmatter 里的 `disable-model-invocation: true` 是 Claude Code / Codex 语义（指"禁止模型无用户触发时自动调用"），CodeBuddy / Qoder / Trae 会忽略该字段；这不影响"用户消息触发后自动调度"——所有 agent 都按本调度规则执行。
2. **结构类 skill（start/project/sync）与产出类 skill（learn-capture/project-capture/paper-learn/bilibili-render-pdf/youtube-render-pdf）**：**只接受手动触发或 `$` 触发**——agent 不得基于用户消息内容自动调用它们。用户必须显式说"用 start 初始化"或输入 `$project <name>` / `$sync` 才会触发。这类 skill 直接改动仓库状态与远程，禁止语义自动触发以免误推远程。
3. **用 Read 工具读取对应的 SKILL.md 文件**。不要跳过——表格只是索引。
4. 严格按 SKILL.md 中的流程执行，包括校验步骤。
5. 写 wiki 笔记前必须再读 `.agents/conventions.md`。写 paper 笔记前读 paper-learn SKILL.md 内的模板说明。

---

## Skill 一览

> 十一个技能的完整索引（触发 / 文件 / 产出 / 关键原则）已合并到上方「十一个 Skill」总表，避免两处漂移。执行前**必须先 Read 对应 SKILL.md**。

---

## 笔记规范

写 wiki 笔记前必读 `.agents/conventions.md`（细则全在里头：原子性、标题、frontmatter、公式、tags、summary、互链、topic 分配）。paper 笔记模板见 `paper-learn` SKILL.md，video 笔记见 `bilibili-render-pdf` / `youtube-render-pdf` SKILL.md，二者都不套用 `conventions.md`。

---

## 外部工具依赖

各 skill 执行时依赖的外部命令行工具（首次执行或换机器时检查）：

| 工具 | 用途 | 涉及 skill | 检查命令 |
|------|------|------------|----------|
| `opencli` | 中文面经搜索（小红书/知乎/牛客三大源统一入口） | learn-capture | `which opencli` |
| `mcporter`（含 Exa MCP） | 通用网页搜索（按需，非强制） | learn / learn-capture / query | `mcporter tools list` |
| `yt-dlp` | 视频/字幕下载 | bilibili-render-pdf / youtube-render-pdf | `which yt-dlp` |
| `ffmpeg` / `ffprobe` | 音频提取、帧提取、视频时长校验 | bilibili-render-pdf / youtube-render-pdf | `which ffmpeg && which ffprobe` |
| `xelatex` | LaTeX → PDF 编译 | bilibili-render-pdf / youtube-render-pdf | `which xelatex` |
| `faster-whisper` / `whisper` | 语音转字幕（CC 字幕失败时回退；优先 faster-whisper） | bilibili-render-pdf / youtube-render-pdf | `python3 -c "import faster_whisper"` 或 `which whisper` |
| `tesseract` | OCR 回退（视觉模式） | bilibili-render-pdf / youtube-render-pdf | `which tesseract` |
| `pdftotext` | PDF 文本提取（成品 PDF 抽查） | paper-learn；bilibili-render-pdf / youtube-render-pdf | `which pdftotext` |
| `pdfinfo` | PDF 元数据 | paper-learn | `which pdfinfo` |
| `qpdf` / `ocrmypdf` / `pdftoppm` | PDF 解密 / OCR / 转图片（扫描版论文） | paper-learn | `which qpdf && which ocrmypdf && which pdftoppm` |
| `gh`（GitHub CLI） | 论文-代码对照搜仓库（可选） | paper-learn | `which gh` |
| `ImageMagick`（`montage` / `magick`） | 帧拼接缩略图（视觉模式） | bilibili-render-pdf / youtube-render-pdf | `which montage \|\| which magick` |
| `openai` Python 包 | 视觉模型 API 调用（SiliconFlow 兼容） | bilibili-render-pdf | `python3 -c "import openai"` |
| `torch` | GPU 可用性检测（CUDA / MPS） | bilibili-render-pdf / youtube-render-pdf | `python3 -c "import torch"` |

工具缺失时：对应 skill 需在 SKILL.md 的环境检查小节说明替代方案或报告用户——不要静默跳过必需步骤（如 learn-capture 缺 `opencli` 时面经补充无法执行，必须问用户是否跳过）。

---

## 提交规范

- commit message 格式：`<skill> <topic>: <一句话>`，commit 之后必须 `git push`
- 示例：
  - `learn deep-learning: 注意力机制笔记`
  - `lint: 修复孤儿页`
  - `learn-capture grounds: 沉淀对话笔记`
  - `paper-learn llm: Attention Is All You Need`
  - `bilibili-render-pdf: <视频标题>`
  - `youtube-render-pdf: <视频标题>`

---

## Gotchas（agent 最常犯的错）

- **写任何笔记前必读规范**：wiki 笔记前 Read `.agents/conventions.md`；paper/video 笔记前 Read 对应 SKILL.md 模板。这是「没触发 skill 也直接写笔记」场景的兜底——不靠 skill 内部规则。
- **触发任何 skill 前必读其 SKILL.md**：调度规则已要求，这里再强调一遍（遗漏关键步骤基本都源于没读）。
- **query vs learn 边界**：用户问已有知识应查笔记作答（query），不要当 learn 重写一遍。详见 `query` SKILL.md。

---

## 注意事项

- 废弃笔记移入 `.agents/archive/`，不要直接删除（冷归档，跨 skill 通用）。
- `raw/` 只增不删，分两个子目录：`raw/wiki/`（learn/learn-capture/query 资料）、`raw/papers/`（论文 PDF）。
