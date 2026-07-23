---
name: project-capture
description: 用户用 $project-capture 显式触发，对话结束时通读 project_logs/<current_project>/runbook.md，把其中「脱离本项目还有用的通用知识（概念/原理/方法论）」萃取成 wiki/<topic>/<note>.md（runbook 原位只留一行链接 + 项目视角注解），并核一遍末尾固定落点。是 project M0–M6 实时全记进 runbook 的收尾萃取，不重复记录。只接受手动 / `$` 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# project-capture

project 的 M0–M6 是"实时日志"：每轮发生的事（决策 / 实施 / 坑 / 验证 / 概念）都原样记进 `runbook.md`，像流水账、不做路由判断——这是有意的，记录要快、要全。

本技能是**收尾萃取**：对话结束或阶段节点，你手动触发，我**通读整个 runbook**，逐节点判断"这段内容脱离本项目还有没有用？"——有用（通用知识）→ 抽成 `wiki/<topic>/<note>.md`，runbook 原位只留**一行链接 + 项目视角注解**；没用（项目专属）→ 留在 runbook。最后核一遍末尾固定落点。

> 一句话：**project 负责"记全"，capture 负责"提纯"——把 runbook 里的通用知识萃取到 wiki，让项目日志不锁死可复用内容。**

## 触发与约束

- **只接受手动 / `$` 触发**：用户显式输入 `$project-capture` 才执行；agent 不得基于对话内容自动调用。
- 必须先处于项目模式：本会话已通过 `$project <name>` 进入。未进入 → 提示用户先 `$project <name>` 并退出。

## 目标（完成时）

- 已**通读 runbook**，对每个时间线节点 / 块判定"通用（建议萃取）vs 项目专属（留 runbook）"。
- 通用知识已抽成 `wiki/<topic>/<note>.md`（遵循 `.agents/conventions.md`），runbook 原位替换为指针 + 项目视角注解。
- 项目专属内容留在 runbook 时间线节点，未被误萃。
- 末尾固定落点已核（交付产物 / 能力账本 / index 现状）。
- 已 `git commit`（提交后 `git push origin main` 推到 grounds 远程）。

## 与 project 的关系（关键）

project 的 M0–M6 实时刻在跑，全部内联进 `runbook.md`：

- M1 决策 → runbook「决策」块
- M2 实验 / 验证 → runbook「结果」块
- M3 踩坑 → runbook「问题 / 解决」块
- M6 概念 / 认知 → runbook「概念」块

本技能**不重复写时间线节点、不新开 runbook 结构**——它只读 runbook、萃取出通用知识到 wiki、把 runbook 原位改为指针。即：project 写、capture 提纯，**落点分离（runbook ↔ wiki）而非格式分裂**。

## 与 learn-capture 的边界

- `learn-capture`：知识源是**一次对话**，直接产出通用 `wiki/` 笔记。
- `project-capture`：知识源是 **`runbook.md`**，从项目日志里"萃取"通用知识到 `wiki/`，萃取后 runbook 留指针。二者都产出 wiki，但来源不同。
- 一条洞察若既属项目又具通用价值：通用部分由 capture 萃取进 wiki，runbook 留链接与项目视角注解（真实案例：vllm-plus M0 把 8 条通用 GEMM 概念全塞进 runbook，后由 capture 迁回 wiki/gemm、wiki/gpu）。

## 判定规则：什么该萃取到 wiki

逐块扫描 runbook 时，按此表判定：

| runbook 中的块类型 | 是否萃取到 wiki | 判定依据 |
|------|------|------|
| 决策 | 否（留 runbook） | 项目专属拍板，含本项目上下文与拍板点 |
| 实施 / 步骤 | 一般否 | 项目专属命令 / 产物路径；若其中含**通用方法论**（如"如何系统定位根因"）可只抽方法论部分 |
| 问题 / 解决（坑） | 否（留 runbook） | 项目专属踩坑；但"通用调试心法"可抽 |
| 结果 / 验证 | 否（留 runbook） | 本项目数值 / 现象 |
| **概念 / 认知** | **通常可萃取** | 通用原理 / 方法论（脱离本项目有用）→ 抽 wiki；仅项目专属认知（如"本项目为何选 X 架构"）留 runbook |
| 交付产物 | 否（留 runbook） | 项目产物路径与状态 |
| 能力账本 | 否（留 runbook） | 项目能力快照；通用能力用 wiki 链接代指，不内联长文 |

- **通用知识的判据**：脱离本项目仍有独立价值——可用于面试复习、其他 CUDA / kernel 项目、跨主题理解（如"分块 GEMM 为什么能算对""HBM 流量公式推导""两级缓存复用模型"）。
- **专属的判据**：换了项目语境就失去意义（本项目决策依据 / 本项目踩的特定坑 / 4090D 上的 +13% 吞吐数值 / 交付物路径）。
- **歧义时**：宁可萃取（通用优先 wiki），但列出待确认项交用户拍板，不擅自丢弃项目专属内容。

## 流程

### 一步：通读 runbook + 提取萃取候选（给用户审核，不擅自写）

1. **Read 整个 `runbook.md`**（时间线节点 + 末尾固定小节）。
2. 逐节点扫描每个块（决策 / 实施 / 问题 / 结果 / 概念），标注为 `[通用-建议萃取]` / `[专属-留 runbook]`。
3. 列出**萃取方案**交用户确认 / 调整：
   - 哪些块 → 哪个 wiki 主题 / 笔记（**新建** `wiki/<topic>/<note>.md` 还是**追加**到已有笔记）；
   - runbook 原位改成什么指针（一行链接 + 一句项目视角注解）。

> 不要把所有内容塞进一个 wiki 笔记。一个概念一篇（原子性）；同一概念若已在 wiki 有其他笔记则追加而非新建，避免重复（SSOT）。

用户说「写吧 / 可以」再进入第二步。

**capture 前必查「固定落点」清单**（逐项核 runbook 末尾 + index，漏则补）：
1. 「交付产物清单」：本次新产物（代码 / 脚本 / 文档 / 参考实现）是否登记？**核心交付物最易漏**。
2. 「能力账本 / 已掌握」：新掌握能力是否写进（通用部分用 wiki 链接代指，不内联长文）？
3. 「能力账本 / 还不会 / 下一步」：待补项 / 新阶段目标是否更新（标注是否需特定环境，如 GPU 机）？
4. `index.md`：目标 / 技术栈 / 现状一行是否仍准确（现状须反映本轮进度）？

### 二步：萃取落地（读 runbook → 抽 wiki → 改 runbook 指针）

> **Frontmatter**：`wiki/` 笔记按 `.agents/conventions.md` 的 frontmatter 规范；`runbook.md` 仅在创建时带一次 frontmatter，此处不再动其结构。

对每个 `[通用-建议萃取]` 候选：

- **建 / 追加 `wiki/<topic>/<note>.md`**：遵循 conventions.md（原子性、标题、frontmatter、公式、tags、summary、互链）。通用知识写成可独立复用的笔记，不绑定本项目叙事。
- **改 runbook 原位为指针**：把原块长文迁出，原位只留——
  ```markdown
  - 详见 [<wiki 标题>](../../wiki/<topic>/<note>.md)（本项目 M0 实践：<一句项目视角注解>）
  ```
  不内联长文到 runbook。
- **互链**：wiki 笔记若引用了本项目，可链回 `project_logs/<name>/runbook.md`（wiki ↔ project 单向引用即可，不必双向强耦）。

对每个 `[专属-留 runbook]` 块：**不动**（或仅微调表述，不萃取）。

然后做**固定落点闭环**：按一步清单补「交付产物清单 / 能力账本 / index 现状」。

萃取后**更新 `runbook.md` frontmatter 的 `updated` 日期**到当天。

- **记录萃取动作（留痕，不可省略）**：在 runbook 末尾「萃取记录（capture 历史）」小节追加一条（无此小节则新建于文件末尾）；每条格式：
  ```markdown
  - <YYYY-MM-DD>：将「<源块类型 / 摘要，如 M0 概念：decode GEMM 分块心智模型>」从 runbook 萃取至 wiki/<topic>/<note>.md（原位留指针，正文迁出）。
  ```
  runbook 是时间线流水账，萃取把长文迁出后，若无此记录，"这段曾存在、因 capture 而提纯"的痕迹会消失——此小节让动作可追溯，不似从未发生。

> **萃取不是删除**：runbook 留指针、wiki 存正文，二者互链。日后回看项目日志仍能顺着指针跳到通用知识，且不把可复用内容锁死在项目里。

- **更新 wiki 索引**：
  - 目标 `wiki/<topic>/index.md` 的"包含笔记"列表新增本笔记条目；若该 `<topic>/` 为新 topic，还需在根 `wiki/index.md` 追加一行指向 `wiki/<topic>/`（让新主题在根 index 可见），没有"## 主题"小节则新建之。

### 三步：校验（必做，因 lint 不扫 project_logs）

- `wc -l` 确认 runbook 与新建 wiki 笔记均非空（wiki 笔记建议 ≥ 50 行，frontmatter-only 视为异常）。
- 确认 frontmatter 完整（wiki 笔记含 title/topic/tags/summary/created/updated）。
- **自检链接**：对 runbook 里新增的 wiki 指针执行 `test -f <相对路径基准>/wiki/<topic>/<note>.md && echo OK`（lint 不扫 project_logs，必须自检）；对新建 wiki 笔记内的互链（含可能指向 `project_logs/<name>/runbook.md` 的链接）同样 `test -f` 校验。
- 确认 `wiki/<topic>/index.md`（及必要时根 `wiki/index.md`）已含新笔记条目，篇数与实际文件数一致。
- 确认 runbook 末尾「萃取记录（capture 历史）」已追加本次萃取条目（留痕不可省）。
- `git status` 确认改动符合预期。

### 四步：提交

```bash
# 身份兜底（仓库级，缺失才补；不动 --global，与 AGENTS.md「NEVER update git config」不冲突）
git config user.email >/dev/null 2>&1 || git config user.email "$(git log -1 --format=%ae 2>/dev/null || echo you@example.com)"
git config user.name  >/dev/null 2>&1 || git config user.name  "$(git log -1 --format=%an 2>/dev/null || echo you)"
# 只 add 具体文件（严守 AGENTS.md「绝不 git add . / -A」）；runbook + index + 新建/改的 wiki 文件
git add project_logs/<current_project>/runbook.md project_logs/<current_project>/index.md wiki/<topic>/<note>.md
# 提交信息格式与 AGENTS.md 一致：<skill> <topic>: <一句话>
git commit -m "project-capture grounds: <current_project> 从 runbook 萃取 <N> 条通用知识到 wiki"
git push origin main
```

### 五步：发布闭环提示

笔记落在 `project_logs/<current_project>/` 与 `wiki/`，提交后 `git push origin main` 推到 grounds 远程，但要真正"上站"还需两个条件：

1. **进 deploy 白名单**：grounds 的 `.github/workflows/deploy.yml` 的 `paths:` 必须包含 `project_logs/**` 与 `wiki/**`，否则改动不触发 CI 部署。
2. **`publish: true`**：Quartz explicit-publish 插件只发布 frontmatter 带 `publish: true` 的页；笔记若要上站需加该字段（不想公开则保持默认不发布）。

> 二者缺一，就会出现"推到了 grounds 却没部署前端"的情况。

## Gotchas

- **必须处于项目模式**：本会话未通过 `$project <name>` 进入就拒绝执行，提示先 `$project <name>`。
- **绝不写进 `project/`**：项目目录是独立 git 仓库，笔记放 `project_logs/` 与 `wiki/` 才随父仓库 `git push` 流转。
- **萃取 ≠ 删除**：runbook 留指针，wiki 存正文，二者互链；别把专属内容误萃（决策 / 本项目坑 / 本项目数值留在 runbook）。
- **格式同构**：wiki 笔记遵循 conventions.md；runbook 指针保持单 runbook 格式，不发明新模板。
- **有代码必贴**：抽出的 wiki 笔记里若含关键代码，要落在笔记中并注明语言。
- **不补面经**：project-capture 不做小红书 / 知乎 / 牛客搜索（那是 learn-capture 的事）。
- **project_logs 不进 lint / query**：该项目笔记不参与 wiki 互链与 orphan 检查；wiki 笔记按 wiki 规范正常互链。

## 关联

- `AGENTS.md`（仓库地图、提交规范）
- `.agents/skills/project/SKILL.md`（进入项目、M0–M6 实时白盒工作流、单 runbook 结构定义）
- `.agents/skills/learn-capture/SKILL.md`（从对话直接产出通用 wiki 笔记）
- `.agents/conventions.md`（wiki 笔记模板）
