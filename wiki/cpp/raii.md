---
title: RAII
topic: cpp
tags: [cpp, memory-management, exception-safety, resource-management]
summary: Resource Acquisition Is Initialization——把资源获取绑定到对象构造，释放绑定到对象析构。用栈对象的自动析构来驱动堆资源、文件句柄、互斥锁等一切需要配对释放的资源，实现异常安全。RAII 不是只等于智能指针——文件流、lock_guard 都遵循同一个原则。
created: 2026-07-18
updated: 2026-07-18
---

## TL;DR

RAII 是 C++ 最核心的资源管理哲学：**构造时获取资源，析构时释放资源。** 它用栈展开（stack unwinding）保证即使抛异常也不会泄漏——不论函数怎么退出，栈对象的析构函数一定会被调用。RAII 管一切需要配对释放的东西：堆内存、文件句柄、互斥锁、数据库连接。

## 核心概念

### 原理：把"释放"交给编译器

```cpp
// 裸指针——每次 return 前必须手动 delete，抛异常时泄漏
void bad() {
    int* p = new int[1000];
    do_something();       // 这里抛异常 → delete 永远执行不到 → 泄漏
    do_something_else();  // 这里也可能抛异常
    delete[] p;
}

// RAII——不管怎么退出，析构都会执行
void good() {
    std::vector<int> v(1000);  // 内部在堆上分配，析构时自动 delete[]
    do_something();             // 即使抛异常，栈展开时 v.~vector() 自动调用
    do_something_else();
}
```

C++ 保证：函数退出时（return、抛异常、走到末尾），所有已构造完成的栈对象的析构函数会按构造的逆序被调用。这就是"栈展开"（stack unwinding）。

### RAII 不限于内存

任何需要"获取 → 使用 → 释放"配对的资源，都可以包装成 RAII 类：

| 资源类型 | RAII 包装 |
|---------|----------|
| 堆内存 | `std::unique_ptr` / `std::shared_ptr` / `std::vector` |
| 文件 | `std::ifstream` / `std::ofstream`（析构时 fclose） |
| 互斥锁 | `std::lock_guard` / `std::scoped_lock`（析构时 unlock） |
| 数据库连接 | 自定义类，析构时断开连接 |

### 编写一个 RAII 类

```cpp
class Buffer {
    int* data_;
    size_t size_;
public:
    Buffer(size_t n) : data_(new int[n]), size_(n) {}  // 构造 = 获取资源
    ~Buffer() { delete[] data_; }                       // 析构 = 释放资源
    int& operator[](size_t i) { return data_[i]; }
};

void work() {
    Buffer buf(1000);
    buf[0] = 42;
    // ... 复杂逻辑，可能抛异常 ...
}  // buf 离开作用域，析构自动 delete[]——保证不泄漏
```

### RAII 的边界：什么时候不合适

1. **资源生命周期不匹配任何作用域**：如果你的资源需要在某个精确时刻释放而非"离开 `}`"，RAII 反而别扭。
2. **所有权模糊**：十个对象各自持有同一资源的裸指针，每个都想在自己析构时释放——这不是 RAII 的问题，是所有权不清的问题，需要智能指针来解决。
3. **全局资源**：全局 RAII 对象的析构顺序在不同翻译单元间是不确定的——可能 A 已经析构（文件关闭），B 析构时还想写日志，UB。

## 直觉 / 类比

你去健身房领一把储物柜钥匙，挂在手腕上。走的时候还钥匙——不管你是正常练完离开、还是临时有事中途冲出去，只要有还钥匙这个动作，柜子就不会一直被占着。RAII 就是这把钥匙：资源在拿钥匙那一刻获得，在钥匙离手那一刻释放。钥匙（栈对象）的生命周期就是资源的使用周期。

## 常见误区

- **误区一："RAII 就是智能指针。"** — RAII 是原则，智能指针是 RAII 在堆内存上的一个具体实现。`std::ifstream`（文件）、`std::lock_guard`（互斥锁）同样遵循 RAII，两者都不是智能指针。
- **误区二："有了 RAII 就不用管内存了。"** — RAII 解决的是"何时释放"（时机），不解决"释放什么"（所有权）。如果析构里写了 `delete p` 但 `p` 已经被别人 `delete` 过（double free），RAII 救不了你。时机的正确要配合所有权的清晰——这是下一节智能指针的职责。

## 关联

- [Stack vs Heap](stack-vs-heap.md) — RAII 的基石：用栈对象的自动析构来驱动堆资源的释放
- [Smart Pointers](smart-pointers.md) — RAII 在堆内存管理上的标准实现
- [Move Semantics](move-semantics.md) — unique_ptr 的可移动性是移动语义 + RAII 的结合：所有权通过移动转移，最后持有者析构时自动释放


## 面试常见问题

- **Q: RAII 的核心思想是什么？和手动 new/delete 相比在异常安全上强在哪里？**
  **A**: RAII 把资源获取绑定到对象构造、释放绑定到对象析构。无论函数正常返回还是抛异常，栈展开都会调用已构造对象的析构函数——异常安全是自动的。手动 new/delete 则需要在每个 `return` 和异常路径上手动释放，极易遗漏。
  *来源：牛客 • 服务端老cpp • 影石 C++ 一面面经；牛客 • 代码练习生_code • 智协慧同 C++开发 一面*

- **Q: C++ 中有哪些 RAII 的典型应用？**
  **A**: 智能指针（`unique_ptr` / `shared_ptr` 管理堆内存）、互斥锁守卫（`std::lock_guard` / `std::scoped_lock` 管理锁）、文件流（`std::ifstream` / `std::ofstream` 管理文件句柄）、数据库连接封装。任何需要"获取→使用→释放"配对的资源都适合 RAII 包装。
  *来源：牛客 • 服务端老cpp • 大华 C++ 面经*

- **Q: 什么是异常安全的三个级别（basic/strong/nothrow）？和 RAII 有什么关系？**
  **A**: Basic guarantee：异常发生后程序状态仍然有效（不泄漏、不破坏不变量）。Strong guarantee：操作要么完全成功，要么完全回滚（commit-or-rollback）。Nothrow guarantee：操作绝不抛异常。RAII 是实现 basic guarantee 的基础——即使抛异常，析构函数保证资源被释放、不泄漏。
  *来源：牛客 • 服务端老cpp • 影石 C++ 一面面经*
