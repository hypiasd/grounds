---
title: Qwen2 模型推理
topic: llaisys
tags: [llm-inference, cpp, qwen2, kv-cache, autoregressive]
summary: "Qwen2 完整推理实现：C++ 后端做 forward（Embedding→N×(RMSNorm→Attn→FFN)→LMHead→Argmax），KV Cache 缓存历史 K/V 避免重复计算，Python 前端加载 safetensors 权重并驱动 autoregressive generate 循环。"
created: 2026-07-20
updated: 2026-07-20
sources:
  - ../../raw/wiki/llaisys/src/llaisys/qwen2_model.cc
  - ../../raw/wiki/llaisys/python/llaisys/models/qwen2.py
---

## TL;DR

模型推理分两阶段：**prefill**（一次处理整个 prompt，填充 KV Cache）和 **decode**（每次只处理 1 个新 token，复用 KV Cache）。C++ 后端实现完整 forward + KV Cache 管理，Python 前端负责加载权重和驱动生成循环。核心：每层 Attention 把新 K/V concat 到 cache 上，下次 decode 时 Q 只需和全部历史 K 做 attention。

## 设计决策

**为什么需要 KV Cache？**

Autoregressive 生成时，每生成一个新 token 都要对全部历史做 attention。如果每次都重新算所有 token 的 K/V，复杂度是 O(n²)（n 是已生成长度）。KV Cache 把历史的 K/V 存下来，新 token 只需算自己的 Q/K/V（O(n)），然后和 cache 做 attention。代价是显存占用随序列长度线性增长。

**为什么 prefill 和 decode 用同一段代码？**

两者的计算逻辑完全相同（同一个 forward），区别只是 `seqlen` 不同：prefill 时 seqlen = prompt_len（一次处理多个 token），decode 时 seqlen = 1（只处理一个新 token）。KV Cache 的 concat 逻辑自动处理两种情况。这也是 vLLM V1 “没有 prefill phase 也没有 decode phase”的设计思路。

**为什么用 argmax 而不是 sampling？**

测试要求“和 PyTorch 生成完全一致的 token 序列”。只有 argmax（greedy，top_k=1）是确定性的——sampling 有随机性，无法保证一致。生产环境会用 top-p/top-k sampling，但测试时用 argmax 验证正确性。

## 核心概念

### Forward 数据流（每步 tensor shape）

```
token_ids [seqlen]
    ↓ embedding
hidden [seqlen, hs=1536]
    ↓ × N layers (28):
    ├── rms_norm → [seqlen, hs]
    ├── linear(Q) → [seqlen, nh*dh=16*96=1536]  → view [seqlen, 16, 96]
    ├── linear(K) → [seqlen, nkvh*dh=2*96=192]  → view [seqlen, 2, 96]
    ├── linear(V) → [seqlen, nkvh*dh=192]       → view [seqlen, 2, 96]
    ├── rope(Q), rope(K)
    ├── KV Cache concat → K [total_len, 2, 96], V [total_len, 2, 96]
    ├── self_attention → [seqlen, 16, 96] → view [seqlen, 1536]
    ├── linear(O) → [seqlen, hs]
    ├── residual: hidden += O
    ├── rms_norm → [seqlen, hs]
    ├── linear(gate) → [seqlen, di=8960]
    ├── linear(up)   → [seqlen, di=8960]
    ├── swiglu → [seqlen, di]
    ├── linear(down) → [seqlen, hs]
    └── residual: hidden += down
    ↓
rms_norm → [seqlen, hs]
linear(lm_head) → [seqlen, voc=151936]
argmax(last_token) → next_token
```

### KV Cache 实现

```cpp
// 每层维护一个 KV cache，存所有历史 token 的 K/V
std::vector<tensor_t> kv_cache_k;  // [layer] → [total_len, nkvhead, dh]
std::vector<tensor_t> kv_cache_v;
size_t cache_len;  // 已缓存的 token 数

// 每次 forward：新 K/V concat 到 cache
tensor_t full_k = concat_kv(cache_k[layer], new_k, cache_len, seqlen, ...);
cache_k[layer] = full_k;  // 更新 cache
cache_len += seqlen;      // prefill 后 cache_len = prompt_len
```

### C API

```cpp
// include/llaisys/models/qwen2.h
struct LlaisysQwen2Meta {
    llaisysDataType_t dtype;
    size_t nlayer, hs, nh, nkvh, dh, di, maxseq, voc;
    float epsilon, theta;
    int64_t end_token;
};

__export LlaisysQwen2Model *llaisysQwen2ModelCreate(const LlaisysQwen2Meta*, ...);
__export void llaisysQwen2ModelDestroy(LlaisysQwen2Model*);
__export LlaisysQwen2Weights *llaisysQwen2ModelWeights(LlaisysQwen2Model*);
__export int64_t llaisysQwen2ModelInfer(LlaisysQwen2Model*, int64_t *token_ids, size_t ntoken);
```

### Python 前端：权重加载

```python
# safetensors 权重名 → 模型结构体字段的映射
mapping = {
    "model.embed_tokens.weight": "in_embed",
    "lm_head.weight": "out_embed",
    "model.norm.weight": "out_norm_w",
    "model.layers.{i}.input_layernorm.weight": "attn_norm_w[i]",
    "model.layers.{i}.self_attn.q_proj.weight": "attn_q_w[i]",
    "model.layers.{i}.self_attn.q_proj.bias": "attn_q_b[i]",
    "model.layers.{i}.self_attn.k_proj.weight": "attn_k_w[i]",
    "model.layers.{i}.self_attn.v_proj.weight": "attn_v_w[i]",
    "model.layers.{i}.self_attn.o_proj.weight": "attn_o_w[i]",
    "model.layers.{i}.post_attention_layernorm.weight": "mlp_norm_w[i]",
    "model.layers.{i}.mlp.gate_proj.weight": "mlp_gate_w[i]",
    "model.layers.{i}.mlp.up_proj.weight": "mlp_up_w[i]",
    "model.layers.{i}.mlp.down_proj.weight": "mlp_down_w[i]",
}
```

### Python 前端：generate 循环

```python
def generate(self, inputs, max_new_tokens=128, ...):
    output_tokens = list(inputs)
    # Prefill: 一次处理整个 prompt
    token_arr = (c_int64 * len(output_tokens))(*output_tokens)
    next_token = LIB_LLAISYS.llaisysQwen2ModelInfer(self._model, token_arr, len(output_tokens))
    output_tokens.append(next_token)
    # Decode: 逐 token 生成
    for _ in range(max_new_tokens - 1):
        token_arr = (c_int64 * 1)(next_token)
        next_token = LIB_LLAISYS.llaisysQwen2ModelInfer(self._model, token_arr, 1)
        if next_token == self._end_token: break
        output_tokens.append(next_token)
    return output_tokens
```

## 直觉 / 类比

KV Cache 就像考试时把每道做过的题的答案留着——下次遇到相关题不用重新推导，直接查。Prefill 是"一次性把阅读材料全读完并做笔记"，Decode 是"每次只看一个新问题，翻笔记回答"。

## 常见误区

- **“每个 decode step 都要重新算所有 token 的 K/V”** → 不需要，KV Cache 缓存了历史的 K/V，新 token 只需算自己的 Q/K/V 然后 concat。这是推理引擎最核心的优化。
- **“prefill 和 decode 用不同的 forward 代码”** → 同一段代码，区别只是 seqlen 不同（prefill seqlen=prompt_len，decode seqlen=1）。这也是为什么 vLLM V1 说“没有 prefill phase 也没有 decode phase”。
- **“KV Cache 只是‘缓存’，不影响正确性”** → 影响。如果 KV Cache 的 concat 顺序错了（比如新 K 放在历史 K 前面），causal mask 的位置就会错，生成结果就乱了。cache 的顺序必须和 token 的实际位置一致。

## 关联

- [算子实现](operators.md) — forward 中调用的所有算子
- [Tensor 实现](tensor.md) — KV Cache 的 concat 用 Tensor 的 view/slice
- [vLLM V1 架构](../vllm/vllm-v1-architecture.md) — vLLM 的 PagedAttention 是 KV Cache 的产品级优化
- 源码：[qwen2_model.cc](../../raw/wiki/llaisys/src/llaisys/qwen2_model.cc)、[qwen2.py](../../raw/wiki/llaisys/python/llaisys/models/qwen2.py)
