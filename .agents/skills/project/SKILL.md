---
name: project
description: 进入项目模式，把 agent 当「陪练 / 教练」而非代写——白盒化每一个决策、实时沉淀实验 / 踩坑 / 学习，让你逐步掌控全局、脱离 agent 也能做。手动 / `$` 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# project

## 核心理念：这个 skill 不为「做完」，为「学会」

AI 时代代码大多是 agent 写的。如果你只给 prompt、看测试结果，你得到的是「完成的任务」，失去的是「能力」——你始终被关在黑盒外。

本 skill 把项目模式重新定义为一台**能力萃取机**。它借「认知学徒制（Cognitive Apprenticeship: 示范 modeling → 支架 scaffolding → 指导 coaching → 淡出 fading）」的思路，强迫 agent 把专家的**思考过程外显**成你能学习的素材：

- **守住决策权**（freeCodeCamp 黄金规则）：用 AI 加速「怎么实现（how）」，但架构、安全、复杂业务逻辑、第一次学的新概念（what & why）**必须你自己定**。agent 只摊选项、不替你拍板。
- **白盒优先**：任何非平凡决策前，agent 先停下、把方案摊开给你看、等你说「懂了 / 选 A / 我有问题」再动。绝不静默实现。
- **实时沉淀**：决策、实验、踩坑、顿悟，发生瞬间就写卡片，不做完才回忆（决策日志只有「即时捕获」才有效）。
- **能力可量化**：用「淡出机制」跟踪你从「agent 给完整方案」到「你自己提方案、agent 把关」的成长，让「我进步了没有」看得见。

> 一句话：**做完这个项目，你不该只会说「agent 帮我搞定了」，而该能说「这个决策为什么这么选、那个坑怎么踩的、下次我自己也能定」。**

## 何时用（触发）

- 用户说「进入项目 X」「把 X 收进项目」「project X」「切换到项目模式」。
- 用户给了一个项目名 / 本地路径 / git URL，想把它纳入当前派生仓的 `project/` 下，并**以学习为目的**地推进。

**只接受手动 / `$` 触发**：agent 不得基于用户消息内容自动调用。

## 目标（完成时仓库应处于的状态）

- 目标项目已落在 `project/<name>/` 下（clone / 软链 / 新建之一）。
- `.buildconfig` 的 `current_project=<name>` 已更新（标记「当前处于项目模式」）。
- 首次进入非空已有项目 → 已 onboard，并在 `project_logs/<name>/` 下建好 **M0 全局掌控视图**全套骨架（见下方）。由 `.buildconfig` 的 `onboarded` 列表持久标记，只做一次。
- 项目推进中，每个非平凡决策都有 **Decision Card** 留痕；每次实验有 **Experiment Card**；踩坑 / 顿悟实时进 **pitfalls / learning-journal**。

## 参数判别（与旧版一致）

`project` 只认一个参数（名称 / 本地路径 / git URL），按优先级自动判别：

```bash
ARG="$1"
case "$ARG" in
  git@* | http://* | https://* ) MODE=clone ;;
  * ) [ -d "$ARG" ] && MODE=link || MODE=new ;;
esac
```

- `MODE=clone`：clone 到 `project/<name>/`。
- `MODE=link`：`ARG` 是本地已有目录 → 在 `project/` 下建**软链** `<name> → $ARG`（保留原路径，不移动；详见 Gotchas）。
- `MODE=new`：纯名字 → `git init` 空项目（独立 git，父仓库忽略其内容）。

## 流程

### 第一步：解析参数与 <name>（与旧版一致）

```bash
ARG="$1"
[ -z "$ARG" ] && { echo "用法：$project <name|本地路径|git URL>"; exit 1; }
NAME=$(basename "${ARG%.git}")
case "$NAME" in
  *" "*) echo "❌ 项目名不能含空格：'$NAME'。请用中划线代替（如 my-project）"; exit 1 ;;
esac
```

### 第二步：按 MODE 收纳（与旧版一致）

```bash
mkdir -p project
if [ -e "project/$NAME" ] || [ -L "project/$NAME" ]; then
  echo "项目 project/$NAME 已存在，直接切换。"
else
  case "$MODE" in
    clone) git clone "$ARG" "project/$NAME" ;;
    link)  ln -s "$(cd "$ARG" && pwd)" "project/$NAME" ;;
    new)   git init "project/$NAME" >/dev/null 2>&1
           echo "new: 已 git init project/$NAME（独立仓库，父仓库忽略其内容）" ;;
  esac
fi
mkdir -p "project_logs/$NAME"
```

### 第三步：更新 .buildconfig 的 current_project（与旧版一致）

```bash
[ -f .buildconfig ] || cat > .buildconfig <<'EOF'
grounds_remote=git@github.com:hypiasd/grounds.git
workbase_remote=git@github.com:hypiasd/workBase.git
local_grounds_path=
current_project=
EOF
if grep -q '^current_project=' .buildconfig; then
  sed -i.bak "s/^current_project=.*/current_project=$NAME/" .buildconfig && rm -f .buildconfig.bak
else
  echo "current_project=$NAME" >> .buildconfig
fi
```

### 第四步：onboard（首次进入非空已有项目）—— 建好 M0 全景骨架

判定「非空已有项目」：`project/$NAME/` 已存在且不是本次新建空壳。link 模式需用 `readlink -f` 解引用再查（否则软链误判为空壳，见旧版 Gotchas）。

```bash
TARGET="project/$NAME"; [ -L "$TARGET" ] && TARGET=$(readlink -f "$TARGET")
cnt=$(find "$TARGET" -mindepth 1 -maxdepth 1 -not -name .gitkeep -not -name notes -not -name .git 2>/dev/null | head -1)
ONBOARDED=""; [ -f .buildconfig ] && ONBOARDED=$(grep '^onboarded=' .buildconfig 2>/dev/null | cut -d= -f2-)
already() { echo " $ONBOARDED " | grep -qF " $1 "; }
if [ -n "$cnt" ] && ! already "$NAME"; then echo "ONBOARD=yes"; else echo "ONBOARD=no"; fi
```

若 `ONBOARD=yes`，agent **主动盘点**并生成 **M0 全套骨架**（写进 `project_logs/<name>/`）：

1. `index.md`：**项目全景**（目标 / 技术栈 / 命令 / 结构 / 现状 / 待办 / 决策指针 / 外部仓库）—— 这是你的「控制台」。
2. `decisions.md`：**决策索引**（表格，逐条链接到 `decision-<topic>.md`；首版可为空表 + 说明）。
3. `decisions/` 目录：每个重大决策一个 `decision-<topic>.md`（Decision Card 模板见 M1）。
4. `experiments/` 目录 + `experiments/index.md`：**实验记录台**（每个实验一张 Experiment Card，模板见 M2）。
5. `pitfalls.md`：**踩坑 / 知识点账本**（实时 append，模板见 M3）。
6. `learning-journal.md`：**能力账本**（当前淡出阶段 / 已掌握 / 还不会 / 下一步练什么，模板见 M5）。

外部仓库节**只写远程 URL + 软链名，绝不写本机绝对路径**（如 `/Users/tian/...`）——`project_logs/` 会随 `$sync` 进 git 推远程，写本机绝对路径会泄露本机用户名与目录结构；真实本地路径记在 `.buildconfig` 的 `local_grounds_path`，不进笔记。

生成后务必写入 `onboarded` 标记（保证只做一次、不覆盖已写笔记）：

```bash
if ! grep -q '^onboarded=' .buildconfig 2>/dev/null; then
  echo "onboarded=$NAME" >> .buildconfig
elif ! grep '^onboarded=' .buildconfig | cut -d= -f2- | grep -q " $NAME "; then
  sed -i.bak "s/^onboarded=.*/onboarded=$(grep '^onboarded=' .buildconfig | cut -d= -f2-) $NAME/" .buildconfig && rm -f .buildconfig.bak
fi
```

## 白盒协作工作流（本 skill 的核心）

进入项目模式后，以下机制**随时生效**。它们是「工作流」而非「自律建议」——agent 在每一步主动执行，不靠自觉。

### M0 · 全局掌控视图

`project_logs/<name>/` 是项目的「白盒仪表盘」。

> **Frontmatter 规范（前端对齐 Quartz 必须）**：上述每个独立 md 文件开头都要带 frontmatter，否则前端会显示成文件名而非中文标题。格式：
> ```markdown
> ---
> title: <中文标题，与 H1 同名>
> tags: [project, <name>]
> created: <YYYY-MM-DD>
> updated: <YYYY-MM-DD>
> ---
> ```
> `pitfalls.md` / `changes.md` 在**文件创建时**带一次 frontmatter，之后只 append `###` 小节（小节不带 frontmatter）。任何推进都要回写对应文件，让用户随时 `cat` 一眼就知道全局。各文件职责见第四步。原则：**改了东西就更新 index 的「现状 / 待办」，做了决策就加 Decision Card，跑了实验就填 Experiment Card，踩了坑就 append pitfalls。**

### M1 · 决策卡 Decision Card（白盒核心）

**任何非平凡的选型 / 架构 / 安全 / 性能 / 第一次遇到的新概念，agent 必须先停，产出 Decision Card，等用户确认 / 提问，绝不静默实现。**

Card 字段（吸收工程决策日志：Context / Options / Decision / Rationale / Consequences）：

```markdown
---
title: 决策：<一句话主题>
tags: [project, <name>, decision]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

# 决策：<一句话主题>

- **问题（what & why）**：现在要解决什么？为什么现在必须定？
- **候选方案**（≥2，各写利弊与适用边界）：
  - 方案 A：… pros / cons / 适合场景
  - 方案 B：… pros / cons / 适合场景
- **推荐 + 理由**：选哪个、为什么不是别的（关键点要说人话）
- **需要你拍板的点**：明确把决策权交还用户（如「A 还是 B？」「阈值取多少？」）
- **关联**：commit / 实验卡链接（留痕）
- **复审日期**（可选）：什么时候该回看这个决策还成不成立
```

- 落地：写成 `decisions/decision-<topic>.md`，并在 `decisions.md` 索引表追加一行。
- 行为：把 Card 完整展示给用户，**停下来等回复**。用户说「我懂了 / 选 A / 我有问题」才进入实现。用户提问时，agent 用类比 / 形式化讲清，不回避。
- 这是「守住决策权」的硬机制：agent 永远只给选项，不替用户定 what & why。

### M2 · 实验卡 Experiment Card

用户想验证某个优化 / 假设（如「KV 量化到底有没有用」）时，agent **先帮把实验设计白盒化**，跑完一起填结论，形成可复看的记录。

```markdown
---
title: 实验：<假设一句话>
tags: [project, <name>, experiment]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

# 实验：<假设一句话>

- **假设**：如果做 X，预期 Y 会改善（明确因→果）
- **方法**：怎么做的（改了哪、基准是什么）
- **度量指标**：用什么数据判断成败（吞吐 / 显存 / 延迟 / 准确率…）
- **预期**：预期看到什么
- **结果**（跑完填）：实际数据 / 现象
- **结论**：假设成立吗？下次还这么做吗？保留还是回退？
- **关联**：对应 Decision Card / commit
```

- 落地：`experiments/exp-<slug>.md`，并在 `experiments/index.md` 列进度。
- 价值：把「调参 / 优化」从玄学变成「假设—证据—结论」的可积累知识（对应 vllm-plus 那种 12 项实验的可复看化）。

### M3 · 踩坑 / 学习卡（实时）

遇到坑、顿悟、非显然知识点，**发生瞬间就写**，不等项目结束回忆（决策 / 实验日志只有即时捕获才有效，事后补会失真）。

`pitfalls.md` 用分隔块 append，单文件成本低：

```markdown
### <YYYY-MM-DD> <一句话坑 / 知识点>

- **现象**：出现了什么
- **根因**：为什么（借 debugging 五步定位根因，不修表象）
- **解法**：怎么解
- **防复发**：下次怎么一眼避开
- **学到了什么**：这条让我的哪个认知升级了
```

### M4 · 理解优先（强制读 — diff — 反问）

- **实现前**：先和用户对齐（M1 Decision Card / M2 实验设计），不拿到方向就写代码。
- **实现后**：agent **主动列出**「本次改了哪些文件 / 关键改动是什么 / 为什么这么改」，方便用户逐文件 diff。用户反问「为何遗漏 X / 这里为什么这么写」时，agent 必须解释清楚、不敷衍——把每次 AI 产出当教学样本。
- **第一次遇到的新概念**：agent 必须用自然语言（类比 / 形式化）讲清，绝不丢给用户一段看不懂的代码就完事。
- **验收纪律**：动了关键代码，跑 `index.md` 里记的 test / build 命令确认没坏；不知道命令就明确提醒用户跑，绝不「看起来对」就算完。出错停手 → 复现 → 定位根因 → 修根因 → 补防复发验证。

### M5 · 淡出机制 Fading（能力成长路径）

这是「学习导向」的度量。随项目推进，agent **逐步把决策权交还用户**，让「能力增长」可量化：

| 阶段 | 用户状态 | agent 行为 |
|------|----------|-----------|
| **1 陌生** | 第一次接触该技术 | agent 给完整方案 + 多选 + 教学，用户选 |
| **2 熟悉** | 懂基本套路 | agent 只给选项 + 推荐，用户定方向 |
| **3 熟练** | 能独立想方案 | agent 只点出关键决策点，用户自己提方案，agent 把关 / 补盲点 |

- `learning-journal.md` 记录：当前所处阶段、已掌握的点、还不会的点、下一步该练什么。
- 每次项目推进后，agent 主动更新 journal 的阶段与「还不会的点」——用户回看就知道「我成长了多少、还差哪块」。
- 目标：项目结束时，用户对该领域能从阶段 1 走到阶段 3，脱离 agent 也能自己做决策。

---

## 与 project-capture / learn-capture 的边界

- `project-capture`（`$` 手动触发）：对话结束后，**批量补沉淀**当前项目收获（改动 / 困难 / 实验 / 决策 / 踩坑），进 `project_logs/`。它是本工作流的**补充**——本工作流强调「实时卡片」，project-capture 适合收尾时把零散对话再蒸馏一遍。
- `learn-capture`（`$` 手动触发）：**通用知识**进 `wiki/`，跨项目复用；只在项目语境下才有意义的内容留 `project_logs/`。
- 关系：本 skill 的 M1–M3 是「边做边写」，project-capture 是「做完补漏」，learn-capture 是「升华到通用」。三者不冲突。

## 设计原则（为什么没有子命令）

`project` 只负责「**收纳 + 切换 + 定义学习导向白盒工作流**」，不做项目过程管理的具体命令（不提供 `log` / `retro` / `add`）。记进展、复盘、沉淀是普通文件编辑 / `$project-capture` 调用。保持职责单一：获取项目 = `project`，推送成果 = `sync`，初始化仓 = `start`。

## Gotchas（真实踩过的坑）

- **收纳默认软链，不要默认移动**：`mv` 会破坏用户原项目路径；除非用户显式要「迁移」，否则用软链（见第一步–第二步）。
- **onboard 只做一次**：由 `.buildconfig` 的 `onboarded` 保证；禁止每次进入重做全盘扫描（会覆盖已写笔记）。
- **笔记只进 `project_logs/<name>/`**：代码 / 构建产物放 `project/<name>/`（独立 git，父仓库忽略）；`sync` 只收 `project_logs/`，绝不把代码推回 grounds。
- **current_project 是模式标记，不是数据**：只告诉后续 skill「当前上下文是哪个项目」。
- **`.buildconfig` 不进 sync**：派生仓自己的配置，推回 grounds 时排除。
- **白盒不是啰嗦**：M1 摊方案要有结构（问题 / 选项 / 推荐 / 拍板点），不是长篇流水；用户说「直接做」时可精简，但**关键决策仍留 Decision Card**（写文件比口头说更易回溯）。
- **本机绝对路径不进笔记**：外部仓库节只写远程 URL + 软链名（见第四步）。
- **淡出要真淡出**：阶段 3 时 agent 别再抢着给方案，主动退到「把关」角色，逼用户自己思考——这才是能力增长的来源。
