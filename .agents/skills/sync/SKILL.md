---
name: sync
description: 把派生仓的笔记推回 grounds、把 agent 改进推回 workBase（push 模式）；或把 workBase 的最新 agent 文件集拉回本仓（pull 模式）。只接受手动 / `$` 触发。push 模式下：读 .buildconfig，复制 wiki/ paper/ video/ project/*/notes/ 到 grounds（排除 agent 文件集与 .buildconfig），并覆盖式推送本仓 agent 文件集到 workBase。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# sync

## 何时用（触发）
- 用户说"同步一下"、"推回 grounds"、"sync"、"拉一下基类 / sync pull"。
- 派生仓产生了笔记（wiki/ paper/ video/ project）或改进了 agent 文件集，需要推回上游。

**只接受手动 / `$` 触发**：agent 不得基于用户消息内容自动调用。

## 两种模式

| 模式 | 触发 | 动作 |
|---|---|---|
| **push**（默认，`$sync`） | 推送本地成果 | ① 笔记 → grounds；② agent 改进 → workBase |
| **pull**（`$sync pull`） | 接收基类更新 | workBase 的 agent 文件集 → 覆盖本仓 |

## agent 文件集（固定清单，push / pull 都用）

```
AGENT_FILESET=".agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae"
```

复制 / 覆盖这些文件时务必**保留软链**（`cp -R` / `rsync -a`，不要解引用）。`.claude` 是软链到 `.agents`，`.codebuddy/.qoder/.trae` 内含软链到 `.agents/skills`——解引用会让链接失效。

> ⚠️ **zsh 兼容性**：zsh 不会按空格自动分词。bash 块里**凡涉及文件集的循环，一律用字面列表** `.agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae`，不要写 `for f in $AGENT_FILESET`（zsh 下 `$AGENT_FILESET` 会被当成一个词，循环失效）。

---

# push 模式（`$sync`）

## 目标（完成时状态）
- `wiki/ paper/ video/ project/*/notes/` 已覆盖式推到 grounds 远程。
- 本仓的 agent 文件集已覆盖式推到 workBase 远程。
- 冲突策略：**本地优先覆盖**（派生仓是本次创作的真相源）。

## 流程

### 第一步：读 .buildconfig

```bash
set -a; . ./.buildconfig; set +a
# 现在可用：$role  $grounds_url  $workbase_url  $local_grounds_path  $current_project
```

- 若 `.buildconfig` 不存在 → 停止，提示「当前目录未初始化（缺 .buildconfig）。请先 `$start`，或用 `$project` 进入项目模式。」
- **角色保护**：若 `role=main-derived`（即本仓就是 grounds 本身）→ 停止，提示「grounds 是笔记目的地，不能对自己 sync push。请在临时派生仓里运行 `$sync`。」

### 第二步：准备 grounds 本地副本

```bash
if [ -n "$local_grounds_path" ] && [ -d "$local_grounds_path/.git" ]; then
  GROUNDS="$local_grounds_path"
  git -C "$GROUNDS" pull --ff-only 2>/dev/null || true
else
  GROUNDS=$(mktemp -d)
  git clone "$grounds_url" "$GROUNDS"
fi
```

### 第三步：合并式复制笔记（排除 agent 文件集与 .buildconfig）

**关键语义：本地优先、合并而非替换。** 只把本仓**有的**内容合入 grounds，绝不用本仓的空占位目录去 `rm -rf` 删除 grounds 里已有的真实笔记。grounds 中本仓没有的文件必须保留。

只收**内容目录**，且 `project/` 下**只收 `*/notes/`**，绝不收项目代码：

```bash
# 合并式复制：rsync -a（本地文件优先覆盖同名、保留远程独有）；无 rsync 时回退 cp -R 内容
for d in wiki paper video; do
  [ -d "$d" ] || continue
  mkdir -p "$GROUNDS/$d"
  rsync -a "$d/" "$GROUNDS/$d/" 2>/dev/null || cp -R "$d/." "$GROUNDS/$d/"
done
# project 只收各项目的 notes/（合并式，保留 notes/ 子目录本身）
mkdir -p "$GROUNDS/project"
for p in project/*/; do
  name=$(basename "$p")
  [ -d "$p/notes" ] || continue
  mkdir -p "$GROUNDS/project/$name"
  # 源不带尾斜杠：rsync 复制 notes/ 目录本身，落到 grounds 的 project/<name>/notes/
  rsync -a "$p/notes" "$GROUNDS/project/$name/" 2>/dev/null || cp -R "$p/notes" "$GROUNDS/project/$name/"
done
```

> 关键点：用 `rsync -a`（或 `cp -R 内容`）**合并**，不加 `--delete`，所以 grounds 里本仓没有的笔记、paper、video **全部保留**；本仓有而 grounds 没有的文件被新增；两边同名的冲突文件以**本地（本仓）为准**覆盖。
> `project/*/notes/` 之外的代码、构建产物**不复制**，所以 grounds 永不被项目代码撑大。
> agent 文件集（`.agents` 等）和 `.buildconfig` **不复制**——它们不属于"笔记"，agent 改动走下面的 push-agent。

### 第四步：提交 + 推送 grounds（本地优先）

```bash
cd "$GROUNDS"
# 本地优先：先合入远程新增（如有），冲突以本地为准
git add -A
git commit -m "sync: 推送派生仓笔记 $(date +%Y-%m-%dT%H-%M)" || echo "nothing to commit"
git pull --no-edit -X ours "$grounds_url" main 2>/dev/null || true
git push "$grounds_url" main
```

- 若本机直接用 `local_grounds_path`：`git push` 即可（已 pull --ff-only）。
- 若用临时 clone：push 后 `rm -rf "$GROUNDS"` 清理。
- `git commit` 无变更时会失败（`|| echo`），属正常（说明本地没有新笔记），不阻塞。

### 第五步：push-agent（agent 改进 → workBase）

把本仓的 agent 文件集覆盖式推回 workBase：

```bash
WB=$(mktemp -d)
git clone "$workbase_url" "$WB"
# 用本仓 agent 文件集覆盖 workBase（字面列表，zsh 不自动分词）
for f in .agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae; do
  rm -rf "$WB/$f"
  [ -e "$f" ] && cp -R "$f" "$WB/"
done
cd "$WB"
git add -A
git commit -m "sync: 派生仓推送 agent 改进 $(date +%Y-%m-%dT%H-%M)" || echo "agent 无变更"
git push "$workbase_url" main
rm -rf "$WB"
```

> 这是"派生仓 agent 改动直接覆盖基类仓"的语义：派生仓为准，覆盖式推送，不做三方合并。若 workBase 被别人同时改了，会以本仓为准（覆盖）。需要并发协调时，先 `$sync pull` 接收再改。

### 第六步：收尾提示

```
sync push 完成：
- 笔记已推到 grounds（wiki/ paper/ video/ project/*/notes/）
- agent 改进已推到 workBase
- 本地优先：本次内容覆盖远程同名文件
```

---

# pull 模式（`$sync pull`）

## 目标（完成时状态）
- workBase 的最新 agent 文件集已覆盖式拉回本仓并推送本仓远程。
- 用于"接收基类更新"：grounds 用它收基类改动，临时仓用它保持最新。

## 流程

```bash
set -a; . ./.buildconfig; set +a
WB=$(mktemp -d)
git clone "$workbase_url" "$WB"
# 用 workBase 的 agent 文件集覆盖本仓（字面列表，zsh 不自动分词）
for f in .agents AGENTS.md CLAUDE.md CODEBUDDY.md .claude .codebuddy .qoder .trae; do
  rm -rf "$f"
  [ -e "$WB/$f" ] && cp -R "$WB/$f" ./
done
rm -rf "$WB"
# 提交并推送本仓（让本仓远程也拿到最新基类）
git add -A
git commit -m "sync pull: 接收 workBase 基类更新 $(date +%Y-%m-%dT%H-%M)" || echo "已是最新"
git push 2>/dev/null || echo "本仓无远程（临时仓未设 origin），跳过 push"
```

> 临时派生仓 `start` 时已移除 origin（避免误推内容回 workBase），所以 `git push` 会失败属正常——本地已拿到最新 agent 即可。若本仓有自己的远程，会正常推送。

---

## Gotchas（真实踩过的坑）
- **复制必须保留软链**：`cp -R` 在 macOS 默认不跟随符号链接（符合预期）；切勿 `-L` / 解引用，否则 `.claude → .agents` 等链接会变成实体副本，pull 后链接关系丢失。
- **grounds 自身不能 push**：`role=main-derived` 时必须拒绝，否则会把自己当目的地又推自己，逻辑死循环。
- **project 只收 `*/notes/`**：项目代码、构建产物绝不能进 grounds（那是目的地，不是代码仓）。
- **`.buildconfig` 不进 sync**：它是派生仓私有配置，推回 grounds 时排除。
- **push-agent 是覆盖式，不是合并**：派生仓改了 agent 就以其为准覆盖 workBase；多机并发改 agent 时，先 `sync pull` 接收再改，避免互相覆盖。
- **临时 clone 要清理**：push / pull 用 `mktemp -d` 建临时区，结束务必 `rm -rf`，不留中间产物污染仓库。
- **`git commit` 无变更会失败**：用 `|| echo` 接住，不要让它中断整个 sync。
