---
name: paper-capture
description: 用户用 $paper-capture 显式触发，通读 paper/<topic>/<论文标题>.md，把其中「脱离本论文还有用的通用知识（概念/通用方法/原理/数学技巧/设计模式/领域共识）」萃取成 wiki/<topic>/<note>.md（paper 笔记原位只留一行链接 + 论文视角注解；wiki 笔记自包含、不反向链回 paper），并核 wiki 索引。是 paper-learn 沉淀论文笔记的收尾萃取，不重复记录。只接受手动 / `$` 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# paper-capture

`paper-learn` 把一篇论文读透、沉淀成 `paper/<topic>/<论文标题>.md`——这是**论文专属记录**：这篇论文解决了什么、提了什么方法、实验如何、局限在哪。但它里面往往裹着**通用知识**：某条领域共识、某个可复用的数学技巧、某种通用设计模式、某个已成标准的方法论——这些脱离"本篇论文"也有独立价值，本该在 `wiki/` 里跨论文、跨项目复用。

本技能是**收尾萃取**：论文笔记写完后，你手动触发，我**通读整篇 paper 笔记**，逐段判断"这段脱离本论文还有没有用？"——有用（通用知识）→ 抽成 `wiki/<topic>/<note>.md`；没用（论文专属叙事）→ 留在 paper。最后核一遍 wiki 索引。

> 一句话：**paper-learn 负责"读透并记全"，paper-capture 负责"提纯"——把论文笔记里的通用知识萃取到 wiki，让论文记录不锁死可复用内容。**

## 触发与约束

- **只接受手动 / `$` 触发**：用户显式输入 `$paper-capture [论文标题或路径]` 才执行；agent 不得基于对话内容自动调用。
- 必须先有目标论文笔记：先确认 `paper/<topic>/<论文标题>.md` 已存在（由 `paper-learn` 产出）。不存在 → 提示用户先 `$paper-learn` 该论文并退出。
- 参数：可带论文标题或 `paper/<topic>/<标题>.md` 路径；不带参则对当前会话最近处理的论文笔记操作（仍须用户显式触发）。

## 目标（完成时）

- 已**通读 paper 笔记**，对每段判定"通用（建议萃取）vs 论文专属（留 paper）"。
- 通用知识已抽成 `wiki/<topic>/<note>.md`（遵循 `.agents/conventions.md`），**wiki 笔记自包含、不反向链回 paper**。
- paper 笔记原位替换为指针 + 论文视角注解（paper→wiki 单向引用，符合"paper 可单向引用 wiki"）。
- `wiki/<topic>/index.md`（若新建 topic 还需根 `wiki/index.md`）已更新，使新笔记可见。
- 已 `git commit`（提交后 `git push origin main` 推到 grounds 远程）。

## 与 paper-learn 的关系（关键）

`paper-learn` 实时刻在跑，产出 `paper/<topic>/<论文标题>.md`，结构含 TL;DR / 核心方法 / 实验 / 局限 / 批判性思考等。

本技能**不重复写论文笔记、不新开结构**——它只读 paper 笔记、萃取出通用知识到 wiki、把 paper 原位改为指针。即：paper-learn 写、paper-capture 提纯，**落点分离（paper ↔ wiki）而非格式分裂**。

## 与 project-capture 的关系

设计完全对称，只是知识源不同：

- `project-capture`：知识源是 `project_logs/<name>/runbook.md`（项目日志）→ 萃取到 wiki。
- `paper-capture`：知识源是 `paper/<topic>/<论文标题>.md`（论文笔记）→ 萃取到 wiki。

两者都产出 wiki、都"读源 → 抽 wiki → 源留指针"。区别在源的性质（项目日志 vs 论文笔记）和互链约束（见下）。

## 互链约束（与 project-capture 的关键区别）

AGENTS.md 铁律 3：**`paper/` 不参与互链**，且 wiki 只与 wiki / `raw/wiki/` 互链。因此：

- **paper → wiki 单向引用允许**：paper 笔记原位指针可链到 wiki 笔记（这正是萃取后留下的指针）。
- **wiki → paper 禁止**：萃取出的 wiki 笔记必须是**自包含的通用知识**，不反向链回 paper 笔记（否则破坏 paper 隔离、违反铁律 3）。wiki 笔记若要溯源，可链 `raw/wiki/` 或同 wiki 其他笔记，而不是 paper。
- 与 project-capture 同理，指针的方向单向：源（paper）留指针指向 wiki，wiki 不指回源。

## 判定规则：什么该萃取到 wiki

逐段扫描 paper 笔记时，按此表判定：

| paper 笔记中的段落 / 内容 | 是否萃取到 wiki | 判定依据 |
|------|------|------|
| 核心方法里的**通用技术/数学技巧**（如某通用的优化引理、可复用算子、领域标准公式） | 通常可萃取 | 脱离本论文仍成立、可用于其他论文/项目 |
| 概念 / 原理 / 方法论（如"什么是 X 注意力""Y 范式的通用步骤"） | 通常可萃取 | 通用领域知识，跨论文有用 |
| 设计模式 / 架构范式（已成领域共识的） | 可萃取 | 非本论文独有 |
| 本文**专属方法**（本论文提出的、仅在此论文成立的算法） | 否（留 paper） | 论文专属叙事 |
| 实验设计与关键结果 | 否（留 paper） | 本论文数值/现象 |
| 创新点与贡献 | 否（留 paper） | 本论文的定位 |
| 局限与改进方向 | 否（留 paper） | 针对本论文 |
| 我的批判性思考 | 否（留 paper） | 针对本论文的反思 |
| 论文-代码对照 | 否（留 paper） | 本论文复现细节 |

- **通用知识的判据**：脱离本论文仍有独立价值——可用于读其他论文、做相关项目、面试复习、跨主题理解（如"分块 GEMM 为什么能算对""FlashAttention 的 tiling 思想"）。
- **专属的判据**：换了论文语境就失去意义（本论文提出的特定算法、本论文在某某 benchmark 上的 +X% 结果、本论文的局限）。
- **歧义时**：宁可萃取（通用优先 wiki），但列出待确认项交用户拍板，不擅自丢弃论文专属内容。

## 流程

### 一步：通读 paper 笔记 + 提取萃取候选（给用户审核，不擅自写）

1. **Read 整个 `paper/<topic>/<论文标题>.md`**。
2. 逐段扫描，标注为 `[通用-建议萃取]` / `[论文专属-留 paper]`。
3. 列出**萃取方案**交用户确认 / 调整：
   - 哪些内容 → 哪个 wiki 主题 / 笔记（**新建** `wiki/<topic>/<note>.md` 还是**追加**到已有笔记）；
   - paper 笔记原位改成什么指针（一行链接 + 一句论文视角注解）；
   - wiki 笔记的标题 / tags / summary（供 query 扫描）。

> 不要把所有内容塞进一个 wiki 笔记。一个概念一篇（原子性）；同一概念若已在 wiki 有其他笔记则追加而非新建，避免重复（SSOT）。

用户说「写吧 / 可以」再进入第二步。

### 二步：萃取落地（读 paper → 抽 wiki → 改 paper 指针 → 核 wiki 索引）

> **Frontmatter**：`wiki/` 笔记按 `.agents/conventions.md` 的 frontmatter 规范（title/topic/tags/summary/created/updated）；**wiki 笔记不写指向 paper 的反链**。

对每个 `[通用-建议萃取]` 候选：

- **建 / 追加 `wiki/<topic>/<note>.md`**：遵循 conventions.md（原子性、标题、frontmatter、公式、tags、summary、互链）。写成**自包含的通用知识**，不依赖"本论文"叙事；可链同 wiki 其他笔记或 `raw/wiki/`，不链 paper。
- **改 paper 笔记原位为指针**：
  ```markdown
  - 详见 [<wiki 标题>](../../wiki/<topic>/<note>.md)（本文中的应用：<一句论文视角注解>）
  ```
  不内联长文到 paper 笔记。
- **更新 wiki 索引**：
  - 目标 `wiki/<topic>/index.md` 的"包含笔记"列表新增本笔记条目；若该 `<topic>/` 为新 topic，还需在根 `wiki/index.md` 追加一行指向 `wiki/<topic>/`（让新主题在根 index 可见），没有"## 主题"小节则新建之。

对每个 `[论文专属-留 paper]` 段：**不动**（或仅微调表述，不萃取）。

- **记录萃取动作（留痕，不可省略）**：在 paper 笔记末尾「萃取记录（capture 历史）」小节追加一条（无此小节则新建于文件末尾）；每条格式：
  ```markdown
  - <YYYY-MM-DD>：将「<段落摘要>」从本论文笔记萃取至 wiki/<topic>/<note>.md（原位留指针，正文迁出）。
  ```
  让"本段通用知识因 paper-capture 而提纯至 wiki"可追溯，论文笔记不丢失该动作痕迹。

> **萃取不是删除**：paper 留指针、wiki 存正文，paper→wiki 单向互链。日后回看论文笔记仍能顺着指针跳到通用知识，且不把可复用内容锁死在论文里。

### 三步：校验（必做，因 lint 不扫 paper）

- `wc -l` 确认 paper 笔记与新建 wiki 笔记均非空（wiki 笔记建议 ≥ 50 行，frontmatter-only 视为异常）。
- 确认 frontmatter 完整（wiki 笔记含 title/topic/tags/summary/created/updated）。
- **自检链接**：对 paper 笔记里新增的 wiki 指针执行 `test -f <相对路径基准>/wiki/<topic>/<note>.md && echo OK`（lint 不扫 paper，必须自检）；对新建 wiki 笔记内的互链（含可能指向 `raw/wiki/` 的链接）同样 `test -f` 校验。
- 确认 `wiki/<topic>/index.md`（及必要时根 `wiki/index.md`）已含新笔记条目，篇数与实际文件数一致。
- 确认 paper 笔记末尾「萃取记录（capture 历史）」已追加本次萃取条目（留痕不可省）。
- `git status` 确认改动符合预期。

### 四步：提交

```bash
# 身份兜底（仓库级，缺失才补；不动 --global，与 AGENTS.md「NEVER update git config」不冲突）
git config user.email >/dev/null 2>&1 || git config user.email "$(git log -1 --format=%ae 2>/dev/null || echo you@example.com)"
git config user.name  >/dev/null 2>&1 || git config user.name  "$(git log -1 --format=%an 2>/dev/null || echo you)"
# 只 add 具体文件（严守 AGENTS.md「绝不 git add . / -A」）；paper 笔记 + 新建/改的 wiki 笔记 + wiki 索引
git add "paper/<topic>/<论文标题>.md" "wiki/<topic>/<note>.md" "wiki/<topic>/index.md" "wiki/index.md"
# 提交信息格式与 AGENTS.md 一致：<skill> <topic>: <一句话>
git commit -m "paper-capture <topic>: 从 <论文标题> 萃取 <N> 条通用知识到 wiki"
git push origin main
```

### 五步：发布闭环提示

笔记落在 `paper/` 与 `wiki/`，提交后 `git push origin main` 推到 grounds 远程，但要真正"上站"还需两个条件：

1. **进 deploy 白名单**：grounds 的 `.github/workflows/deploy.yml` 的 `paths:` 必须包含 `paper/**` 与 `wiki/**`，否则改动不触发 CI 部署。
2. **`publish: true`**：Quartz explicit-publish 插件只发布 frontmatter 带 `publish: true` 的页；wiki 笔记若要上站需加该字段（不想公开则保持默认不发布）。

> 二者缺一，就会出现"推到了 grounds 却没部署前端"的情况。

## Gotchas

- **必须手动触发**：用户没显式调用就拒绝执行，提示先 `$paper-learn` 或 `$paper-capture`。
- **绝不写进 `project/`**：项目目录是独立 git 仓库，笔记放 `paper/` 与 `wiki/` 才随父仓库 `git push` 流转。
- **萃取 ≠ 删除**：paper 留指针，wiki 存正文，paper→wiki 单向互链。
- **wiki 笔记不反向链回 paper**：paper 不参与互链（铁律 3），萃取出的 wiki 知识必须自包含；指针仅留在 paper 笔记里。
- **别把论文专属内容误萃**：本论文方法 / 实验 / 局限 / 批判性思考留在 paper。
- **格式同构**：wiki 笔记遵循 conventions.md；paper 指针保持 paper 笔记既有结构，不发明新模板。
- **有公式必贴**：抽出的 wiki 笔记里若含关键公式/代码，要落在笔记中（与 paper-learn"有公式必须写出来"同铁律）。
- **lint 不扫 paper**：paper 笔记的断链、index 缺失无 lint 兜底，必须在三步自检链接。
- **不补面经**：paper-capture 不做小红书 / 知乎 / 牛客搜索。
- **project_logs / paper 不进 lint / query**：paper 笔记与 project 笔记不参与 wiki 互链与 orphan 检查；wiki 笔记按 wiki 规范正常互链。

## 关联

- `AGENTS.md`（仓库地图、提交规范、铁律 3 互链约束）
- `.agents/skills/paper-learn/SKILL.md`（读论文、产出 paper 笔记）
- `.agents/skills/project-capture/SKILL.md`（对称技能：从 runbook 萃取通用知识到 wiki）
- `.agents/conventions.md`（wiki 笔记模板）
