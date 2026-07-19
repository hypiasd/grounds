---
alwaysApply: true
---

# grounds 仓库运行约定（Trae 桥接）

本仓库是一套「用对话学知识、用 git 管笔记」的个人学习系统，完整约定在仓库根目录 `AGENTS.md`。

**请先 Read 根目录的 `AGENTS.md` 并严格遵循其中的 Skill 调度规则**（learn / capture / lint / query / paper-learn / bilibili-render-pdf / youtube-render-pdf），再响应用户请求。

- 所有 Skill 的实现文件在 `.agents/skills/<name>/SKILL.md`，触发后必须先 Read 对应 SKILL.md。
- 本仓库的 skill 已通过 `.trae/skills`（软链到 `.agents/skills`）暴露给 Trae，可直接 `/<skill-name>` 调用或按 description 自动触发。
- 铁律：改动 `wiki/`、`paper/`、`video/` 后立即 `git commit` 并 `git push`；绝不编造；互链只发生在 `wiki/` 内。
