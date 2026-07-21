---
name: project-capture
description: 用户用 $project-capture 显式触发，把当前对话中关于「当前项目」的收获（决策/实验/踩坑/改动），按 project 的统一结构（decisions/、experiments/、pitfalls.md、changes.md）蒸馏沉淀进 project_logs/<current_project>/，作为 M0–M5 实时白盒工作流的收尾补漏。只接受手动 / `$` 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# project-capture

把**当前项目**相关的对话收获，沉淀进 `project_logs/<current_project>/`。它是 project 技能**实时白盒工作流（M0–M5）的收尾补漏**——项目推进中 agent 已边做边写了决策卡 / 实验卡 / 踩坑卡；本技能在对话结束或阶段节点，由你手动触发，把**当时没空细化、或漏记的零散收获**再蒸馏补进**同一套结构**，而不是另搞一套。

## 触发与约束

- **只接受手动 / `$` 触发**：用户显式输入 `$project-capture` 才执行；agent 不得基于对话内容自动调用。
- 必须先处于项目模式：`current_project`（在 `.buildconfig`）已设置。未设置 → 提示用户先 `$project <name>` 并退出。

## 目标（完成时）

- 当前对话中属于「当前项目」的收获，已按类型切分并补进 project 的统一结构；
- 每个洞察落在正确位置（见下方「类型与落点」），不新建游离文件、不与 project 实时写的卡片格式冲突；
- `decisions.md` / `experiments/index.md` 索引已补对应链接；
- 已 `git commit`（grounds 直接 push；临时派生仓 commit 后由用户 `$sync` 推回 grounds）。

## 与 project 的关系（关键）

project 的 M0–M5 实时白盒工作流**已在协作中自动写**：
- M1 决策卡 → `decisions/decision-<topic>.md`
- M2 实验卡 → `experiments/exp-<slug>.md`
- M3 踩坑 → append `pitfalls.md`
- M5 能力账本 → `learning-journal.md`

本技能**不重复造结构**，只把收尾时新发现的收获，用**完全相同的卡片格式**补到上述位置。即：实时写和收尾写，**落点一致、格式一致**。

## 与 learn-capture 的边界

- `learn-capture`：通用知识，沉淀进 `wiki/`，跨项目复用。
- `project-capture`：**当前项目专属**的收获，沉淀进 `project_logs/` 的统一结构。
- 一条洞察若既属于当前项目、又具备通用价值 → 用 `learn-capture` 进 `wiki/`；只在项目语境下才有意义的内容留 `project_logs/`。

## 类型与落点（对齐 project 统一结构）

回顾对话后，按以下类型把收获切成洞察，**每类落到固定位置**：

| 类型 | 落点 | 格式 | 索引维护 |
|------|------|------|---------|
| **决策** | `decisions/decision-<topic>.md`（一篇一概念） | 决策卡：问题 / 候选方案 / 推荐+理由 / 需拍板点 / 关联 | 在 `decisions.md` 追加一行链接 |
| **实验** | `experiments/exp-<slug>.md`（一篇一概念） | 实验卡：假设 / 方法 / 度量 / 结果 / 结论 | 在 `experiments/index.md` 追加一行 |
| **踩坑 / 知识点 / 困难与解决** | append `pitfalls.md`（单文件，每坑一个 `###` 小节） | 现象 / 根因 / 解法 / 防复发 / 学到了什么 | — |
| **改动记录** | append `changes.md`（单文件，每次改动一个 `###` 小节） | 改了什么 / 为什么 / 影响面 / 验证结果 | — |
| **能力账本更新** | 更新 `learning-journal.md` 的「还不会 / 下一步」 | — | — |

> **格式一致性**：`decision-<topic>.md` 用 project M1 决策卡格式，`exp-<slug>.md` 用 project M2 实验卡格式，`pitfalls.md` 用 M3 小节格式——与 project 实时写出的卡片**完全同构**，这样同一项目里所有决策卡 / 实验卡长得一样，检索和互链不分裂。

> **为什么踩坑 / 改动用单文件 append 而非每篇一文件**：这两类高频、零散、即时性强；单文件 append 成本最低（决策日志系统原则：记录成本 < 重新讨论的痛苦才有效），符合 project M3 的「实时捕获」精神。决策 / 实验因需深度展开，仍一篇一概念独立成文件。

> **已有内联 `decisions.md` 的处理**：若项目 onboard 时已在 `decisions.md` 内联了旧格式决策（如 `vllm-plus` 的 D1–D6），新决策走 `decisions/decision-<topic>.md` 并在 `decisions.md` 追加索引行即可；旧内联内容可后续逐步迁出，不强制。

## 流程

### 一步：蒸馏 + 切分（给用户审核，不擅自写）

回顾当前对话，提取属于当前项目的收获，切成多个洞察。每个洞察拟定：
- 落点（上表四类之一）
- 文件名（decision / exp 用 kebab-case；pitfalls / changes 只需拟定小节标题）

列出切分方案交用户确认 / 调整。用户说「写吧 / 可以」再进入第二步。

> 不要把所有内容塞进一篇。决策 / 实验一篇一概念；踩坑 / 改动一个条目一个小节。

### 二步：归位（写多个位置）

对每个洞察，写到对应落点：

- **决策** → 写 `decisions/decision-<topic>.md`（决策卡格式），并在 `decisions.md` 索引表追加：`| <topic> | <一句话> | [卡片](decisions/decision-<topic>.md) |`
- **实验** → 写 `experiments/exp-<slug>.md`（实验卡格式），并在 `experiments/index.md` 表格追加一行
- **踩坑 / 知识点 / 困难** → 在 `pitfalls.md` 末尾 append 一个 `### <日期> <标题>` 小节
- **改动** → 在 `changes.md` 末尾 append 一个 `### <日期> <标题>` 小节（若文件不存在则创建，含表头说明）
- **能力账本** → 更新 `learning-journal.md` 的「还不会 / 下一步练什么」

然后确保 `project_logs/<current_project>/index.md`（项目全景）的「决策指针 / 待办」等仍准确（通常只需引用 `decisions.md`、`experiments/index.md` 即可，不必逐条列）。

### 三步：提交

```bash
git add project_logs/<current_project>/
git commit -m "project-capture grounds: <current_project> 沉淀 <N> 条项目笔记 <YYYY-MM-DDTHH-MM>"
if [ "$(basename "$PWD")" = "grounds" ] || git remote -v 2>/dev/null | grep -qi grounds; then
  git push
fi
```

## Gotchas

- **必须处于项目模式**：`current_project` 未设置就拒绝执行，提示先 `$project <name>`。
- **绝不写进 `project/`**：项目目录是独立 git 仓库，笔记放 `project_logs/` 才随父仓库 / `$sync` 流转。
- **落点必须对齐 project 统一结构**：决策进 `decisions/decision-*.md`（不是内联 `decisions.md`）、实验进 `experiments/exp-*.md`（不是根 `exp-*.md`）、踩坑进 `pitfalls.md`（不是 `note-*.md`）、改动进 `changes.md`。否则会与 project 实时写的卡片格式分裂。
- **格式同构**：decision / exp 卡片格式与 project M1 / M2 一致；不要发明新模板。
- **有代码必贴**：关键代码要落在卡片里，并注明语言。
- **不补面经**：project-capture 不做小红书 / 知乎 / 牛客搜索（那是 learn-capture 的事）。
- **project_logs 不进 lint / query**：该项目笔记不参与 wiki 互链与 orphan 检查，按项目自身地图（index.md + 各索引）检索即可。

## 关联

- `AGENTS.md`（仓库地图、提交规范）
- `.agents/skills/project/SKILL.md`（进入项目、M0–M5 白盒工作流、统一结构定义）
- `.agents/skills/learn-capture/SKILL.md`（通用知识走这里）
