---
name: sync
description: 把派生仓的笔记推回 grounds（按仓库名判定是否 grounds），agent 文件集按更新时间定方向与 workBase 同步（推/拉）。无子命令，单条 `$sync` 即完成。只接受手动 / `$` 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# sync

## 何时用（触发）
- 用户说"同步一下"、"推回 grounds"、"sync"、"接收基类更新 / 拉一下基类"。
- 派生仓产生了笔记（wiki/ paper/ video/ project_logs）或改进了 agent 文件集，需要推回上游。

**只接受手动 / `$` 触发**：agent 不得基于用户消息内容自动调用。

## 动作总览（无子命令，单条 `$sync`）

| 步骤 | 方向 | 判定 / 动作 |
|---|---|---|
| ① 推笔记 | 本仓 → grounds | **仅当本仓不是 grounds**（按仓库名判定）才推；合并式推 `wiki/ paper/ video/ project_logs/` |
| ② agent 同步 | 双向 | **按更新时间定方向**：本仓 agent 最近提交比 workBase 新 → 推；workBase 更新 → 拉；相同 → 跳过 |

> **两个判定原则（按你的要求）**：
> 1. **agent 推还是拉，看更新时间**：比较本仓与 workBase 上 agent 文件集的最近提交时间，谁新谁赢，不再"本地必胜"。
> 2. **是否 grounds，看仓库名**：目录名 `grounds` 或远端 URL 含 `grounds` 即视为目的地，不再依赖 `.buildconfig` 的 `role` 字段。

## agent 文件集（固定清单，步骤② agent 同步用）

```
AGENT_FILESET=".agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae"
```

复制 / 覆盖这些文件时务必**保留软链**（`cp -R` / `rsync -a`，不要解引用）。`.claude` 是软链到 `.agents`，`.codebuddy/.qoder/.trae` 内含软链到 `.agents/skills`——解引用会让链接失效。

> ⚠️ **zsh 兼容性**：zsh 不会按空格自动分词。bash 块里**凡涉及文件集的循环或 git 命令（`for` / `git log` / `git status`），一律内联字面列表** `.agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae`，不要写 `$AGENT_FILESET`（zsh 下不会被拆成多个参数，导致匹配失败）。

---

# 流程

## 目标（完成时状态）
- （若非 grounds）`wiki/ paper/ video/ project_logs/` 已合并式推到 grounds 远程。
- agent 文件集已按"更新时间"方向与 workBase 同步（推 / 拉 / 跳过其一）。
- 冲突策略：agent 以**较新一方为准**（按提交时间判，非硬编码本地优先）。

### 第一步：读 .buildconfig + 判定是否 grounds

```bash
set -a; . ./.buildconfig; set +a
# 现在可用：$grounds_remote  $workbase_remote  $local_grounds_path  $current_project

# 按仓库名判定是否 grounds（目录名 / 远端 URL 任一含 grounds 即算）
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
REPO_NAME=$(basename "$REPO_ROOT")
REMOTE_HINT=$(git remote -v 2>/dev/null | tr 'A-Z' 'a-z')
IS_GROUNDS=false
case "$REPO_NAME" in grounds) IS_GROUNDS=true ;; esac
echo "$REMOTE_HINT" | grep -q grounds && IS_GROUNDS=true
```

- 若 `.buildconfig` 不存在 → 停止，提示「当前目录未初始化（缺 .buildconfig）。请先 `$start`，或用 `$project` 进入项目模式。」
- **是否 grounds（按仓库名）**：若 `IS_GROUNDS=true`，本仓就是笔记目的地，**跳过笔记推送**（不能推给自己）；但 agent 同步仍按时间照常进行。

### 第二步：准备 grounds 本地副本（仅非 grounds 时）

```bash
if $IS_GROUNDS; then
  echo "本仓是 grounds（按仓库名判定），跳过笔记推送。"
else
  if [ -n "$local_grounds_path" ] && [ -d "$local_grounds_path/.git" ]; then
    GROUNDS="$local_grounds_path"
    git -C "$GROUNDS" pull --ff-only 2>/dev/null || true
  else
    GROUNDS=$(mktemp -d)
    git clone "$grounds_remote" "$GROUNDS"
  fi
fi
```

### 第三、四步：合并式复制笔记 + 提交推送（仅非 grounds）

> 仅当 `IS_GROUNDS=false`（本仓不是 grounds）才执行；是 grounds 则整段跳过，不推笔记给自己。

```bash
if ! $IS_GROUNDS; then
  # 合并式复制：rsync -a（保留远程独有）；无 rsync 时回退 cp -R 内容
  for d in wiki paper video project_logs; do
    [ -d "$d" ] || continue
    mkdir -p "$GROUNDS/$d"
    rsync -a "$d/" "$GROUNDS/$d/" 2>/dev/null || cp -R "$d/." "$GROUNDS/$d/"
  done
  # project_logs/ 已在上方的 wiki/paper/video 循环中一并推送（合并式）
  # 提交 + 推送 grounds（本地优先、合并式）
  (
    cd "$GROUNDS"
    git add -A
    git commit -m "sync: 推送派生仓笔记 $(date +%Y-%m-%dT%H-%M)" || echo "nothing to commit"
    git pull --no-edit -X ours "$grounds_remote" main 2>/dev/null || true
    git push "$grounds_remote" main
  )
  # 仅临时 clone 才清理；local_grounds_path 模式保留本地副本
  [ -z "$local_grounds_path" ] && rm -rf "$GROUNDS"
fi
```

> 关键点：用 `rsync -a`（或 `cp -R 内容`）**合并**，不加 `--delete`，所以 grounds 里本仓没有的笔记、paper、video **全部保留**；本仓有而 grounds 没有的文件被新增；两边同名的冲突文件以**本地（本仓）为准**覆盖。
> `project/<name>/` 是独立 git 仓库、父仓库忽略其内容；`project_logs/` 之外的代码、构建产物**不复制**，所以 grounds 永不被项目代码撑大。
> agent 文件集（`.agents` 等）和 `.buildconfig` **不复制**——它们不属于"笔记"，agent 改动走下面的 agent 同步。
> 若本机直接用 `local_grounds_path`：`git push` 即推到本地仓（已 pull --ff-only），且不清理；用临时 clone 则自动 `rm -rf` 清理。`git commit` 无变更时失败（`|| echo`）属正常，不阻塞。

### 第五步：agent 同步（按更新时间定方向）

克隆 workBase，比较本仓与 workBase 上 agent 文件集的**最近提交时间**，决定推 / 拉 / 跳过：

```bash
# 注意：zsh 不按空格分词，$VAR 不能展开成多个参数。
# 下面 git log / git status 一律内联字面列表，不依靠变量展开。
# 本仓 agent 文件集最近提交时间（有未提交改动则视为本地更新）
LOCAL_TS=$(git log -1 --format=%ct -- .agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae 2>/dev/null || echo 0)
LOCAL_DIRTY=$(git status --porcelain -- .agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae 2>/dev/null)
[ -n "$LOCAL_DIRTY" ] && LOCAL_TS=$(date +%s)

WB=$(mktemp -d)
git clone "$workbase_remote" "$WB" >/dev/null 2>&1
BASE_TS=$(cd "$WB" && git log -1 --format=%ct -- .agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae 2>/dev/null || echo 0)

if [ "$LOCAL_TS" -gt "$BASE_TS" ] || [ -n "$LOCAL_DIRTY" ]; then
  # 本仓更新 → 推 agent 到 workBase
  (
    for f in .agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae; do
      rm -rf "$WB/$f"
      [ -e "$f" ] && cp -R "$f" "$WB/"
    done
    cd "$WB"
    git add -A
    git commit -m "sync: 派生仓推送 agent 改进 $(date +%Y-%m-%dT%H-%M)" || echo "agent 无变更"
    git push "$workbase_remote" main
  )
  echo "agent：本仓更新 → 已推到 workBase"
elif [ "$BASE_TS" -gt "$LOCAL_TS" ]; then
  # workBase 更新 → 拉 agent 回本仓
  (
    for f in .agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae; do
      rm -rf "$f"
      [ -e "$WB/$f" ] && cp -R "$WB/$f" ./
    done
    git add -A
    git commit -m "sync: 接收 workBase 基类更新 $(date +%Y-%m-%dT%H-%M)" || echo "已是最新"
    git push 2>/dev/null || echo "本仓无远程（临时仓未设 origin），跳过 push"
  )
  echo "agent：workBase 更新 → 已拉回本仓"
else
  echo "agent：两边时间相同 → 已同步，跳过"
fi
rm -rf "$WB"
```

> **为什么用提交时间而非文件 mtime**：clone / pull 会重置文件 mtime，跨机不可比；git 提交时间是稳定的墙钟时间，可正确判断"谁改得更晚"。本仓有未提交改动时也视为"本地更新"，避免被上游悄悄覆盖。
> 临时派生仓 `start` 时已移除 origin，拉回时 `git push` 失败属正常——本地已拿到最新 agent 即可。

### 第六步：收尾提示

```
sync 完成：
- 笔记：<已推到 grounds | 本仓是 grounds，已跳过>
- agent：<本仓更新→已推 workBase | workBase 更新→已拉回 | 已同步跳过>
```

---

## Gotchas（真实踩过的坑）
- **复制必须保留软链**：`cp -R` 在 macOS 默认不跟随符号链接（符合预期）；切勿 `-L` / 解引用，否则 `.claude → .agents` 等链接会变成实体副本，pull 后链接关系丢失。
- **按仓库名判定 grounds**：目录名 `grounds` 或远端 URL 含 `grounds` 即视为目的地，跳过笔记推送；不再依赖 `.buildconfig` 的 `role` 字段（已移除）。
- **project_logs 整体推送**：项目代码在 `project/<name>/`（各自 git，父仓库忽略），sync 只推 `project_logs/`（笔记），绝不把代码推回 grounds。
- **`.buildconfig` 不进 sync**：它是派生仓私有配置，推回 grounds 时排除。
- **agent 按更新时间定方向，覆盖式而非合并**：谁的最近提交时间新，就以谁为准覆盖对方；多机并发改 agent 时，后 sync 的一方（时间更新）覆盖先 sync 的，需协调时人工确认。
- **临时 clone 要清理**：push / pull 用 `mktemp -d` 建临时区，结束务必 `rm -rf`，不留中间产物污染仓库。
- **`git commit` 无变更会失败**：用 `|| echo` 接住，不要让它中断整个 sync。
