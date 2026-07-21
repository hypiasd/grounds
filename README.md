# grounds

个人学习仓库 —— 用对话学知识，用 git 管笔记。

**入口**：[`AGENTS.md`](AGENTS.md) — Claude Code 和 Codex 通用，包含完整约定与十一个 skill。

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

## 仓库模型（单一 grounds）

本仓库是**唯一仓** `grounds`（`git@github.com:hypiasd/grounds.git`）：agent 文件（`.agents/`、`AGENTS.md` 及各 agent 软链）与全部笔记内容**同仓共存、共用一条 git 历史**。任何机器上开始工作只需：

```bash
git clone git@github.com:hypiasd/grounds.git <dir> && cd <dir>
```

agent 行为（角色、铁律、技能、规范）的完整定义见 [`AGENTS.md`](AGENTS.md)；笔记改动经 `$sync`（`git pull --rebase` + `git push`）推到 grounds 远程，并拉取其他机器的改动。
