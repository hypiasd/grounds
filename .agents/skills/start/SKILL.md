---
name: start
description: 在全新机器 / 新目录准备一个可用的 grounds 工作仓。单一 grounds 模型下只需 git clone grounds.git 即可；本 skill 做校验 + SSH 检查，无额外初始化。只接受手动 / $ 触发。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# start

## 何时用（触发）
- 用户说"初始化工作仓"、"start 一下"、"用 start 初始化"。
- 一台新机器 / 新目录，需要准备一个能跑全部 skill 的 grounds 工作仓。

**只接受手动 / `$` 触发**：agent 不得基于用户消息内容自动调用。

## 目标（完成时状态）
- 当前目录已是一个 **grounds 工作仓**（含 agent 文件集 `.agents/` + `AGENTS.md` 及各 agent 软链，以及全部内容目录 `wiki/ paper/ video/ raw/ project/ project_logs/ quartz/`）。
- 已配好 GitHub SSH 认证，可随时 `$sync`。

> 单一 grounds 模型下**无需** `.buildconfig`、无需移除 origin（origin 就是 grounds）、无需建占位目录（grounds 自带）。`$start` 只做校验与提示。

## 流程

### 第一步：前置校验

确认当前目录是 grounds 的工作仓（已含 agent 文件集与内容目录）：

```bash
test -d .agents -a -f AGENTS.md -a -d wiki -a -d project_logs && echo OK || echo MISSING
```

- 输出 `OK` → 跳到第二步（SSH 检查）。
- 输出 `MISSING` → **停止**，提示用户：
  「当前目录不是 grounds 工作仓。请先：
  ```bash
  git clone git@github.com:hypiasd/grounds.git <dir> && cd <dir>
  ```
  再运行 `$start`（或 clone 后直接开始，无需 `$start`）。」

### 第二步：SSH 认证检查（新设备必须配，否则 `$sync` 推拉会失败）

```bash
echo "== 检查 GitHub SSH 认证 =="
if ssh -T -o StrictHostKeyChecking=accept-new -o BatchMode=yes git@github.com 2>&1 | grep -qi "successfully authenticated"; then
  echo "SSH_OK"
else
  echo "SSH_FAIL"
fi
```

- `SSH_OK` → 完成，打印收尾提示。
- `SSH_FAIL` → **停止**，打印配置指引：

  > **本机还没配好 GitHub SSH key，`$sync` 无法推拉 grounds。请：**
  > 1. 生成 key（没有的话）：`ssh-keygen -t ed25519 -C "你的邮箱"`
  > 2. 公钥贴到 GitHub：复制 `cat ~/.ssh/id_ed25519.pub` → Settings → SSH and GPG keys → New SSH key
  > 3. 若 key 有 passphrase：`ssh-add ~/.ssh/id_ed25519`
  > 4. 验证：`ssh -T git@github.com` 出现 "successfully authenticated"
  > 配好后再跑一次 `$start`。

### 第三步：收尾提示

```
grounds 工作仓已就绪（全技能可用）：
- agent 文件集：.agents/ + AGENTS.md + 各 agent 软链（Claude/Codex/CodeBuddy/Qoder/Trae 均已桥接）
- 内容目录：wiki/ paper/ video/ raw/ project/ project_logs/ quartz/ 齐备
- origin：指向 grounds.git（即推送目的地，无需改动）

接下来：
- 用 $project <name|path|url> 收纳一个项目并进入项目模式
- 用 $learn-capture 沉淀通用知识（写进 wiki/）、用 $project-capture 沉淀项目笔记（写进 project_logs/<name>/）
- 干完了用 $sync 把改动推回 grounds 远程、并拉取其他机器的更新
```

---

## Gotchas
- **本 skill 不创建 / 不修改 agent 文件集与内容目录**：它们由 `git clone grounds.git` 提供。不要手建占位目录或软链（易错且会破坏软链关系）。
- **复制 agent 文件集必须保留软链**：若手动搬运，`.claude → .agents`、`.codebuddy/.qoder/.trae` 内含 `skills → ../.agents/skills` 都是软链，须 `cp -a` 保留，切勿解引用。
- **新设备先配 SSH 再 start**：未通过认证时停下，不继续。
- **单一 grounds：无 .buildconfig、无 origin 移除**：与旧版派生仓模型不同，别残留这些步骤。
