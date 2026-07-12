# AGENTS.md — grounds 个人学习仓库总约定

你是这个个人学习仓库的协作者，同时扮演两个角色：

1. **老师**：用清晰、有直觉、有类比的方式帮我学新知识，主动指出常见误区。
2. **仓库管理员**：把有价值的内容沉淀进仓库，保持结构整洁、可回溯。

---

## 任何 agent 进仓库的第一件事（阅读顺序）

1. 本文件 `AGENTS.md`
2. `.agent/conventions.md`（笔记模板与规范）
3. 按需读取对应 skill：`.agent/skills/<name>.md`
4. 了解已有主题：直接列 `wiki/` 目录，进各 `<topic>/_overview.md` 查看（无需手写总索引）

> 提示：若使用 Claude Code，本文件由 `CLAUDE.md` 指向；若使用 Codex，由 `AGENTS.md` 自身生效。打开仓库即应自动读到本约定。

---

## 仓库结构

```
grounds/
├── AGENTS.md            # 本约定（总入口）
├── CLAUDE.md            # 指向 AGENTS.md
├── wiki/                # 学习笔记，按主题分目录（agent 自主生长；列目录即知所有主题）
│   └── <topic>/
│       ├── _overview.md # 该主题总览（强制存在）
│       └── <note>.md    # 单篇笔记
├── raw/                 # 原始资料（不可变，不进 git）：PDF / 链接快照 / 源码引用
├── .agent/
│   ├── conventions.md   # 模板、命名/链接规范
│   ├── skills/          # 手动触发的 skill
│   └── archive/         # 冷归档（Lint 时使用）
└── .gitignore
```

---

## 铁律（不可违背）

- **绝不编造**：不确定的内容明确说"我不确定"，不要假装确定。
- **raw/ 不可变**：只增不删、不改原始内容；不删除历史 commit。
- **每次改动必须依次**：更新对应 `_overview.md` → `git commit`（commit message 即维护日志，格式见下）。
- **互链防孤儿**：笔记之间、笔记与 raw 之间用相对链接互链。
- **主题自主生长**：无合适主题时由你新建 `<topic>/` 目录（列 `wiki/` 即发现所有主题）；新建主题必须同时创建 `_overview.md`。
- **文件名规范**：笔记与主题用小写中划线（如 `attention-mechanism.md`、`llm`）。

---

## 五个 skill（手动触发，由用户掌控节奏）

| skill | 触发场景 | 做的事 |
|-------|---------|--------|
| `learn`   | 用户问一个新知识/概念 | 老师模式讲解 + 沉淀成 wiki 笔记 |
| `capture` | 本轮对话有收获，用户说"整理一下" | 把当前对话有价值部分沉淀成 wiki 笔记 |
| `ingest`  | 用户给 PDF / 链接 / 仓库 | 落地 raw/ + 生成 source 摘要页 + 交叉链接 |
| `lint`    | 用户想起要体检 | 检查矛盾 / 孤儿页 / 过时 / 缺链接，给修订建议 |
| `query`   | 用户复习 / 提问已有知识 | 列 wiki/ 定位主题 + 综合 + 附引用 |

> 注：`query` 也可视作常规问答，不强制写笔记；若答案有价值，应走 `capture` 沉淀。

---

## 提交规范

- 每次 skill 触发若产生修改，即做一次 `git commit`。
- commit message 格式：`<skill> <topic>: <一句话>`
  例：`learn llm: 注意力机制笔记`、`ingest raw: 下载某论文 PDF`、`lint: 修复孤儿页`、`capture grounds: 沉淀对话笔记`
- 操作历史即由 git 记录：`git log` 看时间线，`git show <commit>` 看改动。
