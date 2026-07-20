---
name: start
description: 把当前目录（须是 workBase 的 clone）初始化为可用的派生工作仓——建内容占位目录、写 .buildconfig、移除指向 workBase 的 origin，使其成为一个零内容、全技能可用的临时派生仓。只接受手动 / `$` 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# start

## 何时用（触发）
- 用户说"初始化工作仓"、"start 一下"、"用 start 初始化"。
- 一台新机器 / 新目录已 clone 了 workBase，需要把它变成一个能跑全部 skill 的空壳派生仓。

**只接受手动 / `$` 触发**：agent 不得基于用户消息内容自动调用。

## 目标（完成时仓库应处于的状态）
- 当前目录已是一个**派生工作仓**：
  - 含 agent 文件集（本就来自 workBase clone，无需新建）。
  - 含内容占位目录 `wiki/ paper/ video/ raw/ project/`（各放 `.gitkeep`）。
  - 含 `.buildconfig`（声明本仓角色、grounds 远程、workBase 远程）。
  - **origin 不再指向 workBase**（避免误把内容推回基类）。

## agent 文件集（本 skill 不改动，仅作为"我已继承"的证据）

```
.agents/  AGENTS.md  CLAUDE.md  CODEBUDDY.md  .claude  .codebuddy  .qoder  .trae
```

以上由 workBase clone 提供，start 不创建也不修改它们。复制 / 同步这些文件时务必**保留软链**（`cp -R` / `rsync -a`，不要解引用），否则 `.claude → .agents` 等链接会失效。

## 流程

### 第一步：前置校验

确认当前目录是 workBase 的 clone（已含 agent 文件集）：

```bash
test -d .agents -a -f AGENTS.md && echo OK || echo MISSING
```

- 输出 `OK` → 继续。
- 输出 `MISSING` → **停止**，告诉用户：「当前目录不是 workBase 的 clone（缺少 `.agents/` 或 `AGENTS.md`）。请先 `git clone git@github.com:hypiasd/workBase.git <dir> && cd <dir>` 再运行 `$start`。」
- 若 `.buildconfig` 已存在 → 视为"已初始化"，提示「当前目录似乎已经 start 过了（.buildconfig 存在）。如需重置请先删除 `.buildconfig` 再跑。」然后停止（不重复初始化，避免覆盖已有项目）。

### 第二步：建内容占位目录

```bash
for d in wiki paper video raw project; do
  mkdir -p "$d"
  touch "$d/.gitkeep"
done
```

> 占位目录让 `learn` / `capture` / `project` / `sync` 即刻可用，且 git 能跟踪空目录。

### 第三步：写 `.buildconfig`

写入仓库根 `.buildconfig`（纯 key=value，便于 shell `source` 读取）：

```bash
cat > .buildconfig <<'EOF'
role=temp-derived
grounds_url=git@github.com:hypiasd/grounds.git
workbase_url=git@github.com:hypiasd/workBase.git
# 可选：本机已有 grounds 本地路径，sync 时优先直接用，省去 clone
local_grounds_path=
# 可选：当前处于项目模式的项目名（由 project skill 维护）
current_project=
EOF
```

- `role`：固定 `temp-derived`（主派生类 grounds 自身为 `main-derived`）。
- `local_grounds_path`：留空即可；本机已有 grounds（如 `/Users/tian/Documents/sys/grounds`）填上去能让 `sync` 跳过 clone。

### 第四步：处理 origin

本仓是从 workBase clone 来的，origin 当前指向 **workBase**。临时派生仓是独立 git 仓库，内容**绝不能推回 workBase**。所以：

```bash
git remote remove origin
```

- 若用户**想保留**自己的远程（给临时仓建了独立 repo），应在跑 `start` 前自己 `git remote set-url origin <自己的URL>` 或 `git remote add mine <URL>`；`start` 只负责**移除指向 workBase 的 origin**，不碰其他 remote。
- 移除后提示：「已移除指向 workBase 的 origin，避免内容误推回基类。如需把本仓备份到自己的远程，请手动 `git remote add origin <你的URL>`。」

### 第五步：校验 + 收尾

```bash
test -f .buildconfig && test -d project && echo "start OK"
```

打印给用户：

```
派生工作仓已就绪（零内容、全技能可用）：
- 内容目录：wiki/ paper/ video/ raw/ project/ 已建好
- .buildconfig：role=temp-derived，已指向 grounds / workBase 远程
- origin：已移除指向 workBase 的引用

接下来：
- 用 $project <name|path|url> 收纳一个项目并进入项目模式
- 用 $learn / $capture 沉淀通用知识（笔记写进 wiki/）
- 干完了用 $sync 把笔记推回 grounds、把 agent 改进推回 workBase
```

## Gotchas（真实踩过的坑）
- **复制 agent 文件集必须保留软链**：`.claude` 是软链到 `.agents`，`.codebuddy/.qoder/.trae` 内含软链到 `.agents/skills`。任何 `cp` 都要 `-R`（macOS 默认不跟随符号链接，符合预期），切勿用 `cp -L` 或解引用。
- **已 start 过不重复**：检测到 `.buildconfig` 直接停止，不要覆盖用户已有的 `project/` 内容。
- **start 不碰 agent 文件集**：本 skill 只建内容目录 + 写配置 + 处理 origin；agent 文件集的更新由 `sync pull`（拉基类）和 `sync`（push-agent 推回基类）负责。
- **不要 git add -A 后乱 commit**：start 只应新增占位目录与 `.buildconfig`，不碰 agent 文件集的既有跟踪状态。
