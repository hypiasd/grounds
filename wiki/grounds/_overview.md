# grounds 总览

## 这个主题是什么 / 学习目标
关于 `grounds` 这个个人学习仓库**本身**的设计与维护约定。记录我们如何从零设计出一个"agent 可完美维护"的轻量知识库结构，以及每一次去冗余决策背后的理由。

## 包含笔记
- [仓库设计决策与理由](repo-design-decisions.md) — 6 个去冗余决策 + 核心维护机制

## 知识脉络
从零设计本仓库的会话（见 git 历史）→ 沉淀出本主题 → 决策理由见笔记 → 最终规则落在 `AGENTS.md` / `conventions.md`

## 未解问题
- 是否需要给 `lint` 加一个定时 automation（目前定为手动触发）？
- skill 在 CodeBuddy / Claude Code / Codex 中分别如何被最顺手地触发？
- 当学习内容跨多个主题时，笔记的归属由 agent 判断，是否需要人工复核分类？
