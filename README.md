# grounds

个人学习仓库 —— 用对话学知识，用 git 管笔记。

**入口**：[`AGENTS.md`](AGENTS.md) — Claude Code 和 Codex 通用，包含完整约定与七个 skill。

## 结构

```
wiki/    学习笔记（按主题分目录）
paper/   论文笔记（按主题分目录）
video/   视频笔记成品（每个视频一个目录）
raw/     原始资料（只增不删；分 wiki/papers/videos）
```

## 十一个 Skill

- 语义触发：`learn` · `lint` · `query`
- 手动 / `$` 触发：`learn-capture` · `project-capture` · `paper-learn` · `bilibili-render-pdf` · `youtube-render-pdf`

详见 [AGENTS.md](AGENTS.md)。

## 仓库继承模型

本仓库是 agent 基类 **workBase**（`git@github.com:hypiasd/workBase.git`）的**主派生类**：workBase + `wiki/ paper/ video/ raw/ project/` + Quartz 部署。agent 行为（角色、铁律、技能、规范）由 workBase 定义，经「覆盖式同步」在派生仓间共享；详见 AGENTS.md 的「仓库继承模型」一节。临时派生仓的笔记经 `sync` 推回本仓库。
