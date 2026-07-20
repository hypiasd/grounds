---
name: project-capture
description: 用户用 $project-capture 显式触发，把当前对话中关于「当前项目」的收获（踩坑/决策/通用知识点/代码）蒸馏为多个原子洞察，各写成 project_logs/<current_project>/<note>.md。只接受手动 / `$` 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# project-capture

把**当前项目**相关的对话收获，沉淀进 `project_logs/<current_project>/`，而不是 `project/`（项目目录是独立 git 仓库，父仓库不跟踪）。一篇笔记一个概念，像 wiki 一样拆成多个原子 md。

## 触发与约束

- **只接受手动 / `$` 触发**：用户显式输入 `$project-capture` 才执行；agent 不得基于对话内容自动调用。
- 必须先处于项目模式：`current_project`（在 `.buildconfig`）已设置。未设置 → 提示用户先 `$project <name>` 并退出。

## 目标

完成时：

- 当前对话中属于「当前项目」的收获，已蒸馏为多个原子洞察；
- 每个洞察写成 `project_logs/<current_project>/<note>.md`（文件名 kebab-case，如 `retry-after-429.md`）；
- `project_logs/<current_project>/index.md` 已补上这些笔记的链接（不存在则创建，作为该项目的笔记地图）；
- 已 `git commit`（grounds 直接 push；临时派生仓 commit 后由用户 `$sync` 推回 grounds）。

## 与 learn-capture 的边界

- `learn-capture`：通用知识，沉淀进 `wiki/`，跨项目复用。
- `project-capture`：**当前项目专属**的收获（踩坑、决策、项目内通用知识点、关键代码），沉淀进 `project_logs/`。
- 一条洞察若既属于当前项目、又具备通用价值 → 用 `learn-capture` 进 `wiki/`；只在项目语境下才有意义的内容才留 `project_logs/`。

## 笔记类型与模板

回顾对话后，按以下类型把收获切成原子笔记（**一类一篇，按需产出**）：

- **改动记录**（`what-changed-*.md`）：这次改了什么 / 为什么改 / 影响面 / 验证结果。
- **困难与解决**（`fix-*.md`）：现象 → 根因诊断 → 解法 → 如何防复发（借 debugging 五步）。
- **实验记录**（`exp-*.md`）：假设 → 做法 → 结果（数据 / 现象）→ 结论（下次还这么做吗）。
- **决策**：写进 `decisions.md`（ADR：context / decision / alternatives / consequences），不在普通笔记里。
- **踩坑 / 知识点**（`note-*.md`）：非显而易见的坑、可复用的项目内知识。

> 类型边界模糊时：项目语境才有意义 → `project_logs/`；跨项目复用 → 走 `learn-capture` 进 `wiki/`。
> 每篇笔记正文建议含：背景 / 现象 / 做法 / 结论 / 坑；有代码必贴（注明语言）。

## 流程

### 一步：蒸馏 + 切分（给用户审核，不擅自写）

回顾当前对话，提取属于当前项目的收获，切成多个原子洞察。每个洞察拟定：

- 文件名（kebab-case）
- 一句话定位（属于上方哪类：改动 / 困难与解决 / 实验 / 决策 / 踩坑知识点）

列出切分方案交用户确认 / 调整。用户说"写吧 / 可以"再进入第二步。

> 不要把所有内容塞进一篇。一个概念一篇，便于日后独立检索与更新。

### 二步：归位（写多个 md）

对每个洞察，写 `project_logs/<current_project>/<note>.md`：

```markdown
---
title: <概念名>
project: <current_project>
tags: [<维度1>, <维度2>]
created: <YYYY-MM-DDTHH-MM>
updated: <YYYY-MM-DDTHH-MM>
---

<正文：背景 / 现象 / 做法 / 结论 / 坑>

<有代码必须贴代码，用 ``` 代码块，并注明语言>
```

然后更新 `project_logs/<current_project>/index.md`：

- 不存在 → 创建，标题 `# <current_project> 项目笔记`，下列链接；
- 已存在 → 追加本次新笔记的链接（按时间或主题分组均可）。

### 三步：提交

```bash
# 仓库名判定（与 sync 一致）：grounds 直接 push；临时派生仓无 origin 不 push，commit 后用户 $sync 推回 grounds
git add project_logs/<current_project>/
git commit -m "project-capture grounds: <current_project> 沉淀 <N> 条项目笔记 <YYYY-MM-DDTHH-MM>"
if [ "$(basename "$PWD")" = "grounds" ] || git remote -v 2>/dev/null | grep -qi grounds; then
  git push
fi
```

## Gotchas

- **必须处于项目模式**：`current_project` 未设置就拒绝执行，提示先 `$project <name>`。
- **绝不写进 `project/`**：项目目录是独立 git 仓库，笔记放 `project_logs/` 才随父仓库 / `$sync` 流转。
- **一篇一概念**：不要合并成单篇流水账。
- **有代码必贴**：和 learn-capture 一样，关键代码要落在笔记里。
- **不补面经**：project-capture 不做小红书/知乎/牛客搜索（那是 learn-capture 的事）。
- **project_logs 不进 lint / query**：该项目笔记不参与 wiki 互链与 orphan 检查，按项目自身地图（index.md）检索即可。

## 关联

- `AGENTS.md`（仓库地图、提交规范）
- `.agents/skills/project/SKILL.md`（进入项目、设置 current_project）
- `.agents/skills/learn-capture/SKILL.md`（通用知识走这里）
