---
name: project
description: 把项目收纳进 project/<name>/ 并切换到「项目模式」——根据参数自动判别（URL 则 clone、本地目录则软链、纯名字则新建空项目），更新 .buildconfig 的 current_project，并打印该项目模式下如何记进展、复盘、沉淀、sync 的指引。非空已有项目首次进入会做 onboard 盘点。只接受手动 / `$` 触发。
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
- 若是**非空已有项目**首次进入 → 已自动 onboard（生成 `notes/index.md` + `notes/decisions.md`）。
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
- `MODE=new`：`ARG` 是纯名字 → 在 `project/<name>/` 下建空项目（含 `notes/`）。

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
    mkdir -p "project/$NAME/notes"
    touch "project/$NAME/.gitkeep"
    ;;
esac
# 任何模式都确保 notes/ 存在
mkdir -p "project/$NAME/notes"
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
# 检测"非空已有项目"：project/$NAME/ 下除 .gitkeep / notes 外是否还有内容
# MODE=new 新建的空壳不含这些内容 → 不触发 onboard
# MODE=link/clone 拉来的非空仓库 → 触发 onboard（仅一次）
cnt=$(find "project/$NAME" -mindepth 1 -maxdepth 1 \
        -not -name .gitkeep -not -name notes 2>/dev/null | head -1)
if [ -n "$cnt" ]; then
  echo "ONBOARD=yes"   # 命中：执行下方 onboard 盘点（生成 notes/index.md + notes/decisions.md）
else
  echo "ONBOARD=no"    # 空壳 / 新建：跳过，绝不生成 onboard 笔记（避免覆盖用户已写内容）
fi
```

若满足，则 agent **主动盘点现状**，生成两份笔记（写进 `project/$NAME/notes/`）：

1. `notes/index.md`：
   - 项目是什么（从 README / 目录名推断）。
   - 结构地图（列主要子目录 / 模块）。
   - 当前状态 / 卡点（从近 N 条 commit 推断）。
   - 待办（从 issue / TODO 注释 / 最近 WIP commit 提取）。
   - 外部仓库 URL + 本地路径（让 grounds 能指回去）。
2. `notes/decisions.md`：从 commit / PR 记录提炼已有决策（ADR 雏形）；**不确定的地方标"待确认"**。

> onboard 是自动动作，**不是子命令**。只在"进入一个非空已有项目"时触发一次；之后改项目就直接记 `log.md` / 更新 `index.md`，不再重做全盘盘点。

### 第五步：打印「项目模式说明」

无论哪个 MODE，进入后都向用户打印：

```
已进入项目模式：<name>
- 项目位置：project/<name>/（clone/软链/新建）
- 记进展/卡点：编辑 project/<name>/notes/log.md
- 复盘：更新 project/<name>/notes/index.md 的状态与待办
- 踩坑/通用知识点：用 $capture 沉淀；带 wiki 路由标记的笔记会在 $sync 时进入 wiki/
- 原子决策：重要的架构选择补进 project/<name>/notes/decisions.md
- 干完了：用 $sync 把 project/<name>/notes/ 推回 grounds
```

## 设计原则（为什么没有子命令）

`project` 只负责"**收纳 + 切换上下文**"，不做项目过程管理的具体命令（不提供 `log` / `retro` / `add` / `clone` 子命令）。原因：

- 记进展、复盘、沉淀这些是**普通的文件编辑 / `$capture` 调用**，不需要专门子命令；`project` 用"项目模式说明"指引用户即可。
- 保持 skill 职责单一：获取项目 = `project`，推送成果 = `sync`，初始化仓 = `start`，三者不重叠。
- 远程 clone、本地软链、新建空项目，统一由"一个参数 + 自动判别"覆盖，无需用户记子命令。

## Gotchas（真实踩过的坑）
- **收纳默认软链，不要默认移动**：`mv` 会破坏用户原项目路径；除非用户显式要"迁移"，否则用软链。
- **onboard 只做一次**：仅在"进入非空已有项目"时自动盘点；之后改项目按说明记 `log.md` / 更新 `index.md`，禁止每次进入都重做全盘扫描（会覆盖用户已写的笔记）。
- **笔记只进 `project/<name>/notes/`**：代码、构建产物等放 `project/<name>/` 其它位置；`sync` 只收 `notes/`，绝不把代码推回 grounds。
- **current_project 是模式标记，不是数据**：它只告诉后续 skill"当前上下文是哪个项目"，不存放笔记内容。
- **`.buildconfig` 不进 sync**：它是派生仓自己的配置，推回 grounds 时排除（见 sync skill）。
