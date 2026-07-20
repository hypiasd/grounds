---
name: lint
description: 用户说"体检/lint/检查仓库/有没有矛盾/孤儿页/过时内容"时触发。只读检查仓库健康度，默认只报告不修改。不要在用户没要求时用。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# lint

## 何时用（触发）
- 用户说："lint 一下"、"检查仓库"、"有没有矛盾 / 孤儿页 / 过时内容"。
- 用户想定期维护健康度。

## 目标（完成时仓库应处于的状态）
- 产出问题清单（位置 / 类型 / 建议修复）；若用户授权，已修复并 `git commit`（grounds 直接 push；临时派生仓 commit 后**自动 `$sync`** 推回）；现有内容不被破坏。

## 流程
1. **扫描（只读）**：
   - **孤儿页**：`wiki/` 下无任何入链、也不被 `index.md` 引用的笔记。**同时检查 `index.md` 内容完整性**：对比 `index.md` 的"包含笔记"列表和目录下实际 `.md` 文件，未列入的视为孤儿页（`index.md` 存在但笔记未列入 = 实际孤儿页）。
   - **缺失链接**：笔记里链接指向不存在的文件。**区分 raw/ 链接**：链接路径以 `../raw/` 或 `../../raw/` 开头的跳过断链检查（本地素材引用，本地环境可解析即可，不要当断链修掉）。
   - **重复笔记**：检查是否有两篇笔记讲同一概念。通过比对 `title` 相似度 + `tags` 重叠 + `summary` 语义近似发现。提醒用户合并。
   - **矛盾说法**：不同笔记对同一概念描述冲突。需 agent 主动比对相同 `tags` 的笔记两两读 `summary`，发现可疑冲突时加载正文核对。这是 agent 主观判断，非自动检查——不要假装扫描后报"无矛盾"。
   - **过时内容**：引用了被新资料淘汰的说法。`updated` 日期旧 ≠ 内容过时，`updated` 新 ≠ 内容不过时——这同样是 agent 主观判断，对照领域最新进展评估，不要简单按日期报。
   - **索引覆盖**：列 `wiki/` 核对每个 `<topic>/` 是否都有 `index.md`。
   - **索引一致性（防 index 漂移）**：
     - 每个 `wiki/<topic>/index.md` 的"包含笔记"列表，必须与该目录下实际 `.md` 文件（除 `index.md` 自身）**逐一对应且数量相等**；漏列某篇或多了已删的篇 → 报"索引不一致"。
     - 根 `wiki/index.md` 里每个 topic 的「（N 篇）」**必须等于** 对应 `wiki/<topic>/` 下实际笔记数；不等 → 报"根 index 篇数漂移（列 N，实际 M）"。
     - 同理覆盖 `paper/`：每个 `paper/<topic>/index.md` 的"包含论文"列表须与该目录实际 `.md` 文件一致；根 `paper/index.md` 须链接全部 `paper/*/` 主题（缺链 → 报"根 paper/index.md 缺 topic 链接"）。
   - **模板合规**（笔记 + `index.md` 都要查）：
     - 笔记：frontmatter 是否含 `title/topic/tags/summary/created/updated`；标题是否是简洁的概念名（而非"XX 笔记"或过长的句子）；链接是否说明了关系。
     - `index.md`：同样必须有 frontmatter（`title/topic/tags/summary/created/updated`），缺失会导致 Quartz folder note 渲染异常。
     - `title` vs 文件名一致性：仅对 ASCII title 做 kebab-case 比对（如 `title: Attention Mechanism` 应对应 `attention-mechanism.md`）。中文 title 跳过此项——conventions.md 要求文件名用英文 kebab-case，title 可以是中文，两者不强制对应。
   - **草稿提醒**：`status: draft` 且 `updated` 超过 30 天的笔记，提醒用户补完或删除。
   - **Topic 健康度**：
     - 单篇 topic（目录下只有 1 篇笔记）→ 建议合并到相关 topic 或加更多笔记
     - 膨胀 topic（目录下超过 15 篇笔记）→ 建议按子方向拆分
     - 空 topic（有 `index.md` 但无笔记）→ 建议删除目录或补内容
     - 标签与 topic 不一致：笔记的 `topic` 字段指向 A 但实际存放在 B 目录 → 提醒修正
2. **报告**：列出清单给用户，**先不自动改**，让用户决定。
3. **若授权修复**：更新 `index.md`、修正 frontmatter、修复断链等。先 `git status` 列出本次将要改动的文件清单给用户最后确认；显式 `git add <file1> <file2> ...`（不要 `git add -A`，避免误带其他未完成改动），然后 `git commit -m "lint: 修复 <问题摘要>"`。**仓库名判定（与 sync 一致）：grounds 直接 `git push`；临时派生仓无 origin 不 push，commit 后**自动 `$sync`** 推回 grounds。**
4. **校验（必做）**：修复后确认链接已修、`wc -l` 确认文件非空、`git status` 符合预期。

## 报告格式示例

```
## Lint 报告

### 孤儿页（0 入链）
- wiki/llm/forgotten-note.md — 建议：加入 index.md 或被其他笔记链接

### 断链
- wiki/llm/attention.md 引用了 [transformer](transformer.md) — 目标不存在

### 缺 index.md
- wiki/reinforcement-learning/ — 建议新建

### 模板合规
- wiki/llm/old-note.md — 标题是"Old Note 笔记"而非简洁概念名；缺少 `tags` 字段

### 草稿提醒
- wiki/dl/backprop.md — status: draft 已 45 天未更新

### Topic 健康度
- wiki/optimization/ — 仅 1 篇笔记，建议合并到 deep-learning/ 或补充更多笔记
- wiki/deep-learning/ — 18 篇笔记，建议按子方向拆分（如 optimization、regularization、architectures）
- wiki/empty-topic/ — 有 index.md 但无笔记，建议删除目录或补内容
- wiki/dl/dropout.md — topic 字段写的是 `deep-learning` 但文件在 `dl/` 目录下
```

## Gotchas（真实踩过的坑）

- **默认只读优先**：先报告，用户说"直接修"才改。自动修改曾引入意外破坏——agent 把"看起来冗余"的笔记删了，但那是用户刻意保留的草稿。
- **不要把指向 raw/ 的链接当"断链"修掉**：raw/ 是本地素材引用，链接在本地环境可解析即可。曾把有效的 raw 引用当断链删除，导致溯源断裂。
- **绝不删历史 commit**；删除用冷归档（`.agents/archive/`）——保留回滚可能。

## 注意
- 冷归档：确认废弃的笔记移入 `.agents/archive/`，并在原 `index.md` 注明。
- 关联：`AGENTS.md`、`.agents/conventions.md`
