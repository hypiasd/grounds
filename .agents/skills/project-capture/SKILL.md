---
name: project-capture
description: 用户用 $project-capture 显式触发，在对话结束时做「收尾路由 + 闭环核对」——把通用知识（概念/原理/方法论）路由去 wiki、项目专属内容留 project_logs/<current_project>/runbook.md 时间线节点，并核一遍末尾固定落点。是 project M0–M6 实时白盒工作流的收尾补漏。只接受手动 / `$` 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# project-capture

在对话结束或阶段节点，由你手动触发，做**收尾路由 + 闭环核对**：先把对话收获按"通用 / 项目专属"路由（通用知识 → `wiki/` 复用，项目专属 → `project_logs/<current_project>/runbook.md`），再核一遍 runbook 末尾固定落点。它是 project 技能**实时白盒工作流（M0–M6）的收尾补漏**——但 M6 已实时写时间线节点，故本技能的核心增量是**路由判断**与**末尾闭环核对**，而非重复写节点。

## 触发与约束

- **只接受手动 / `$` 触发**：用户显式输入 `$project-capture` 才执行；agent 不得基于对话内容自动调用。
- 必须先处于项目模式：本会话已通过 `$project <name>` 进入。未进入 → 提示用户先 `$project <name>` 并退出。

## 目标（完成时）

- **路由已完成**：通用知识（概念/原理/方法论，脱离本项目也有用）已路由去 `wiki/`（按 learn-capture 规范），runbook 节点只留一行链接 + 项目视角一句话；项目专属内容已内联进 `runbook.md` 对应时间线节点；
- 每个洞察落在正确节点子块（见下方「类型与落点」），不新建游离文件、不与 project 实时写的节点块格式冲突；
- `index.md`（项目入口卡）的目标 / 技术栈 / 现状仍准确并指向 `runbook.md`；
- 已 `git commit`（提交后 `git push origin main` 推到 grounds 远程）。

## 与 project 的关系（关键）

project 的 M0–M6 实时白盒工作流**已在协作中自动写**，全部内联进 `runbook.md` 的时间线节点：
- M1 决策 → runbook 对应节点的「决策」块
- M2 实验 / 验证 → runbook 验证节点的「结果」块
- M3 踩坑 → runbook 节点的「问题 / 解决」块
- M5 能力账本 → runbook 末尾「能力账本 / 下一步」小节

本技能**不重复造结构、不另开文件**，只把收尾时新发现的收获，用**完全相同的节点块格式**补进 `runbook.md` 的对应节点。即：实时写和收尾写，**落点一致、格式一致**。

## 与 learn-capture 的边界

- `learn-capture`：通用知识，沉淀进 `wiki/`，跨项目复用。
- `project-capture`：**当前项目专属**的收获，沉淀进 `project_logs/<current_project>/runbook.md` 的时间线节点。
- **默认 wiki，除非项目强锁定**：写一条洞察先问"这是通用的吗？"——是（概念/原理/方法论，脱离本项目也有用）就进 `wiki/`；**只有项目语境下才有意义的内容**（决策/坑/交付物/里程碑/本项目数值）才留 `project_logs/`。一条洞察若既属项目又具通用价值 → 通用部分进 `wiki/`、runbook 只留链接与项目视角注解（真实案例：vllm-plus M0 曾把 8 条通用 GEMM 概念全塞进 runbook，后迁回 wiki）。

## 类型与落点（对齐 project 单 runbook 结构）

回顾对话后，按以下类型把收获切成洞察，**每类落到固定位置**：

| 类型 | 落点（统一进 `runbook.md`） | 在该时间线节点内怎么写 |
|------|------|------|
| **决策** | runbook 对应时间线节点的「决策」块 | 问题 / 候选方案（≥2）/ 推荐+理由 / **需拍板点** / 关联 |
| **实施 / 步骤** | runbook 一个时间线节点（按执行顺序 / 指南步骤）的「实施」块 | 实际命令 / 关键结果 / 产物路径 |
| **踩坑 / 问题 / 困难** | 同一节点（或新节点）的「问题 / 解决」块 | 现象 / 根因 / 解法 / 防复发 / 学到了什么 |
| **概念 / 认知（教学向）** | **通用 → `wiki/`**（默认）；仅项目专属认知 → runbook「概念」块 | 用户追问"为什么 / 怎么理解"时沉淀的讲解。**先判是否通用**：通用原理/方法论 → 建/追加 `wiki/<topic>/<note>.md`，runbook 节点只留链接；项目专属认知才留 runbook「概念」块（统一命名 `**概念 <主题>（YYYY-MM-DD）**`，内附类比/形式化/图示）。与「问题 / 解决」块区分（后者是"出错"，前者是"认知升级"） |
| **实验 / 验证** | runbook 验证节点的「结果」块 | 触发方式 / 结果 / 备注 |
| **改动** | 相关节点的「实施 / 解决」块（或单独节点） | 改了什么 / 为什么 / 影响面 / 验证结果 |
| **交付产物** | runbook 末尾「交付产物清单」小节 | 是什么 / 位置 / 来源 / 与实测偏差 / 状态 |
| **能力账本** | runbook 末尾「能力账本 / 下一步」小节 | 当前阶段 / 已掌握 / 还不会 / 下一步 |

> **单 runbook 模式**：所有收获一律内联进 `runbook.md` 的对应时间线节点，**不再有 `decisions/` `pitfalls.md` `changes.md` `experiments/` `learning-journal.md` 等独立文件**——同一件事只在归属节点写一次（SSOT），杜绝多文件重复。无「索引维护」列（已无独立索引文件）。老项目若仍是多文件结构可保留，新项目一律单 runbook。

> **格式一致性**：runbook 节点内的「决策」块用 project M1 决策卡结构、「问题 / 解决」块用 M3 结构、「结果」块用 M2 结构——与 project 实时写出的卡片**完全同构**，这样时间线各节点长得一样，检索和阅读不分裂。

> **为什么统一进一份 runbook 而非多文件**：高频、零散、即时性强的内容（踩坑 / 改动 / 小决策）单文件 append 成本最低（决策日志系统原则：记录成本 < 重新讨论的痛苦才有效），且按时间线归位天然带上下文、回看有主线；拆成多份文件只会让同一件事在 decisions / pitfalls / experiments 反复出现，既重复又割裂。深度决策 / 复杂实验虽需展开，仍写在 runbook 节点的「决策 / 结果」块内，不另开文件。

> **老项目兼容**：若项目仍是多文件结构（如 `vllm-plus` 的 `decisions/` + `pitfalls.md`），新收获仍可落旧结构，不必强行回退到单 runbook；单 runbook 模式仅约束**新 onboard 项目**。

## 流程

### 一步：路由 + 蒸馏 + 切分（给用户审核，不擅自写）

回顾当前对话，提取收获切成多个洞察。**先逐条判目的地**（这是本 skill 与 M6 实时写的最大区别，也是它"不冗余"的关键）：
- **通用知识**（概念 / 原理 / 方法论，脱离本项目也有用，如「分块 GEMM 为什么能算对」「HBM 流量怎么推」）→ **路由去 `wiki/`**：按 learn-capture 规范建/追加 `wiki/<topic>/<note>.md`，runbook 对应节点只留**一行链接 + 项目视角一句话**，不把通用内容锁死在项目里。
- **项目专属**（决策 / 坑 / 交付物 / 里程碑 / 本项目特有数值）→ **留 `runbook.md` 时间线节点**，拟定归属节点与子块（决策 / 实施 / 问题·解决 / 结果 / 概念）。

> **默认 wiki，除非项目强锁定**：写一条洞察先问"这是通用的吗？"——是就进 wiki。runbook 只承载"本项目语境下才有意义"的内容（真实案例：vllm-plus M0 把 8 条通用 GEMM 概念全塞进 runbook，后迁回 wiki）。

列出**路由 + 切分方案**交用户确认 / 调整。用户说「写吧 / 可以」再进入第二步。

> **先判「是否已实时写入」**：若本对话中 agent 已按 project 的 M0–M6 节拍把收获逐条即时回写进 runbook 对应节点，则 capture **不再重写**，改为**补漏（reconciliation）**——只核对下方固定落点是否漏登、把缺的补上（**含反向核查：该进 wiki 的是否误留了 runbook**）即可。

> 不要把所有内容塞进一个节点。每个时间线节点聚焦一件事；决策 / 踩坑 / 验证各用各自子块，保持节点清晰。

**capture 前必查「固定落点」清单**（逐项核 runbook 末尾 + index，漏则补）：
1. 「交付产物清单」：本次是否有新产物（代码 / 脚本 / 文档）未登记？**核心交付物最易漏**（如参考实现、上手指南、测试脚本）。
2. 「能力账本 / 已掌握」：新掌握的能力是否写进（通用部分用 wiki 链接代指，不内联长文）？
3. 「能力账本 / 还不会 / 下一步」：待补项 / 新阶段目标是否更新（标注是否需特定环境，如 GPU 机）？
4. `index.md`：目标 / 技术栈 / 现状一行是否仍准确（现状须反映本轮进度）？

### 二步：归位（路由落地）

> **Frontmatter**：`runbook.md` 创建时带一次 frontmatter（title / tags: [project, <name>] / created / updated / publish: true，与 project M0 同构），之后按时间线节点 append `##` 小节，小节不带 frontmatter。`wiki/` 笔记按 `.agents/conventions.md` 的 frontmatter 规范。

对每个洞察，按一步判定的目的地落到对应位置：

- **通用知识 → `wiki/`**：建/追加 `wiki/<topic>/<note>.md`（遵循 learn-capture 规范与 conventions.md），runbook 对应节点只补**一行链接 + 项目视角注解**（如"本项目 M0 实践见 [分块 GEMM](../gemm/tiled-gemm.md)"）。
- **项目专属 → `runbook.md` 时间线节点**：先定位这件事发生 / 属于哪个时间线节点；
  - 决策 → 补「决策」块（问题 / 候选方案 / 推荐+理由 / 需拍板点 / 关联）
  - 实施 / 步骤 → 补「实施」块（实际命令 / 关键结果 / 产物路径）
  - 踩坑 / 困难 → 补「问题 / 解决」块（现象 / 根因 / 解法 / 防复发 / 学到了什么）
  - 验证 / 实验 → 补「结果」块（触发方式 / 结果 / 备注）
  - 概念（仅项目专属认知）→ 补「概念」块（统一命名 `**概念 <主题>（YYYY-MM-DD）**`）。
- **交付产物** → 落到 `runbook.md` 末尾「交付产物清单」小节（是什么 / 位置 / 来源 / 与实测偏差 / 状态）；**尤其要登记"上手指南 / 部署蓝图 / 参考实现"这类贯穿全程的核心文档**——这是项目最有价值的产出，最容易被"只记了踩坑"而漏登。
- **能力账本** → 落到 `runbook.md` 末尾「能力账本 / 下一步」小节（当前阶段 / 已掌握 / 还不会 / 下一步；通用能力用 wiki 链接代指，不内联长文）。

然后确保 `project_logs/<current_project>/index.md`（项目入口卡）的「目标 / 技术栈 / 现状 / 外部仓库」仍准确，并指向 `runbook.md`（单 runbook 模式下 index 只做入口卡，不重复叙述）。

### 三步：提交

```bash
# 身份兜底（仓库级，缺失才补；不动 --global，与 AGENTS.md「NEVER update git config」不冲突）
git config user.email >/dev/null 2>&1 || git config user.email "$(git log -1 --format=%ae 2>/dev/null || echo you@example.com)"
git config user.name  >/dev/null 2>&1 || git config user.name  "$(git log -1 --format=%an 2>/dev/null || echo you)"
# 只 add 具体文件（严守 AGENTS.md「绝不 git add . / -A」；单 runbook 模式仅此两文件）
git add project_logs/<current_project>/runbook.md project_logs/<current_project>/index.md
# 提交信息格式与 AGENTS.md 一致：<skill> <topic>: <一句话>
git commit -m "project-capture grounds: <current_project> 沉淀 <一句话>"
git push origin main
```

### 四步：发布闭环提示

笔记落在 `project_logs/<current_project>/`，提交后 `git push origin main` 推到 grounds 远程，但要真正"上站"还需两个条件：

1. **进 deploy 白名单**：grounds 的 `.github/workflows/deploy.yml` 的 `paths:` 必须包含 `project_logs/**`，否则改动不触发 CI 部署。
2. **`publish: true`**：Quartz explicit-publish 插件只发布 frontmatter 带 `publish: true` 的页；项目笔记若要上站，对应 md 需加该字段（不想公开则保持默认不发布）。

> 二者缺一，就会出现"推到了 grounds 却没部署前端"的情况。

## Gotchas

- **必须处于项目模式**：本会话未通过 `$project <name>` 进入就拒绝执行，提示先 `$project <name>`。
- **绝不写进 `project/`**：项目目录是独立 git 仓库，笔记放 `project_logs/` 才随父仓库 `git push` 流转。
- **落点：通用进 `wiki/`、专属进 runbook 时间线节点**：项目专属的决策 / 实施 / 踩坑 / 验证一律内联进 `runbook.md` 对应节点子块（见「类型与落点」），**不新建 `decisions/` `experiments/` `pitfalls.md` `changes.md` 等独立文件**（老项目若已是多文件结构可沿用）；通用概念/原理则进 `wiki/`（独立文件，符合 wiki 规范），不要锁死在 runbook。否则会与 project 实时写的节点块分裂，或把通用知识错配进项目。
- **格式同构**：节点内「决策 / 结果 / 问题·解决」块格式与 project M1 / M2 / M3 一致；不要发明新模板。
- **有代码必贴**：关键代码要落在卡片里，并注明语言。
- **不补面经**：project-capture 不做小红书 / 知乎 / 牛客搜索（那是 learn-capture 的事）。
- **project_logs 不进 lint / query**：该项目笔记不参与 wiki 互链与 orphan 检查，按项目自身地图（index.md 入口卡 + runbook.md 时间线）检索即可。

## 关联

- `AGENTS.md`（仓库地图、提交规范）
- `.agents/skills/project/SKILL.md`（进入项目、M0–M6 白盒工作流、单 runbook 结构定义）
- `.agents/skills/learn-capture/SKILL.md`（通用知识走这里）
