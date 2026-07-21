---
name: sync
description: 把当前 grounds 工作仓的改动同步到 grounds 远程（pull --rebase 取最新 + push 本仓改动），并可选遍历 project/* 各独立仓分别 push。无子命令，单条 $sync 即完成。只接受手动 / $ 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# sync

## 何时用（触发）
- 用户说"同步一下"、"推一下"、"sync"、"拉一下最新"。
- 当前 grounds 工作仓产生了笔记（wiki/ paper/ video/ project_logs）或改进了 agent 文件，需要推回 grounds 远程 / 拉取其他机器（他人）的改动。

**只接受手动 / `$` 触发**：agent 不得基于用户消息内容自动调用。

## 动作总览（无子命令，单条 `$sync`）

| 步骤 | 方向 | 动作 |
|---|---|---|
| ① 拉取 | 远程 → 本仓 | `git pull --rebase origin main` 取 grounds 远程最新（agent 文件与笔记都是普通跟踪文件，一并拉齐） |
| ② 推送 | 本仓 → 远程 | `git push origin main` 推本仓改动 |
| ③ 项目仓 | 各自独立 | 可选：遍历 `project/*/`（各是独立 git 仓），分别 `git push` 自己的远程 |

> **模型说明**：单一 grounds 仓下，agent 文件（`.agents` 等）与笔记**同仓同 git 历史**，因此不再有"覆盖式 `AGENT_FILESET` 同步"与"笔记线 / agent 线分流"——全部由普通 `git pull/push` 完成。`$sync` 本质是一次"先 rebase 拉齐、再 push"的安全包装。切换机器前跑一次 `$sync` 即保证各端一致。

## 环境预检（关键）

**受限网络（GitHub 22/443 被封）逃生通道**：若 `ssh -T git@github.com` 超时，多半是直连 github.com 的 22 端口被防火墙阻断。改走 SSH-over-HTTPS，在 `~/.ssh/config` 写入：
> ```
> Host github.com
>     Hostname ssh.github.com
>     Port 443
>     User git
>     IdentityFile ~/.ssh/id_ed25519
>     StrictHostKeyChecking no
> ```
> 连通性预检：
> ```bash
> ssh -T -o ConnectTimeout=8 git@github.com 2>&1 | grep -q "successfully authenticated" \
>   && echo "SSH OK" || echo "SSH 不通，检查上面的逃生通道 / 代理"
> ```

**git 身份保障（commit 前必做）**：受限 / 临时环境常缺 `user.name/email`。本 skill 用仓库级兜底（优先复用历史作者，不动 --global）：
> ```bash
> git config user.email >/dev/null 2>&1 || git config user.email "$(git log -1 --format=%ae 2>/dev/null || echo you@example.com)"
> git config user.name  >/dev/null 2>&1 || git config user.name  "$(git log -1 --format=%an 2>/dev/null || echo you)"
> ```

## 流程

### 第一步：脏检查（有未提交改动先提交）
```bash
git status --porcelain
```
- 若有未提交改动 → 按「提交规范」分文件 `git add <具体文件>` + `git commit`（**绝不 `git add -A`**，避免误吞 `project/` 内容或 `raw/` 本地资料——虽 `.gitignore` 已兜底，仍保持好习惯）。
- 若无改动 → 直接进入第二步。

### 第二步：拉取最新（rebase 避免无谓 merge commit）
```bash
git pull --rebase origin main
```
- 若 rebase 冲突 → **停下**告知用户手动解决（`git status` 看冲突文件），不要静默覆盖。
- 若本地落后且无冲突 → 自动 fast-forward / rebase 完成。

### 第三步：推送本仓
```bash
git push origin main
```
- 失败（如远端有未拉取的更新）→ 回到第二步重 pull 再 push；仍失败则提示用户检查网络 / 权限。

### 第四步（可选）：遍历 project/* 各独立仓 push
```bash
for p in project/*/; do
  [ -d "$p/.git" ] || continue
  (
    cd "$p"
    git push 2>/dev/null && echo "已推 $p" || echo "⚠️ $p 推送失败（可能未设远程）"
  )
done
```
- `project/<name>/` 是各自独立的 git 仓（父仓库 `.gitignore` 忽略其内容），**不走 grounds**，各自推自己的远程。

### 第五步：收尾提示
```
sync 完成：
- 本仓：已 pull --rebase + push 到 grounds 远程
- project/*：<已分别 push | 无独立仓>
```

---

## Gotchas（真实踩过的坑）
- **别 `git add -A`**：即便 `.gitignore` 已忽略 `project/`、`raw/`、`video/` 中间产物，仍保持有范围 add，防止某天 `.gitignore` 规则变动误吞。
- **pull 用 `--rebase` 而非 merge**：避免产生一堆无意义的 merge commit，历史保持线性。
- **冲突别静默覆盖**：rebase 冲突必须停下手解，不能自动 `--ours` 强推。
- **SSH 逃生通道**：直连 github.com 22 端口常被封，`ssh.github.com:443` 可绕过（见「环境预检」）。
- **commit 前保障仓库级身份**：临时 / 受限环境缺 `user.name/email` 时按历史作者补仓库级配置，否则 commit 失败。
- **project 仓独立**：`project/<name>/` 各自 git，父仓忽略；sync 绝不把它们推上 grounds。
- **agent 文件随 git 走**：单一 grounds 下 `.agents` 等是普通跟踪文件，`$sync` 的 pull/push 自然覆盖其同步，无需覆盖式机制。
