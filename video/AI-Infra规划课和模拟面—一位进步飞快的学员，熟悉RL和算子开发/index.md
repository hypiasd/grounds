---
title: "AI-Infra规划课和模拟面—一位进步飞快的学员，熟悉RL和算子开发"
topic: video
tags: [video]
summary: "视频笔记 — Bilibili：刘yr AI-Infra课程"
created: 2026年
updated: 2026年
video_url: "https://www.bilibili.com/video/BV1icKK6tEoG/"
video_channel: "Bilibili：刘yr AI-Infra课程"
video_duration: "约25分钟"
sources:
  - AI-Infra规划课和模拟面—一位进步飞快的学员，熟悉RL和算子开发.pdf
---

## 视频概述

本视频以一位 AI-Infra 方向学员的真实简历为素材，进行了一次模拟面试与职业规划指导。学员 F 同学背景扎实——985 本科、港中文硕士在读，在国产 GPU 公司和量化机构研究院各有一段高质量的 AI-Infra 相关实习经历，技术方向覆盖算子优化、编译器适配、大模型训练/推理系统、MoE 路由一致性等前沿话题。

视频的核心议题围绕三个问题展开：

1. 当前应该继续沉淀准备秋招，还是冲提前批？
2. 简历如何进一步优化？版本 1 和版本 2 选哪个？
3. 应该往算子方向深耕，还是往全栈方向扩展？

### 本章小结
本视频是一份 AI-Infra 方向学员简历的深度剖析，以模拟面试+规划指导的形式，从简历结构、技术深度、面试策略到职业方向选择，给出了系统性的建议。

## 学员背景与简历结构

### 教育背景

F 同学的教育经历呈现清晰的上升轨迹：

- **本科（2021.09--2025.06）**：末 9（985），获得学业奖学金和特长奖学金（竞赛创新）
- **硕士（2025.09--2027.06 预计）**：港中文 xx 校区

> **[知识]** **AI-Infra 岗位的学历门槛**
> 当前 AI-Infra（尤其大模型系统、GPU 算子优化方向）对学历要求较高，硕博士是主流。985 本科 + 港校硕士的背景在该方向属于有力的基础配置。用人单位更关注的是实习经历中的技术深度和工程交付能力，而非纯论文产出。

### 实习经历概览

F 同学的两段实习分别聚焦于两个不同的技术层次：

- **某国产 GPU 公司（2026.01--2026.04，算子与编译器优化）**：偏底层，涉及 TensorFlow 算子接入、GELU Fusion、Shape Tensor 根因定位与修复
- **某量化机构研究院（2026.04--至今，大模型系统与 HPC）**：偏系统层，涉及 FlashInfer CUDA Graph 修复、MoE Router Replay、OE 异步算子开发

[图：figures/resume_overview.jpg — 见 PDF]
*F 同学简历概览 *

*视频画面时间区间：00:00:00--00:02:30。*

### 本章小结
F 同学的简历结构清晰，教育背景扎实，两段实习经历覆盖了 AI-Infra 的两个核心层次——底层算子/编译器优化与上层大模型系统/训练框架。这种「底层+系统」的组合是非常理想的 AI-Infra 方向配置。

## 实习经历深度解读

### 国产 GPU 公司：算子与编译器优化

这段经历的核心产出可以分为三个层次：

#### GELU Fusion 链路修复与优化

GELU（Gaussian Error Linear Unit）是大模型推理中高频出现的激活函数。在原 TensorFlow on 国产 GPU 的插件实现中，存在大图场景下部分 GELU 节点未被融合的问题，导致额外的 kernel launch 开销。

- **问题定位**：大图中 GELU 的 pattern matching 不完整
- **解决方案**：完成 xDNN GELU 接入与 fusion 链路修复
- **量化结果**：整网 11 个 GELU 全部融合，真实 shape testcase 性能提升约 36.6%

> **[重要]** **GELU 融合的关键收益**
> 算子融合（Operator Fusion）将多个连续的算子合并为单个 kernel，消除中间的显存读写和 kernel launch 开销。在大模型推理中，激活函数（GELU、SiLU 等）的融合是最基础也最高频的优化手段之一。36.6% 的性能提升在这个场景下属于合理的工程收益。

#### Shape Tensor 稳定性修复

整网长跑场景中存在 OOM（Out of Memory）和随机崩溃问题，根因最终收敛到 shape tensor 在特定路径中的设备分配错误。

- **根因**：shape tensor 通过 `StridedSlice<int32> / Pack<int32>` 链路时，错误地进入了 device path 而非 host memory 路径
- **修复**：重构 HostMemory 路径，确保 shape tensor 始终在 CPU 端处理
- **验证结果**：
  - inference 500 轮成功率从约 30% 提升至 1000 轮 100%
  - 通过 4 万/40 万/80 万轮长跑验证，结果均稳定

> **[注意]** **Shape Tensor 的设备分配陷阱**
> Shape tensor 本质上是描述张量形状的元数据，其值应在 CPU 端计算和存储。当编译器或运行时错误地将 shape tensor 的计算图下发到 GPU 时，可能导致：
>
> 1. GPU 显存中存储不必要的元数据
> 2. Shape 推导在 GPU 和 CPU 之间不一致
> 3. 长跑中显存碎片化加剧导致 OOM
>
> 在国产芯片的 TensorFlow 适配中，这种问题尤为常见，因为算子边界和内存管理策略与 CUDA 生态存在差异。

#### 热点算子优化与稳定性修复

持续性的算子级优化工作包括：

- **LogicalOr 标量广播优化**：平均耗时从 21.2$\mu$s 降至 10.7$\mu$s，整网吞吐从 8187.48 提升至 8284.65
- **AddV2 hot path 优化**
- **ResourceApplyAdam graph mode 结果对齐**

### 量化机构研究院：大模型系统与 HPC

第二段实习的技术难度明显上了一个台阶，从单算子优化上升到分布式训练系统的层面。

#### FlashInfer CUDA Graph 稳定性修复

这是一个典型的底层 bug 定位案例，展示了 AI-Infra 工程师需要的调试能力。

- **问题**：H200 上 vLLM TP-2 FULL CUDA Graph 的 rollout 卡死
- **定位过程**：构建两卡最小复现环境，将根因收敛到 `fusedAllReduce + RMSNorm` 的通信轮询逻辑
- **根因**：原实现通过浮点比较识别 Lamport -0.0 sentinel，FTZ（Flush to Zero）会将合法的 FP32 负次正规数误判为负零，导致轮询无法退出，GPU Kernel 不结束，最终触发 rollout timeout
- **修复**：将 sentinel 判断改为 `0x80000000` 位级精确比较
- **验证**：两卡最小复现及模型级 Graph on/off 回归全部通过

[图：figures/flashinfer_fix.jpg — 见 PDF]
*FlashInfer CUDA Graph 修复与 R3 Router Replay 描述 *

*视频画面时间区间：00:02:30--00:05:00。*

> **[重要]** **FTZ 与浮点数 sentinel 的坑**
> FTZ（Flush to Zero）是 GPU 的一种浮点优化模式，会将极小的非正规数（subnormal）直接置为零。当通信库使用 -0.0 作为 sentinel 标记时，FTZ 下的浮点比较会因位级表示差异而误判。位级精确比较（`0x80000000`）是避免此类问题的标准做法——它直接比较 IEEE 754 的符号位，不受 FTZ 影响。

#### R3 Router Replay：MoE 训练路由一致性

这是一个从论文方案到工业实现的完整项目，展示了 F 同学的系统工程能力。

- **背景**：vLLM rollout 侧与 Megatron 训练侧的 MoE 路由可能存在不一致，导致训练-推理 gap
- **技术方案**：
  - 打通 `[token, MoE-layer, top-k]` 维度的 route 采集、传输与回放链路
  - 建立 response-mask 对齐及异常检测
  - 覆盖 18 项 CPU 测试
- **实验结果**：8-H200、Qwen3-30B-A3B BF16 的 20-step 实验中，route mismatch 由 17%--19% 降至 0，Fmax 降低 36%--145%，KL 降低 4%--7%
- **规模化**：最终扩展至 128 卡集群，使用内部大模型完成竞赛单轮 200-step 运行，接入 SwanLab 监控

#### OE 异步算子开发

这是一个深度的算子级优化项目，核心思路是将计算保留在 GPU 端，消除 CPU-GPU 同步的开销。

- **核心做法**：将 recent-token history 与 oe\_input\_ids 构造保留在 GPU，以 Triton fused-hash 消除 GPU 同步及 H$\to$D 回传中的 Bubble
- **TP1 结果**：28/28 case 通过，吞吐较 sync +4.99%，较 async-unfused +1.94%
- **TP>1 安全性**：引入 batch-invariant 安全路径后，TP2/TP4 确定性由 48.8%/75% 提升至 100%，0 mismatch

[图：figures/oe_async_operator.jpg — 见 PDF]
*OE 异步算子开发细节 *

*视频画面时间区间：00:05:00--00:07:00。*

### 项目经历：LLMORT 量化推理

F 同学的个人项目同样具有较高的工程含量：

- **量化 Runtime 与后端适配**：在支持 W4A16 AWQ、W8A8 SmoothQuant 与 FP8 的 PyTorch Extension Runtime 中，完成 FlashAttention-2/4 可配置接入，补齐 GQA 的 KV heads 展开、softcap mask 及 SDPA 回退
- **H200 Kernel 与 Tensor Parallel**：在 2-H200（SM90/CUDA 13.0）环境下完成 AWQ Runtime 迁移
- **Qwen2.5-Coder-32B W4A16 量化验证**：
  - checkpoint 由 61.04 GiB 降至 18.02 GiB（-70.5%）
  - E2E output 吞吐由 2.53 提升至 4.47 tok/s（+76.8%）
  - 运行期峰值显存由 32.02 降至 10.63 GiB/rank（-66.8%）

[图：figures/project_llmort.jpg — 见 PDF]
*LLMORT 量化推理项目详情 *

*视频画面时间区间：00:07:00--00:08:30。*

> **[知识]** **W4A16 量化的工程收益**
> W4A16 表示权重（Weight）用 4-bit 整型存储，激活（Activation）保持 16-bit。在 32B 参数的模型上：
>
> - 权重显存压缩比约 4$\times$（FP16 2B $\to$ INT4 0.5B per 参数）
> - 实际 checkpoint 压缩约 70% 是合理的（还有 KV cache、embedding 等未量化部分）
> - 吞吐提升 76.8% 来自更小的显存占用允许更大的 batch size 和更少的 HBM 带宽压力

### 本章小结
F 同学的实习经历呈现了一个清晰的进阶路径：从单算子优化（GELU Fusion、LogicalOr）到分布式系统稳定性（FlashInfer CUDA Graph），再到训练-推理一致性（MoE Router Replay）和异步算子设计（OE），技术深度逐步提升。这种「底层理解 + 系统视野」的组合是 AI-Infra 方向最受认可的能力模型。

## 简历优化与版本选择

### 版本 1 vs 版本 2

学员准备了两版简历，核心差异在于实习经历的呈现方式：

- **版本 1**：按实习公司分段，每段实习下罗列多个技术产出
- **版本 2**：将同一主题的技术工作跨实习合并，突出技术主线（如 Router Replay、OE 算子）

> **[重要]** **简历版本选择建议**
> 版本 2 更适合 AI-Infra 方向，因为它突出了技术主线而非时间线。面试官更关心「你解决了什么技术问题」而非「你在哪家公司做了什么」。将同一技术主线（如 MoE 训练、算子优化）的不同阶段串联起来，比按公司罗列更有冲击力。

### 简历的具体优化方向

- **量化指标前置**：36.6%、70.5%、76.8% 等数字应放在每条描述的最前面
- **技术栈显式标注**：在每段经历开头标注核心技术栈（TensorFlow/CUDA/Triton/vLLM/Megatron）
- **问题-方案-结果结构**：每条经历按「定位了什么问题$\to$采用了什么方案$\to$取得了什么量化结果」组织
- **避免过度匿名化**：「某国产 GPU 公司」「某量化机构」虽保护隐私，但部分面试官可能因信息不足而降低兴趣

### 本章小结
简历优化的核心逻辑是让面试官在 30 秒内抓住技术主线。量化指标、技术栈显式标注、问题-方案-结果的结构化描述，是 AI-Infra 方向简历的三要素。

## 职业规划：算子深度 vs 全栈广度

### 学员的核心困惑

F 同学面临一个典型的 AI-Infra 职业选择：是继续往算子方向深耕（加深深度），还是在实习期间充分利用资源，多参与大模型训练中不同的部分（往全栈方向走）？

### 两条路径的分析

[图：TikZ 可视化 — 见 PDF]

### 当前阶段的建议

根据视频中的分析，F 同学当前阶段（硕士在读，两段实习）应该：

1. **短期（秋招前）**：以算子深度为主线，用第二段实习的「全栈」经历作为差异化加分项
2. **中期（入职后）**：从算子向系统层扩展，逐步建立训练/推理全栈能力
3. **长期**：成为某个细分方向的 T 型人才——算子优化为纵轴，训练系统/推理引擎为横轴

> **[重要]** **AI-Infra 的 T 型人才模型**
> AI-Infra 方向最稀缺的不是「全栈」也不是「深度专家」，而是有深度主线的全栈能力。具体来说：
>
> - **纵轴（深度）**：算子优化、CUDA Kernel 编写、编译器后端适配
> - **横轴（广度）**：训练框架架构（Megatron/verl）、推理引擎（vLLM/SGLang）、分布式通信（NCCL/DeepEP）
>
> 纵轴决定面试通过率，横轴决定 Offer 等级和长期发展空间。

### 秋招策略

- **提前批**：如果目标公司（如 NVIDIA、华为昇腾、AMD、国产 GPU 厂商）有明确的算子/编译器岗位，可以冲提前批
- **正式秋招**：建议再多积累 2--3 个月的实习产出，将第二段实习的技术栈（R3 Router Replay、OE 算子）打磨到能流畅讲解的程度
- **简历投递优先级**：国产 GPU 厂商 $>$ 大模型独角兽 $>$ 互联网大厂 AI 部门 $>$ 量化机构

> **[注意]** **AI-Infra 秋招的关键时间节点**
> - 6--7 月：NVIDIA、AMD 等外企的提前批
> - 7--8 月：华为昇腾、寒武纪等国产芯片厂商的提前批
> - 8--9 月：字节、阿里、腾讯等互联网大厂的正式批
> - 9--10 月：量化机构的秋招（通常偏晚，且要求更高）
>
> F 同学应重点关注 7--8 月的国产 GPU 厂商提前批，这与其技术栈（TensorFlow 国产芯片适配）最匹配。

### 本章小结
AI-Infra 方向的职业发展不是「深度 vs 广度」的二选一，而是「先深度后广度」的时序策略。F 同学当前应巩固算子优化的纵深能力，同时将第二段实习的大模型系统经验作为「广度展示」，在秋招中占据「底层基础扎实 + 系统视野开阔」的有利位置。

## AI-Infra 学习路径

### 技能栈分层

基于视频中对 F 同学技术栈的分析，AI-Infra 的学习路径可以分为四个层次：

[图：TikZ 可视化 — 见 PDF]

### 各层核心技能

#### 算子层（F 同学当前深度）

- CUDA C++ 编程（内存层级、warp 调度、bank conflict 避免）
- Triton 语言编写 GPU Kernel
- 常见算子的高效实现：GEMM、Attention、LayerNorm、激活函数融合
- 量化推理（W4A16、W8A8、FP8）的 Kernel 适配
- Nsight Systems / Nsight Compute profiling

#### 编译器层

- MLIR / TVM / XLA 的 IR 设计和 Pass 编写
- 图优化（算子融合、内存规划、layout 优化）
- 计算图调度与自动并行化

#### 系统层

- 分布式训练框架（Megatron-LM、DeepSpeed、verl）的架构理解
- Tensor Parallel / Pipeline Parallel / Expert Parallel 的实现原理
- MoE 训练的负载均衡与路由一致性
- CUDA Graph 的 capture 与 replay 机制

#### 应用层

- vLLM / SGLang 等推理引擎的架构与使用
- PagedAttention / FlashInfer 等关键组件的原理
- 训练-推理一致性（RLHF / GRPO 场景下）

> **[知识]** **F 同学当前的技术栈覆盖度**
> center
> tabular{lcc}
>
> **层次** & **覆盖程度** & **代表性经历**

>
> 算子层 & ★★★★★ & GELU Fusion、OE 异步算子、量化 Kernel

> 编译器层 & ★★★☆☆ & TensorFlow on 国产 GPU 插件开发

> 系统层 & ★★★★☆ & FlashInfer CUDA Graph、R3 Router Replay

> 应用层 & ★★★☆☆ & vLLM rollout、Megatron 训练侧适配

>
> tabular
> center
> 整体来看，F 同学在算子层有最深的积累，系统层正在快速建立，编译器层和应用层是后续可以加强的方向。

### 本章小结
AI-Infra 的四层技术栈——算子、编译器、系统、应用——构成了从芯片到模型的完整链路。F 同学当前在算子层积累最深，系统层正在追赶，建议后续重点补齐编译器层（MLIR/Triton）的知识，形成「算子+编译器」的双深度组合。

## 总结与延伸

### 讲者核心观点回顾

视频中讲者通过对 F 同学简历的逐行分析，传达了以下核心观点：

1. **实习产出要有「故事线」**：不要按公司罗列，要按技术主线串联。F 同学的 GELU Fusion $\to$ Shape Tensor 修复 $\to$ LogicalOr 优化形成了一条清晰的「算子优化与稳定性」故事线
2. **量化指标是简历的灵魂**：36.6%、70.5%、100% 等数字比任何描述性语言都有说服力
3. **技术深度决定面试通过率，广度决定 Offer 等级**：F 同学当前最需要的是在算子优化方向建立不可替代的深度
4. **秋招时机取决于目标公司**：国产 GPU 厂商的提前批是最佳窗口，建议优先冲

### 综合提炼

从 F 同学的案例中，可以提炼出 AI-Infra 方向的几条通用规律：

> **[重要]** **AI-Infra 秋招核心竞争力模型**
> AI-Infra 方向的秋招竞争力 = 底层技术深度 × 系统视野广度 × 工程交付能力。其中：
>
> - **底层技术深度**（算子优化/CUDA/编译器）是敲门砖，决定能否过简历筛选
> - **系统视野广度**（训练框架/推理引擎/分布式）是加分项，决定面试评价的高低
> - **工程交付能力**（量化指标/长跑验证/规模化部署）是决定性因素，决定能否拿到 Offer
>
> 三者缺一不可，但权重随目标公司和岗位而变化。国产 GPU 厂商更看重底层深度，大模型独角兽更看重系统广度，量化机构三者都要。

### 面试高频考点预测

基于 F 同学简历中涉及的技术栈，以下是 AI-Infra 模拟面试中可能被追问的高频问题：

- **GELU Fusion**：GELU 的数学定义是什么？为什么 GELU 可以作为单个融合算子？Pattern matching 在什么情况下会失效？
- **Shape Tensor**：什么是 shape tensor？为什么它不能在 GPU 上计算？StridedSlice 和 Pack 在此场景下各起什么作用？
- **FTZ 与 sentinel**：FTZ 是什么？为什么浮点比较 sentinel 在 FTZ 下会出错？还有哪些场景会遇到类似问题？
- **MoE Router Replay**：Router Replay 要解决什么问题？为什么要同时采集 token、layer、topk 三个维度的路由信息？
- **W4A16 量化**：W4A16 和 W8A8 各有什么适用场景？为什么激活通常保持 16-bit 而非 8-bit？

### TikZ 可视化：AI-Infra 全栈技能地图

[图：TikZ 可视化 — 见 PDF]

### 开放问题与后续方向

- **国产芯片适配的长期前景**：随着国产 GPU（昇腾、寒武纪、壁仞等）的生态逐步成熟，TensorFlow/PyTorch on 国产 GPU 的适配需求会持续增长，F 同学的这段经历在未来 2--3 年内具有较高的市场价值
- **量化推理的工业落地**：W4A16 量化虽然压缩率可观，但在实际业务中面临精度损失的权衡。如何系统性地评估量化对模型输出质量的影响，是量化推理工程师必须掌握的能力
- **MoE 训练的路由一致性**：R3 Router Replay 解决了训练-推理的显式路由对齐，但隐式的分布偏移（distribution shift）问题仍需持续关注
- **算子优化与 AI 编译器自动化的博弈**：随着 Triton、MLIR 等编译器技术的发展，手写 CUDA Kernel 的需求是否会减少？算子优化工程师需要如何适应这一趋势？

### 拓展阅读

- FlashInfer 官方文档：[https://docs.flashinfer.ai/](https://docs.flashinfer.ai/) — 了解 CUDA Graph 在推理引擎中的应用
- vLLM 源码仓库：[https://github.com/vllm-project/vllm](https://github.com/vllm-project/vllm) — 深入理解 PagedAttention 与推理引擎架构
- MoE Router Replay 相关工作：对应论文讨论了 rollout 侧与训练侧的路由一致性问题
- CUDA C++ Programming Guide：[https://docs.nvidia.com/cuda/cuda-c-programming-guide/](https://docs.nvidia.com/cuda/cuda-c-programming-guide/) — 算子优化的基础知识来源
