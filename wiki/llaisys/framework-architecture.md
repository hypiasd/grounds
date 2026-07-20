---
title: 推理引擎框架设计
topic: llaisys
tags: [llm-inference, cpp, device-abstraction, c-api]
summary: "LLAISYS 三层架构（Python ctypes → C API __export → C++ impl），Runtime API 函数指针表实现 C 风格设备多态，thread_local Context 管设备上下文，算子 switch(deviceType) 分发。核心哲学：一套接口，多套后端。"
created: 2026-07-20
updated: 2026-07-20
sources:
  - ../../raw/wiki/llaisys/
---

## TL;DR

LLAISYS 用三层架构实现"一套接口，多套后端"：Python 前端通过 ctypes 调用 C API（`.so` 导出的 `__export` 函数），C API 桥接到 C++ 内部实现。设备抽象通过 `LlaisysRuntimeAPI` 函数指针表（C 风格虚函数表）实现——CPU 填 `std::malloc`/`std::memcpy`，GPU 填 `cudaMalloc`/`cudaMemcpy`，上层代码完全不感知底层设备。

## 核心概念

### 三层调用链

```
Python (ctypes)  →  C API (.so/.dll 导出)  →  C++ 内部实现
```

| 层 | 位置 | 职责 |
|---|---|---|
| Python 前端 | `python/llaisys/` | Pythonic 接口，加载 `.so`，声明 ctypes 原型 |
| C API 边界 | `include/llaisys/*.h` | `__export` 函数（C linkage），ABI 契约 |
| C++ 实现 | `src/` | 真正逻辑：core / tensor / ops / models |

**为什么要 C API？** C++ 没有稳定 ABI（name mangling、vtable 布局编译器各异）。导出 C 函数 = 任何语言都能通过 FFI 调用。

### Runtime API：函数指针表

```cpp
// include/llaisys/runtime.h
struct LlaisysRuntimeAPI {
    get_device_count_api get_device_count;
    set_device_api set_device;
    device_synchronize_api device_synchronize;
    create_stream_api create_stream;
    destroy_stream_api destroy_stream;
    stream_synchronize_api stream_synchronize;
    malloc_device_api malloc_device;
    free_device_api free_device;
    malloc_host_api malloc_host;
    free_host_api free_host;
    memcpy_sync_api memcpy_sync;
    memcpy_async_api memcpy_async;
};
```

CPU 实现（`src/device/cpu/cpu_runtime_api.cpp`）：

```cpp
void *mallocDevice(size_t size) { return std::malloc(size); }
void memcpySync(void *dst, const void *src, size_t size, ...) { std::memcpy(dst, src, size); }

static const LlaisysRuntimeAPI RUNTIME_API = {
    &getDeviceCount, &setDevice, &deviceSynchronize,
    &createStream, &destroyStream, &streamSynchronize,
    &mallocDevice, &freeDevice, &mallocHost, &freeHost,
    &memcpySync, &memcpyAsync
};
```

### Context / Runtime：线程级设备管理

```cpp
// src/core/context/context.cpp
Context &context() {
    thread_local Context thread_context;  // 每线程独立
    return thread_context;
}
```

- **`thread_local`**：多线程推理时每个线程独立管设备，无需加锁
- **延迟初始化**：`setDevice(NVIDIA, 0)` 时才 `new Runtime(NVIDIA, 0)`
- **Runtime 持有 API 指针 + Allocator**：分配 Storage 时走对应设备的 `malloc_device`

### 算子设备分发模式

```cpp
// src/ops/add/op.cpp — 每个算子的统一模式
void add(tensor_t c, tensor_t a, tensor_t b) {
    CHECK_SAME_DEVICE(c, a, b);
    CHECK_SAME_SHAPE(c->shape(), a->shape(), b->shape());
    ASSERT(c->isContiguous() && a->isContiguous() && b->isContiguous(), "...");

    switch (c->deviceType()) {
    case LLAISYS_DEVICE_CPU:
        return cpu::add(c->data(), a->data(), b->data(), c->dtype(), c->numel());
#ifdef ENABLE_NVIDIA_API
    case LLAISYS_DEVICE_NVIDIA:
        return nvidia::add(...);
#endif
    default:
        EXCEPTION_UNSUPPORTED_DEVICE;
    }
}
```

### xmake 构建体系

```
llaisys-utils (static)     ← 工具函数
    ↑
llaisys-device-cpu (static) ← CPU Runtime API
    ↑
llaisys-device (static)    ← 设备路由
    ↑
llaisys-core (static)      ← Context / Runtime / Storage
    ↑
llaisys-tensor (static)    ← Tensor
    ↑
llaisys-ops-cpu (static)   ← CPU 算子实现
    ↑
llaisys-ops (static)       ← 算子分发入口
    ↑
llaisys (shared)           ← 最终 .so，导出 C API
```

条件编译：`xmake f --nv-gpu=y` → `add_defines("ENABLE_NVIDIA_API")` → NVIDIA 分支参与编译。

## 直觉 / 类比

把 LLAISYS 想象成迷你 OS 内核：对上提供统一 syscall（C API），对下通过驱动（Runtime API）适配不同硬件。用户程序（Python）不感知底层是 NVMe 还是 SATA——`read()` 就是 `read()`。

## 常见误区

- **"C API 只是薄包装"** → 它是可移植性基石，决定了参数传递方式（opaque pointer）、错误跨边界传播、ABI 稳定性。
- **"Context 是全局单例"** → 它是 `thread_local` 的，多线程各自独立。

## 关联

- [Tensor 实现](tensor.md) — Tensor 的 storage 分配直接走 Runtime.allocateDeviceStorage()
- [算子实现](operators.md) — 每个算子遵循本文描述的设备分发模式
- [vLLM V1 架构](../vllm/vllm-v1-architecture.md) — vLLM 是产品级引擎，LLAISYS 是教学级引擎，设计思路同源
- 源码：[LLAISYS 仓库](../../raw/wiki/llaisys/)
