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

Tensor 不拥有数据——它通过 `storage`（shared_ptr 指向一块设备内存）+ `offset`（字节偏移）+ `meta`（shape/strides/dtype）来"描述"数据。view/permute/slice 全部只修改 meta 或 offset，不搬移数据。这就是"形状是幻觉，内存是真相"——同一个 storage 可以被多个 Tensor 以不同形状/步长描述。

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

```cpp
// === load: 从主机内存加载数据到 Tensor ===
void Tensor::load(const void *src_) {
    size_t total_bytes = numel() * elementSize();
    core::context().setDevice(this->deviceType(), this->deviceId());
    core::context().runtime().api()->memcpy_sync(
        this->data(), src_, total_bytes, LLAISYS_MEMCPY_H2D);
}

// === isContiguous: 判断内存是否连续 ===
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

// === permute: 重排维度顺序（零拷贝）===
tensor_t Tensor::permute(const std::vector<size_t> &order) const {
    size_t ndim_ = ndim();
    TensorMeta new_meta;
    new_meta.dtype = _meta.dtype;
    new_meta.shape.resize(ndim_);
    new_meta.strides.resize(ndim_);
    for (size_t i = 0; i < ndim_; i++) {
        new_meta.shape[i] = _meta.shape[order[i]];
        new_meta.strides[i] = _meta.strides[order[i]];
    }
    return std::shared_ptr<Tensor>(new Tensor(new_meta, _storage, _offset));
}

// === view: 重塑形状（零拷贝，要求连续）===
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

// === slice: 沿某维切片（零拷贝）===
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

// === contiguous: 使非连续 Tensor 变连续（拷贝数据）===
tensor_t Tensor::contiguous() const {
    if (isContiguous())
        return std::shared_ptr<Tensor>(new Tensor(_meta, _storage, _offset));
    auto out = Tensor::create(_meta.shape, _meta.dtype, deviceType(), deviceId());
    size_t elem_size = elementSize();
    size_t total = numel(), ndim_ = ndim();
    std::vector<size_t> idx(ndim_, 0);
    std::byte *dst_ptr = out->data();
    for (size_t i = 0; i < total; i++) {
        ptrdiff_t src_elem_offset = 0;
        for (size_t d = 0; d < ndim_; d++)
            src_elem_offset += static_cast<ptrdiff_t>(idx[d]) * _meta.strides[d];
        std::memcpy(dst_ptr + i * elem_size,
                    this->data() + src_elem_offset * (ptrdiff_t)elem_size, elem_size);
        for (size_t d = ndim_; d > 0; d--) {
            idx[d - 1]++;
            if (idx[d - 1] < _meta.shape[d - 1]) break;
            idx[d - 1] = 0;
        }
    }
    return out;
}

// === to: 跨设备迁移 ===
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

Tensor 就像一张"地图"——storage 是实际地形（内存），shape/strides 是地图上的标注（怎么读地形）。permute 是旋转地图，slice 是裁掉一角，view 是换一种比例尺——地形本身没动。只有 contiguous() 是"按新地图重新铺一遍地形"。

## 常见误区

- **"view 就是改 shape"** → 必须验证连续性。shape (2,3,5) strides (30,10,1) 可以 view 成 (2,15)，但 permute 后 strides 变了就不能直接 view。
- **"strides 单位是字节"** → 不是，是**元素数**。实际字节偏移 = stride × elementSize()。

## 关联

- [框架分层与设备抽象](framework-architecture.md) — Tensor 的 storage 分配走 Runtime API
- [算子实现](operators.md) — 算子要求输入 Tensor 连续（isContiguous），否则需先 contiguous()
- 源码：[tensor.cpp](../../raw/wiki/llaisys/src/tensor/tensor.cpp)
