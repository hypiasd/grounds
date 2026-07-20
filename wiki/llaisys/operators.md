---
title: 算子实现
topic: llaisys
tags: [llm-inference, cpp, operators, cpu]
summary: "7 个 LLM 核心算子的 CPU 实现：argmax/embedding/linear/rms_norm/rope/self_attention/swiglu。统一模式：op.cpp 做设备分发，cpu/ 下模板化实现支持 FP32/FP16/BF16。self_attention 支持 GQA 和 causal mask。"
created: 2026-07-20
updated: 2026-07-20
sources:
  - ../../raw/wiki/llaisys/src/ops/
---

## TL;DR

每个算子遵循统一模式：`op.cpp` 做前置检查 + 设备分发（switch deviceType），`cpu/<name>_cpu.cpp` 用 C++ 模板实现 FP32/FP16/BF16 三种精度。半精度计算统一先 cast 到 float32 做运算再 cast 回去。self_attention 支持 GQA（nhead ≠ nkvhead 时按 group 映射）和 causal mask。

## 设计决策

**为什么半精度要先 cast 到 float32 再算？**

FP16 只有 ~3 位有效十进制精度，BF16 只有 ~2 位。如果直接在半精度下做累加（比如 linear 的 4096 维点积），舍入误差会累积到不可接受。先 cast 到 float32（~7 位精度）做中间计算，最后再 cast 回去，是精度和性能的标准平衡点。PyTorch 内部也是这么做的。

**为什么用模板而不是运行时多态？**

算子的内层循环是性能热点。模板在编译期展开，编译器可以对每种 dtype 独立优化（向量化、循环展开）。运行时多态（虚函数）会在每次调用时查 vtable，内层循环里这个开销不可忽略。

**为什么 self_attention 的 causal mask 用 -infinity 而不是 0？**

softmax 中 $e^{-\infty} = 0$，所以 -infinity 位置的注意力权重精确为 0。如果用 0 作为 mask 值，$e^0 = 1$，这个位置还会分走一部分注意力权重——结果就错了。

## 统一模式

```cpp
// op.cpp 模板（以 add 为参考）
void op_name(tensor_t out, tensor_t in, ...) {
    CHECK_SAME_DEVICE(out, in, ...);
    ASSERT(out->isContiguous() && in->isContiguous(), "...");
    switch (out->deviceType()) {
    case LLAISYS_DEVICE_CPU:
        return cpu::op_name(out->data(), in->data(), ..., out->dtype(), ...);
    default: EXCEPTION_UNSUPPORTED_DEVICE;
    }
}

// cpu/op_cpu.cpp 模板
template <typename T>
void op_(T *out, const T *in, ...) {
    for (...) {
        float v = utils::cast<float>(in[i]);  // 半精度→float32
        // 计算
        out[i] = utils::cast<T>(result);       // float32→半精度
    }
}
void op(std::byte *out, ..., llaisysDataType_t type, ...) {
    switch (type) {
    case LLAISYS_DTYPE_F32: return op_(reinterpret_cast<float*>(out), ...);
    case LLAISYS_DTYPE_BF16: return op_(reinterpret_cast<bf16_t*>(out), ...);
    case LLAISYS_DTYPE_F16: return op_(reinterpret_cast<fp16_t*>(out), ...);
    default: EXCEPTION_UNSUPPORTED_DATATYPE(type);
    }
}
```

## argmax

```cpp
template <typename T>
void argmax_(int64_t *max_idx, std::byte *max_val_raw, const T *vals, size_t numel) {
    float best = -std::numeric_limits<float>::infinity();
    size_t best_idx = 0;
    for (size_t i = 0; i < numel; i++) {
        float v = utils::cast<float>(vals[i]);
        if (v > best) { best = v; best_idx = i; }
    }
    *max_idx = static_cast<int64_t>(best_idx);
    *reinterpret_cast<T*>(max_val_raw) = vals[best_idx];
}
```

## embedding

```cpp
// out[i] = weight[index[i]]（按行拷贝）
void embedding(std::byte *out, const int64_t *index, const std::byte *weight,
               llaisysDataType_t type, size_t seqlen, size_t embed_dim) {
    size_t row_bytes = embed_dim * utils::dsize(type);
    for (size_t i = 0; i < seqlen; i++) {
        std::memcpy(out + i * row_bytes,
                    weight + index[i] * (int64_t)row_bytes, row_bytes);
    }
}
```

## linear

$$Y = XW^T + b$$

```cpp
template <typename T>
void linear_(T *out, const T *in, const T *weight, const T *bias,
             size_t M, size_t N, size_t K, bool has_bias) {
    for (size_t i = 0; i < M; i++)
        for (size_t j = 0; j < N; j++) {
            float sum = 0.0f;
            for (size_t k = 0; k < K; k++)
                sum += cast<float>(in[i*K+k]) * cast<float>(weight[j*K+k]);
            if (has_bias) sum += cast<float>(bias[j]);
            out[i*N+j] = cast<T>(sum);
        }
}
```

## rms_norm

$$Y_i = \frac{W_i \times X_i}{\sqrt{\frac{1}{d}\sum_{j=1}^d X_j^2 + \epsilon}}$$

```cpp
template <typename T>
void rms_norm_(T *out, const T *in, const T *weight, size_t rows, size_t d, float eps) {
    for (size_t row = 0; row < rows; row++) {
        float sum_sq = 0.0f;
        for (size_t j = 0; j < d; j++) {
            float v = cast<float>(in[row*d+j]);
            // 匹配 PyTorch：先在 native dtype 平方再累加
            T sq_native = cast<T>(v * v);
            sum_sq += cast<float>(sq_native);
        }
        float rms_inv = 1.0f / std::sqrt(sum_sq / (float)d + eps);
        for (size_t j = 0; j < d; j++)
            out[row*d+j] = cast<T>(cast<float>(weight[j]) * cast<float>(in[row*d+j]) * rms_inv);
    }
}
```

## rope（旋转位置编码）

$$\phi_{i,j} = p_i / \theta^{2j/d}$$
$$a'_{i,j} = a_{i,j}\cos\phi - b_{i,j}\sin\phi, \quad b'_{i,j} = b_{i,j}\cos\phi + a_{i,j}\sin\phi$$

```cpp
template <typename T>
void rope_(T *out, const T *in, const int64_t *pos_ids,
           size_t seqlen, size_t nhead, size_t d, float theta) {
    size_t half_d = d / 2;
    for (size_t i = 0; i < seqlen; i++) {
        float pos = (float)pos_ids[i];
        for (size_t h = 0; h < nhead; h++) {
            size_t base = (i * nhead + h) * d;
            for (size_t j = 0; j < half_d; j++) {
                float freq = pos / std::pow(theta, 2.0f * j / (float)d);
                float cos_v = std::cos(freq), sin_v = std::sin(freq);
                float a = cast<float>(in[base + j]);
                float b = cast<float>(in[base + half_d + j]);
                out[base + j]        = cast<T>(a * cos_v - b * sin_v);
                out[base + half_d+j] = cast<T>(b * cos_v + a * sin_v);
            }
        }
    }
}
```

## self_attention（含 GQA + causal mask）

$$A = QK^\top \cdot \text{scale}, \quad Y = \text{causal\_softmax}(A) \cdot V$$

```cpp
template <typename T>
void self_attention_(T *attn_val, const T *q, const T *k, const T *v,
                     size_t seqlen, size_t nhead, size_t nkvhead,
                     size_t d, size_t dv, size_t total_len, float scale) {
    size_t group_size = nhead / nkvhead;  // GQA
    size_t q_start_pos = total_len - seqlen;
    std::vector<float> scores(total_len);

    for (size_t i = 0; i < seqlen; i++) {
        size_t q_pos = q_start_pos + i;
        for (size_t h = 0; h < nhead; h++) {
            size_t kvh = h / group_size;  // 对应的 KV head
            // Q·K dot product
            for (size_t j = 0; j <= q_pos; j++) {
                float dot = 0;
                for (size_t dk = 0; dk < d; dk++)
                    dot += cast<float>(q[(i*nhead+h)*d+dk])
                         * cast<float>(k[(j*nkvhead+kvh)*d+dk]);
                scores[j] = dot * scale;
            }
            for (size_t j = q_pos+1; j < total_len; j++)
                scores[j] = -INFINITY;  // causal mask
            // softmax
            float mx = *std::max_element(scores.begin(), scores.begin()+total_len);
            float sum = 0;
            for (size_t j = 0; j < total_len; j++) { scores[j] = expf(scores[j]-mx); sum += scores[j]; }
            for (size_t j = 0; j < total_len; j++) scores[j] /= sum;
            // weighted sum of V
            for (size_t dv_i = 0; dv_i < dv; dv_i++) {
                float acc = 0;
                for (size_t j = 0; j < total_len; j++)
                    acc += scores[j] * cast<float>(v[(j*nkvhead+kvh)*dv+dv_i]);
                attn_val[(i*nhead+h)*dv+dv_i] = cast<T>(acc);
            }
        }
    }
}
```

## swiglu（SwiGLU 激活）

$$\text{out}_i = \text{up}_i \cdot \frac{\text{gate}_i}{1 + e^{-\text{gate}_i}} = \text{up}_i \cdot \text{SiLU}(\text{gate}_i)$$

```cpp
template <typename T>
void swiglu_(T *out, const T *gate, const T *up, size_t numel) {
    for (size_t i = 0; i < numel; i++) {
        float g = cast<float>(gate[i]), u = cast<float>(up[i]);
        out[i] = cast<T>(u * g / (1.0f + expf(-g)));
    }
}
```

## 常见误区

- **“半精度直接算就行”** → FP16/BF16 必须先 cast 到 float32 做中间计算，否则精度损失会在累加中放大。尤其是 linear（4096 维点积）和 rms_norm（求平方和），累加次数多，误差累积显著。
- **“self_attention 的 nhead 一定等于 nkvhead”** → GQA（Grouped Query Attention）中 nkvhead < nhead，多个 Q head 共享一组 KV。Qwen2-1.5B 是 16 个 Q head 共享 2 个 KV head（group_size=8）。
- **“RoPE 是加在 embedding 上的”** → 不是，RoPE 加在 Q/K 上（每层都加），不是加在输入 embedding 上。它编码的是相对位置，不是绝对位置。
- **“rms_norm 的精度无关紧要”** → 实际上 rms_norm 的平方和累加顺序会影响 fp16 结果。PyTorch 先在 native dtype 平方再累加，而不是先 cast 到 float32 再平方——这个顺序差异在 4096 维时能超过 1e-3 容差。

## 关联

- [Tensor 实现](tensor.md) — 算子要求输入连续，非连续需先 contiguous()
- [Qwen2 模型推理](qwen2-model.md) — 模型 forward 按顺序调用这些算子
- [框架分层与设备抽象](framework-architecture.md) — 算子分发模式的设计来源
- 源码：[src/ops/](../../raw/wiki/llaisys/src/ops/)
