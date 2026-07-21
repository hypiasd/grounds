---
name: start
description: 从 grounds 远程拉取最新版本（git pull --rebase origin main），并做最小连通性预检。只接受手动 / $ 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# start

## 何时用（触发）
- 用户说"拉取最新"、"pull 一下"、"更新一下仓库"、"start"。
- 想把 grounds 远程（`origin/main`）的最新改动拉到本机当前工作仓。

**只接受手动 / `$` 触发**：agent 不得基于用户消息内容自动调用。

## 目标（完成时状态）
- 当前工作仓已与 grounds 远程 `origin/main` 拉齐（`git pull --rebase origin main` 成功，或本地已是最新）。
- 已报告拉取结果（fast-forward / 已最新 / 有冲突需手动解）。

> 单一 grounds 模型下，agent 文件（`.agents/` 等）与笔记同仓同 git 历史，所以 `git pull` 自然把最新 skills 与笔记一并拉齐——**`start` 只负责「拉」，不负责「推」**。推送由各 skill 提交后自己 `git push origin main` 完成。

## 流程

### 第一步：确认是 grounds 工作仓
```bash
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && echo OK || echo NOT_GIT
```
- `NOT_GIT` → **停止**，提示用户先：
  ```bash
  git clone git@github.com:hypiasd/grounds.git <dir> && cd <dir>
  ```
- `OK` → 继续。

### 第二步：连通性 / 身份预检（受限网络逃生通道）
若 `ssh -T git@github.com` 超时，多半是直连 github.com 的 22 端口被防火墙阻断。改走 SSH-over-HTTPS，在 `~/.ssh/config` 写入：
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

### 第三步：拉取最新（rebase 保持线性）
```bash
git pull --rebase origin main
```
- 冲突 → **停下**告知用户手动解决（`git status` 看冲突文件），不静默覆盖。
- 成功 → 打印结果（已 fast-forward / 已最新 / rebase 完成）。

---

## Gotchas
- **pull 用 `--rebase` 而非 merge**：避免一堆无意义 merge commit，历史保持线性。
- **冲突别静默覆盖**：rebase 冲突必须停下手解，不能自动 `--ours` 强推。
- **只拉不推**：`start` 只把远程最新拉到本机；推送由各个 skill 自己 `git push origin main`（如 learn-capture 提交后即推）。
- **SSH 逃生通道**：直连 github.com 22 端口常被封，`ssh.github.com:443` 可绕过（见第二步）。
- **新机器先配 SSH 再 start**：未通过认证时停下，不继续。
