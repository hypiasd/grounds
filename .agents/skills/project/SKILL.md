---
name: project
description: 把项目收纳进 project/<name>/ 并切换到「项目模式」——根据参数自动判别（URL 则 clone、本地目录则软链、纯名字则新建空项目），更新 .buildconfig 的 current_project，生成/更新项目全景，并打印该项目模式下的做项目规则与如何复盘、沉淀、sync 的指引。非空已有项目首次进入会做 onboard 盘点。做项目规则（R1–R7）进入即生效，见下方「做项目规则」节。只接受手动 / `$` 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# project

## 何时用（触发）
- 用户说"进入项目 X"、"把 X 收进项目"、"project X"、"切换到项目模式"。
- 用户给了一个项目名 / 本地路径 / git URL，想把它纳入当前派生仓的 `project/` 下管理。

**只接受手动 / `$` 触发**：agent 不得基于用户消息内容自动调用。

## 目标（完成时仓库应处于的状态）
- 目标项目已落在 `project/<name>/` 下（clone / 软链 / 新建之一）。
- `.buildconfig` 的 `current_project=<name>` 已更新（标记"当前处于项目模式"）。
- 若是**非空已有项目**首次进入 → 已自动 onboard（生成 `project_logs/<name>/index.md` + `project_logs/<name>/decisions.md`）；**由 `.buildconfig` 的 `onboarded` 列表持久标记，保证只做一次**（重进同一项目不再重做盘点、不覆盖已写笔记）。
- 已向用户打印「项目模式说明」（后续怎么工作）。

## 参数判别

`project` 只认**一个参数**（名称 / 本地路径 / git URL），按以下优先级自动判别：

```bash
ARG="$1"
case "$ARG" in
  git@* | http://* | https://* )
    MODE=clone ;;
  * )
    if [ -d "$ARG" ]; then MODE=link; else MODE=new; fi ;;
esac
```

- `MODE=clone`：把 `ARG`（git URL）clone 到 `project/<name>/`，`<name>` 取 URL 最后一段去 `.git`。
- `MODE=link`：`ARG` 是本地已有目录 → 在 `project/` 下建**软链** `<name> → $ARG`（保留原路径，不移动）。
- `MODE=new`：`ARG` 是纯名字 → 在 `project/<name>/` 下 `git init` 空项目（独立 git 仓库，父仓库不跟踪其内容）。

> **收纳默认用软链**（保留原项目路径，零风险）。若用户明确要求"移动 / 物理迁移"，再把软链换成 `mv`；否则不要用 `mv` 破坏原路径。

## 流程

### 第一步：解析参数与 <name>

```bash
ARG="$1"
[ -z "$ARG" ] && { echo "用法：$project <name|本地路径|git URL>"; exit 1; }
# 取 name：clone 取 URL basename 去 .git；其余取路径 basename
NAME=$(basename "${ARG%.git}")
```

### 第二步：按 MODE 收纳

```bash
mkdir -p project
case "$MODE" in
  clone)
    git clone "$ARG" "project/$NAME"
    ;;
  link)
    ln -s "$(cd "$ARG" && pwd)" "project/$NAME"
    ;;
  new)
    git init "project/$NAME" >/dev/null 2>&1
    echo "new: 已 git init project/$NAME（独立仓库，父仓库忽略其内容）"
    ;;
esac
# 任何模式都确保项目笔记目录存在（与 project/ 解耦，project/ 是独立 git 仓库，父仓库忽略）
mkdir -p "project_logs/$NAME"
```

### 第三步：更新 .buildconfig 的 current_project

```bash
# 若 .buildconfig 不存在先建（理论上 start 已建；这里兜底）
[ -f .buildconfig ] || cat > .buildconfig <<'EOF'
grounds_remote=git@github.com:hypiasd/grounds.git
workbase_remote=git@github.com:hypiasd/workBase.git
local_grounds_path=
current_project=
EOF
# 更新 current_project 字段（不存在则追加）
if grep -q '^current_project=' .buildconfig; then
  sed -i '' "s/^current_project=.*/current_project=$NAME/" .buildconfig
else
  echo "current_project=$NAME" >> .buildconfig
fi
```

### 第四步：onboard（仅当非空已有项目首次进入）

判断"非空已有项目"：`project/$NAME/` 已存在且**不是本次新建的空壳**（即进入前已有内容，或 `MODE=link`/`clone` 拉来的是非空仓库）。

```bash
# 检测"非空已有项目 + 未 onboard 过"：
#  1) project/$NAME/ 下除 .gitkeep / notes 外是否还有内容（非空才盘点）
#  2) 是否已在 .buildconfig 的 onboarded 列表里（在则跳过，保证只做一次）
# ⚠️ link 模式 project/$NAME 是软链：find 默认不跟随软链，软链自身又在 depth 0 被 -mindepth 1 排除，
#    必须先用 readlink -f 解引用到真实目录再查，否则会误判 link 项目为"空壳"、永不 onboard。
TARGET="project/$NAME"
[ -L "$TARGET" ] && TARGET=$(readlink -f "$TARGET")
cnt=$(find "$TARGET" -mindepth 1 -maxdepth 1 \
        -not -name .gitkeep -not -name notes -not -name .git 2>/dev/null | head -1)
# 读取已 onboard 列表（持久化在 .buildconfig，空格分隔；不进 sync，属本机状态）
ONBOARDED=""
[ -f .buildconfig ] && ONBOARDED=$(grep '^onboarded=' .buildconfig 2>/dev/null | cut -d= -f2-)
already() { echo " $ONBOARDED " | grep -q " $1 "; }
if [ -n "$cnt" ] && ! already "$NAME"; then
  echo "ONBOARD=yes"   # 命中：执行下方 onboard 盘点（生成 project_logs/<name>/index.md + decisions.md）
else
  echo "ONBOARD=no"    # 空壳 / 已 onboard 过 / 新建：跳过，绝不重复生成（避免覆盖用户已写内容）
fi
```

若满足，则 agent **主动盘点现状**，生成两份笔记（写进 `project_logs/<name>/`）：

1. `project_logs/<name>/index.md`（**项目全景**，学 spec-driven 压成认知版）：
   - **目标**：这项目是什么 / 解决什么问题。
   - **技术栈**：语言 / 框架 / 关键依赖。
   - **命令**：build / test / lint / dev 怎么跑（⚠️ 枢纽：喂给 R4 轻关卡用，进项目就探测记下）。
   - **结构**：核心目录与职责（3-8 条）。
   - **现状**：当前进度 / 能跑到哪 / 卡点。
   - **待办**：接下来要做什么。
   - **决策指针**：→ decisions.md。
   - **外部仓库 URL + 本地路径**（让 grounds 能指回去）。
2. `project_logs/<name>/decisions.md`：从 commit / PR 记录提炼已有决策（ADR 雏形）；**不确定的地方标"待确认"**。

> onboard 是自动动作，**不是子命令**。只在"进入一个非空已有项目"时触发一次；之后改项目就直接记 `log.md` / 更新 `index.md`，不再重做全盘盘点。

生成两份笔记后**务必写入 `onboarded` 标记**（保证下次进入同一项目不再重做盘点、不覆盖已写笔记）：

```bash
# 把 NAME 追加进 .buildconfig 的 onboarded 列表（空格分隔；已存在则跳过追加）
if ! grep -q '^onboarded=' .buildconfig 2>/dev/null; then
  echo "onboarded=$NAME" >> .buildconfig
elif ! grep '^onboarded=' .buildconfig | cut -d= -f2- | grep -q " $NAME "; then
  sed -i '' "s/^onboarded=.*/onboarded=$(grep '^onboarded=' .buildconfig | cut -d= -f2-) $NAME/" .buildconfig
fi
```

### 第五步：打印「项目模式说明」

无论哪个 MODE，进入后都向用户打印：

```
已进入项目模式：<name>
- 项目位置：project/<name>/（clone/软链/新建）
- 项目全景：project_logs/<name>/index.md（目标/技术栈/命令/结构/现状/待办）
- 做项目规则已生效（R1–R7，见本 skill「做项目规则」节）：
    · 进项目先读全景与 decisions.md（R1）
    · 重要改动先讲 why、有哪些备选（R3）
    · 改完必验证、出错停线查根因（R4 / R5）
    · 关键决策写 decisions.md（R6）
    · 我会主动补你忽略的点（R7）
- 沉淀：用 $project-capture 把本轮改动/困难/实验/决策蒸馏成原子笔记（类型见 project-capture skill）；具通用价值另用 $learn-capture 进 wiki/
- 回流：干完用 $sync 把 project_logs/<name>/ 推回 grounds（只推笔记，不碰项目代码）
```

## 做项目规则（进入项目模式即生效）

`project` 决定"在这个项目里怎么协作"。进入项目模式后（无论 clone / 软链 / 新建），以下规则**随时生效**，agent 在做项目过程中主动遵守——这是规则集不是流程剧本，不限定先后顺序。

### R1 上下文先行
进项目先读 `project_logs/<name>/` 的 `index.md`、`decisions.md`（有 `plan.md` 也读），对齐现状与已有决策，不凭空开工。
- 借口："我记得这个项目" → 反驳：跨会话记忆会丢；读三份只要几秒，比凭印象搞错方向便宜。

### R2 进来先画全景
首次进入非空项目必须生成/更新 `project_logs/<name>/index.md` 全景（见上方 onboard）；空项目也引导你补一份最小全景。
- 借口："项目很小不用记" → 反驳：小项目最容易被忘；全景是给"未来的你"的地图，不做等于每次从零认路。

### R3 讲人话再动手
做重要改动 / 技术选型前，先用一句话说清"为什么这么干、有什么坑、有哪些备选"，让你学到东西（贴合仓库「老师」角色）。
- 借口："直接做更快，解释浪费 token" → 反驳：你是来学的，不是只来拿结果的；一句话讲清 why，下次你自己才会，长期省时间。

### R4 改完必验证（轻关卡）
动了关键代码，跑 `index.md` 里记的 test / build 命令确认没坏；不知道命令就明确提醒你跑，绝不"看起来对"就算完。
- 借口："改动很小肯定没问题" → 反驳：小改动照样让编译挂、把接口悄悄改坏；跑一下比事后 debug 便宜。
- 借口："测试太慢 / 我不知道命令" → 反驳：不知道就明确提醒你跑，别把"没验"当成"验过"。

### R5 出错停线排查（借 debugging 五步）
报错 / 测试挂时，先停手别加新功能 → 复现 → 定位根因 → 修根因不修表象 → 补一个防复发的验证。不瞎猜、不跳过。
- 借口："这个 bug 先记着，我先把功能写完" → 反驳：bug 会传染；带着错写新功能只会堆更多错。
- 借口："加个 try-catch 把错误吞了就行" → 反驳：吞错是埋雷；修根因才是真修。

### R6 决策留痕
重要架构 / 选型写进 `decisions.md`，记清 context（为什么走到这）/ 选了什么 / 否决了什么 / 后果。不只在脑子里。
- 借口："这次就是个小决定，不用写" → 反驳：三个月后你不会记得为什么这么选；写下来是给未来的自己省一次重新调研。

### R7 新手安全网
主动指出你可能忽略的点——边界条件、错误处理、输入校验、安全、性能、可读性——哪怕你没问（你自述是菜鸟、会忽略很多，正因如此才要主动补位）。
- 借口："用户没要求我就别啰嗦" → 反驳：你明确说过会忽略很多；正因如此才要我主动补位，而不是等你踩了才知道。

## 设计原则（为什么没有子命令）

`project` 只负责"**收纳 + 切换上下文**"，不做项目过程管理的具体命令（不提供 `log` / `retro` / `add` / `clone` 子命令）。原因：

- 记进展、复盘、沉淀这些是**普通的文件编辑 / `$project-capture` 调用**，不需要专门子命令；`project` 用"项目模式说明"指引用户即可。
- 保持 skill 职责单一：获取项目 = `project`，推送成果 = `sync`，初始化仓 = `start`，三者不重叠。
- 远程 clone、本地软链、新建空项目，统一由"一个参数 + 自动判别"覆盖，无需用户记子命令。

## Gotchas（真实踩过的坑）
- **收纳默认软链，不要默认移动**：`mv` 会破坏用户原项目路径；除非用户显式要"迁移"，否则用软链。
- **onboard 只做一次**：由 `.buildconfig` 的 `onboarded` 列表保证——首次进入非空已有项目时盘点并写入标记，之后因标记存在不再触发；禁止每次进入都重做全盘扫描（会覆盖用户已写的笔记）。
- **笔记只进 `project_logs/<name>/`**：代码、构建产物等放 `project/<name>/`（独立 git，父仓库忽略）；`sync` 只收 `project_logs/`，绝不把代码推回 grounds。
- **current_project 是模式标记，不是数据**：它只告诉后续 skill"当前上下文是哪个项目"，不存放笔记内容。
- **`.buildconfig` 不进 sync**：它是派生仓自己的配置，推回 grounds 时排除（见 sync skill）。
