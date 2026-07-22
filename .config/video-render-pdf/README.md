# video-render-pdf API 配置

本目录存放 `video-render-pdf` skill 的本地 API key，**这些文件被 `.gitignore` 排除，不会进入 git**。

## SiliconFlow API Key

`video-render-pdf` 使用 SiliconFlow 的远程 OCR / ASR API 作为帧评估和语音转录回退。

创建文件：

```bash
# 在 grounds 仓库根目录执行
echo "sk-xxxxxxxxxxxxxxxx" > .config/video-render-pdf/siliconflow_key
chmod 600 .config/video-render-pdf/siliconflow_key
```

## 优先级

脚本读取 key 时按以下顺序查找：

1. ` grounds 仓库根目录/.config/video-render-pdf/siliconflow_key`（推荐，与本仓库绑定）
2. `~/.config/video-render-pdf/siliconflow_key`（旧位置，向后兼容）
3. 环境变量 `SILICONFLOW_API_KEY`

找到第一个即停止。

## 安全提醒

- 不要把 key 提交到 git。
- 不要把 key 放在 `.env`、笔记或脚本里。
- 若误提交，立即到 SiliconFlow 控制台重置 key。
