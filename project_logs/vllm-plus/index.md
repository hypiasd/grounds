---
title: vllm-plus 项目全景
tags: [project, vllm-plus]
created: 2026-07-21
updated: 2026-07-21
---
# vllm-plus 项目全景

> 压成认知版的项目手册：目标、技术栈、命令、结构、现状、待办、决策指针、外部仓库。
> 详细决策看 [decisions.md](decisions.md)。

## 1. 目标（一图读懂在做什么）

在 **nano-vllm**（一个 2000 行的教学版 vLLM，已内建连续批处理 / 分页 KV / 投机性已部分）之上，做**推理系统级优化实验台**：把工业界 vLLM 的关键机制（KV 量化、swap 抢占、watermark、投机解码、权重量化）逐个**实现 + 实测**，用数据回答"这些优化在我这张卡上到底有没有用、值不值得上"。

- 一句话：不是要再造一个 vLLM，而是**用最小代码把优化手段跑通并量化收益**。

## 2. 技术栈

| 项 | 值 |
|---|---|
| 语言 | Python 3 + PyTorch（CUDA） |
| 基座 | nano-vllm（https://github.com/GeeeekExplorer/nano-vllm） |
| 模型 | Qwen3（0.6B/4B，GPTQModel 加载量化权重） |
| 硬件 | RTX 5090 / sm_120（FP8 原生，FP16/BF16/INT8 走模拟路径） |
| 关键手段 | 投机解码 / KV INT8 量化 / KV watermark / CPU swap / 权重量化(W8A8) |

## 3. 命令（怎么跑）

```bash
# 进入项目（已软链）
cd project/vllm-plus        # 软链到本机外部目录（真实绝对路径属本机状态，不写死以避免泄露本机路径）

# 基础推理
python example.py           # 单/小批量对话

# 性能与策略实验
python bench.py             # 吞吐 / 显存 / 各策略开关的实测脚本
```

> 注：pyproject 未定义 scripts，运行入口为 `example.py` 与 `bench.py`；具体实验开关在各脚本内配置。

## 4. 结构（核心目录与职责）

| 路径 | 职责 |
|---|---|
| `nanovllm/llm.py` | 对外入口 LLM 类（generate 接口） |
| `nanovllm/engine/` | 引擎核心：`Engine`、`EngineCore`、`Scheduler`、`BlockManager`、`ModelRunner`、`SpecDecode`、`ModelRunner_*` 多实例 |
| `nanovllm/layers/` | 算子层：attention / linear / sampler / rotary / layernorm / embed_head / activation |
| `nanovllm/models/qwen3.py` | Qwen3 模型定义 |
| `nanovllm/utils/` | context（KV 块管理）、loader（权重加载，含 GPTQModel） |
| `nanovllm/config.py` | 全局配置（含量化/投机/swap 开关） |
| `bench.py` | 性能/策略实验台 |
| `experiments_plan.md` | 12 项实验计划与待验证假设 |
| `experiment_results.md` | 已完成的 12 组实验结论汇总 |
| `interview_prep.md` / `interview_qa.md` | 推理系统面经沉淀 |

## 5. 现状（目前做到哪）

- **已落地并实测**：投机解码（Ngram/Prompt Lookup + 动态树 + 自适应 K，CUDA graph verify 保无损）、INT8 KV 量化、KV watermark、CPU swap、W8A8 权重量化。
- **已用数据证伪/收敛的判断**：
  - KV INT8 量化 → 吞吐中性、显存 42%→28%，保留为省显存手段。
  - 权重量化(W8A8) → 本卡无吞吐收益，已回退 BF16。
  - 投机解码 → 高并发/低算占下有效，单请求无效；禁用 vLLM 贪心回退近似以保无损。
- **计划未做**：chunked prefill、prefix cache、disaggregation、radix cache、spec decode CPU 开销优化。

## 6. 待办（接下来）

- [ ] 跑通 experiments_plan.md 中**未做项**（chunked prefill / prefix cache / disagg 等）并补实验结论。
- [ ] 把 bench.py 的实验开关做成显式 CLI 参数，避免改代码切换策略。
- [ ] 将已收敛的优化（投机/量化）整理成可独立启停的"配置矩阵"文档。

## 7. 决策指针

- 所有"该不该上这个优化"的判断集中在 [decisions.md](decisions.md)，每条带实测依据。

## 8. 外部仓库

- 远程：`git@github.com:hypiasd/vllm-plus.git`
- 本地软链：`project/vllm-plus`（→ 本机外部目录；真实绝对路径不写进笔记，跨机器以远程仓库为准）
- 上游基座：https://github.com/GeeeekExplorer/nano-vllm
