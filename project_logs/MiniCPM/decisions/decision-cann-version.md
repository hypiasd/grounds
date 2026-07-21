---
title: 决策：CANN 版本 beta.3 与指南 beta.1 不一致
tags: [project, MiniCPM, decision]
created: 2026-07-21
updated: 2026-07-21
---

# 决策：CANN 版本 beta.3 与指南 beta.1 不一致

- **问题（what & why）**：指南 4.1 假设 CANN=`cann-9.1.0-beta.1`，但实测机装的是 `cann-9.1.0-beta.3`。CMake 通过 `ASCEND_TOOLKIT_HOME` 定位 CANN，错配会导致找不到 `libascendcl.so` / 编译失败。
- **候选方案**：
  - 方案 A：直接用已安装的 beta.3（推荐）。`ASCEND_TOOLKIT_HOME` 环境变量已指向 beta.3，CMake 会自动采用。
  - 方案 B：降级 / 重装到 beta.1。成本高、风险大、无收益。
- **推荐 + 理由**：选 A。beta.3 是 beta.1 的补丁版，API 兼容；指南本身只要求"启用 CANN 后端"，未强依赖具体补丁号。
- **需要你拍板的点**：是否接受"用 beta.3 替代指南 beta.1"？（默认接受，已确认环境变量指向它）
- **关联**：编译步骤 4.1
