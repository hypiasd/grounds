---
title: Tensor 实现
topic: llaisys
tags: [llm-inference, cpp, tensor, zero-copy]
summary: "Tensor = storage（共享内存 shared_ptr）+ offset（字节偏移）+ meta（shape/strides/dtype）。view/permute/slice 全部零拷贝只改 meta——形状是幻觉，内存是真相。isContiguous 从最后一维向前验证 stride 是否等于 shape 累积。"
created: 2026-07-20
updated: 2026-07-20
sources:
  - ../../raw/wiki/llaisys/src/tensor/tensor.cpp
---

## TL;DR

Tensor 不拥有数据——它通过 `storage`（shared_ptr 指向一块设备内存）+ `offset`（字节偏移）+ `meta`（shape/strides/dtype）来“描述”数据。view/permute/slice 全部只修改 meta 或 offset，不搬移数据。这就是“形状是幻觉，内存是真相”——同一个 storage 可以被多个 Tensor 以不同形状/步长描述。

## 设计决策：为什么这样设计

**为什么 Tensor 不直接拥有数据（像 std::vector 那样）？**

因为 LLM 推理中大量操作是“换个角度看同一块数据”：
- Q/K/V 投影后需要 reshape（[seqlen, nh*dh] → [seqlen, nh, dh]）
- Attention 输出需要 reshape 回去
- KV Cache 需要 slice

如果每次 reshape 都拷贝数据，1.5B 模型每层要拷贝几十 MB——完全不可接受。零拷贝的关键就是把“数据”和“描述”分离：storage 不动，只改 meta。

**为什么 offset 是字节而不是元素数？**

因为 slice 可能发生在非第一维。比如 shape [4, 8] slice(dim=0, start=2, end=4)，新 Tensor 的起始地址是 `base + 2 * stride[0] * elementSize()`。用字节偏移可以直接做指针算术，不用每次访问都重新计算。

**为什么 view 要求连续？**

view 是“重新解读 strides”——它假设内存中元素是紧密排列的，然后给一个新的 shape+strides 解读。如果 Tensor 不连续（比如 permute 过），元素在内存中的顺序和新 shape 假设的顺序不一致，强行 view 会读到错误数据。这时应该用 reshape（先 contiguous 再 view）。

## 核心概念

### 数据结构

```cpp
struct TensorMeta {
    llaisysDataType_t dtype;
    std::vector<size_t> shape;
    std::vector<ptrdiff_t> strides;  // 单位：元素数（非字节）
};

class Tensor {
    TensorMeta _meta;
    core::storage_t _storage;  // shared_ptr<Storage>，可被多个 Tensor 共享
    size_t _offset;            // 字节偏移
};
```

### 完整实现

**load：把主机内存的数据拷到 Tensor 所在的设备上。** 如果 Tensor 在 CPU 上，这就是一个 memcpy；如果在 GPU 上，走 cudaMemcpy。关键是先 `setDevice` 切换到目标设备的上下文，再调 Runtime API 的 `memcpy_sync`。

```cpp
void Tensor::load(const void *src_) {
    size_t total_bytes = numel() * elementSize();
    core::context().setDevice(this->deviceType(), this->deviceId());
    core::context().runtime().api()->memcpy_sync(
        this->data(), src_, total_bytes, LLAISYS_MEMCPY_H2D);
}
```

**isContiguous：从最后一维向前检查，每一维的 stride 是否等于“它后面所有维的 shape 之积”。** 比如 shape [2,3,5]，连续时 strides 应该是 [15,5,1]——stride[2]=1，stride[1]=5=shape[2]，stride[0]=15=shape[1]*shape[2]。任何一维不满足就不连续。

```cpp
bool Tensor::isContiguous() const {
    size_t ndim_ = ndim();
    if (ndim_ == 0) return true;
    ptrdiff_t expected_stride = 1;
    for (size_t i = ndim_; i > 0; i--) {
        if (_meta.strides[i - 1] != expected_stride) return false;
        expected_stride *= static_cast<ptrdiff_t>(_meta.shape[i - 1]);
    }
    return true;
}
```

**permute：按 order 重排 shape 和 strides。** 比如 permute({2,0,1}) 把原来的 dim2 放到新的 dim0。注意只是“换标注”，storage 和 offset 不动。返回的新 Tensor 和原 Tensor 共享同一块内存。

```cpp
tensor_t Tensor::permute(const std::vector<size_t> &order) const {
    size_t ndim_ = ndim();
    TensorMeta new_meta;
    new_meta.dtype = _meta.dtype;
    new_meta.shape.resize(ndim_);
    new_meta.strides.resize(ndim_);
    for (size_t i = 0; i < ndim_; i++) {
        new_meta.shape[i] = _meta.shape[order[i]];    // 新 dim_i = 旧 dim_order[i]
        new_meta.strides[i] = _meta.strides[order[i]];
    }
    return std::shared_ptr<Tensor>(new Tensor(new_meta, _storage, _offset));
}
```

**view：先确认连续，然后给新 shape 算出对应的连续 strides。** 核心逻辑是从后往前累乘：stride[ndim-1]=1，stride[i]=stride[i+1]*shape[i+1]。如果 numel 不匹配则报错——不能把 12 个元素 view 成 (5,3)。

```cpp
tensor_t Tensor::view(const std::vector<size_t> &shape) const {
    ASSERT(isContiguous(), "view: tensor must be contiguous");
    size_t new_numel = std::accumulate(shape.begin(), shape.end(),
                                       size_t(1), std::multiplies<size_t>());
    CHECK_ARGUMENT(new_numel == numel(), "view: incompatible shape");
    size_t ndim_ = shape.size();
    std::vector<ptrdiff_t> new_strides(ndim_);
    ptrdiff_t stride = 1;
    for (size_t i = ndim_; i > 0; i--) {
        new_strides[i - 1] = stride;
        stride *= static_cast<ptrdiff_t>(shape[i - 1]);
    }
    TensorMeta new_meta{_meta.dtype, shape, new_strides};
    return std::shared_ptr<Tensor>(new Tensor(new_meta, _storage, _offset));
}
```

**slice：沿 dim 切出 [start, end)。** shape 只改 dim 维的大小，strides 不变。关键是 offset 的移动：新起始地址 = 原 offset + start × stride[dim] × elementSize。比如 shape [4,8] slice(dim=0, start=2, end=4)，新 Tensor 从第 2 行开始，offset 跳过 2×8=16 个元素。

```cpp
tensor_t Tensor::slice(size_t dim, size_t start, size_t end) const {
    TensorMeta new_meta;
    new_meta.dtype = _meta.dtype;
    new_meta.shape = _meta.shape;
    new_meta.strides = _meta.strides;
    new_meta.shape[dim] = end - start;
    size_t new_offset = _offset +
        static_cast<size_t>(start * _meta.strides[dim]) * elementSize();
    return std::shared_ptr<Tensor>(new Tensor(new_meta, _storage, new_offset));
}
```

**contiguous：如果已经不连续，就创建新 Tensor 并逐元素拷贝。** 用多维索引遍历每个逻辑位置，通过 strides 算出源地址，然后 memcpy 到目标的连续位置。这是唯一需要搬移数据的操作。

```cpp
tensor_t Tensor::contiguous() const {
    if (isContiguous())
        return std::shared_ptr<Tensor>(new Tensor(_meta, _storage, _offset));
    auto out = Tensor::create(_meta.shape, _meta.dtype, deviceType(), deviceId());
    size_t elem_size = elementSize();
    size_t total = numel(), ndim_ = ndim();
    std::vector<size_t> idx(ndim_, 0);  // 多维索引
    std::byte *dst_ptr = out->data();
    for (size_t i = 0; i < total; i++) {
        // 用 strides 算出源元素在 storage 中的偏移
        ptrdiff_t src_elem_offset = 0;
        for (size_t d = 0; d < ndim_; d++)
            src_elem_offset += static_cast<ptrdiff_t>(idx[d]) * _meta.strides[d];
        std::memcpy(dst_ptr + i * elem_size,
                    this->data() + src_elem_offset * (ptrdiff_t)elem_size, elem_size);
        // 多维索引 +1（行主序进位）
        for (size_t d = ndim_; d > 0; d--) {
            idx[d - 1]++;
            if (idx[d - 1] < _meta.shape[d - 1]) break;
            idx[d - 1] = 0;
        }
    }
    return out;
}
```

**to：跨设备迁移。** 先判断源/目标是否是 CPU，确定 memcpy 方向（H2H/H2D/D2H/D2D），然后在目标设备上分配新 Tensor，拷贝数据。

```cpp
tensor_t Tensor::to(llaisysDeviceType_t device_type, int device) const {
    if (this->deviceType() == device_type && this->deviceId() == device)
        return std::shared_ptr<Tensor>(new Tensor(_meta, _storage, _offset));
    auto out = Tensor::create(_meta.shape, _meta.dtype, device_type, device);
    size_t total_bytes = numel() * elementSize();
    bool src_cpu = (this->deviceType() == LLAISYS_DEVICE_CPU);
    bool dst_cpu = (device_type == LLAISYS_DEVICE_CPU);
    llaisysMemcpyKind_t kind = src_cpu && dst_cpu ? LLAISYS_MEMCPY_H2H
                             : src_cpu ? LLAISYS_MEMCPY_H2D
                             : dst_cpu ? LLAISYS_MEMCPY_D2H
                             : LLAISYS_MEMCPY_D2D;
    core::context().setDevice(device_type, device);
    core::context().runtime().api()->memcpy_sync(out->data(), this->data(), total_bytes, kind);
    return out;
}
```

## 直觉 / 类比

Tensor 就像一张“地图”——storage 是实际地形（内存），shape/strides 是地图上的标注（怎么读地形）。permute 是旋转地图，slice 是裁掉一角，view 是换一种比例尺——地形本身没动。只有 contiguous() 是“按新地图重新铺一遍地形”。

另一个类比：storage 是一本书的原文，Tensor 是“从第 X 页开始、每隔 Y 行读一句、读成 Z 列的表格”这样的指令。view/permute/slice 只是改指令，不重印书。

## 常见误区

- **“view 就是改 shape”** → 必须验证连续性。shape (2,3,5) strides (30,10,1) 可以 view 成 (2,15)，但 permute 后 strides 变了就不能直接 view。强行 view 不连续的 Tensor 会读到错误数据——不是报错，是静默错误。
- **“strides 单位是字节”** → 不是，是**元素数**。实际字节偏移 = stride × elementSize()。这个区分在混合精度（FP16 和 FP32 混合）时尤其重要。
- **“slice 后 Tensor 拥有新数据”** → 不是，slice 只改 offset 和 shape，底层 storage 是共享的。修改 slice 后的 Tensor 会影响原 Tensor。

## 关联

- [框架分层与设备抽象](framework-architecture.md) — Tensor 的 storage 分配走 Runtime API
- [算子实现](operators.md) — 算子要求输入 Tensor 连续（isContiguous），否则需先 contiguous()
- 源码：[tensor.cpp](../../raw/wiki/llaisys/src/tensor/tensor.cpp)
