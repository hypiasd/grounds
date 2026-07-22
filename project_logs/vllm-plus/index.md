---
title: vllm-plus 项目入口
tags: [project, vllm-plus]
created: 2026-07-22
updated: 2026-07-22
publish: true
---

# vllm-plus

> 基于 [nano-vllm](https://github.com/GeeeekExplorer/nano-vllm)（从零实现的极简 vLLM）做的一系列「投机解码 / 量化 / 调度」性能与正确性实验，目标是攒出简历级、可复看的深度数据。

## 一句话目标
把 nano-vllm 当试验台，逐项验证「投机解码、KV 量化、权重量化、抢占/swap、调度 watermark」等推理优化手段在 RTX 4090D（Ada，无 FP8）上的真实收益边界，并把每个决策/坑/结论白盒化为可复看记录。

## 技术栈
- Python ≥3.10，PyTorch 2.9 + CUDA 13，Triton ≥3，flash-attn 2.8，transformers ≥4.51
- 模型：Qwen3-4B（target, bf16）+ Qwen3-0.6B（draft, bf16）
- GPU：NVIDIA RTX 4090 D，24GB；固定 KV 池语义

## 现状（一行）
12 项实验已跑完并记录在代码仓 `experiment_results.md`；量化路线在本卡上吞吐收益封顶于 INT8 KV 的 +4~13%，真正的 2× 杠杆是投机解码（已 2×+）；下阶段可选 FP8/W8A8（需 Hopper/Blackwell）或转向 kernel 融合 / 更优调度。

## 外部仓库
- 远程：`git@github.com:hypiasd/vllm-plus.git`（独立 git，父仓库 `.gitignore` 忽略其内容，不进 grounds）
- 本机软链：`project/vllm-plus`（指向真实仓库，工作目录锁死于此）
- 详细实验记录（机器本地产物，不进 grounds，跨机需重跑或 clone）：`project/vllm-plus/experiment_results.md`、`experiment_plan` 并列 `experiments_plan.md`、`interview_questions/answers.md`

## 入口
- 主控时间线 / 决策 / 踩坑 / 能力账本 → [runbook.md](./runbook.md)

## 上手命令（来自代码仓）
```bash
cd project/vllm-plus
pip install -e .                      # 安装 nano-vllm（含 torch/triton/flash-attn 依赖）
python bench.py                       # 默认小规模吞吐 bench（baseline + spec K=2）
EAGER=1 python bench.py              # 强制 eager（对照 CUDA graph 路径）
MODE=continuous NUM_KVBLOCKS=80 python bench.py   # 持续到达 + 钉死 KV 池（观测 watermark/swap 收益）
DTYPE=int8 python bench.py           # INT8 KV cache 量化
WQUANT=int8 python bench.py          # INT8 权重量化（W8A8）
USE_LOOKAHEAD=1 python bench.py      # training-free lookahead 投机解码
python example.py                     # chat 演示（rejection sampling, temp=0.6）
```
