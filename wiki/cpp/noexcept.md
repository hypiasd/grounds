---
title: noexcept
topic: cpp
tags: [cpp11, exception, performance, move-semantics]
summary: noexcept 标记函数承诺不抛异常。移动构造/赋值必须加 noexcept，否则 vector 扩容时退化为拷贝——因为 vector 需要保证异常安全，移动到一半抛异常会丢数据且无法回滚。noexcept 函数如果真的抛异常，会触发 std::terminate 直接终止程序。
created: 2026-07-15
updated: 2026-07-15
---


## TL;DR

`noexcept` 告诉编译器"这个函数保证不抛异常"。移动构造/赋值必须加 `noexcept`，否则 `vector` 扩容时不信任你的移动操作，退化为拷贝。`noexcept` 函数如果真的抛异常，程序直接 `std::terminate` 终止。

## 核心概念

### 语法

```cpp
void foo() noexcept { ... }           // 承诺不抛异常
void bar() noexcept(true) { ... }     // 等价于上一行
void baz() noexcept(expr) { ... }     // 条件式：expr 为 true 时承诺不抛
```

### 为什么移动构造必须加 noexcept

`vector` 扩容时要把旧元素搬到新内存。它的策略是：

1. 移动构造是 `noexcept` → 直接移动，$O(1)$
2. 移动构造**可能抛异常** → 退化为拷贝

为什么这么保守？想象 `vector` 正在搬第 50 个元素，移动构造抛异常了：

- 前 49 个已经移动走了（源对象空了）
- 第 50 个没搬成
- 旧内存里有 50 个空壳 + 剩余元素，新内存里有 49 个元素
- **状态已损坏，无法回滚**

但如果用拷贝，旧元素都还在，搬失败时把新内存释放掉就行，旧数据完好无损。所以 `vector` 只有在你承诺不抛异常时才敢用移动。

```cpp
// 不加 noexcept → vector 扩容时拷贝，白写了移动构造
Buffer(Buffer&& other) { ... }

// 加 noexcept → vector 扩容时移动，真正的性能收益
Buffer(Buffer&& other) noexcept { ... }
```

### noexcept 函数抛异常会怎样

直接 `std::terminate` 终止程序——不会向上传播，不会被 catch 捕获。因为 noexcept 是一个承诺，违反承诺意味着程序处于不可恢复的状态。

## 直觉 / 类比

noexcept 像签了一份"绝不出错"的保证书。签了之后，别人（如 vector）才敢把重要工作交给你（用移动而不是保守拷贝）。但如果签了保证书还出了错（抛异常），直接开除（terminate），没有挽回余地。

## 常见误区

- **写了移动构造就以为 vector 会用它**：不加 `noexcept`，vector 不信任你的移动操作，扩容时退化为拷贝——白写了。
- **以为 noexcept 只是建议**：noexcept 是承诺，违反承诺（抛异常）直接 `std::terminate`，不是普通的异常传播。
- **以为 noexcept 只是给编译器看的**：它也给标准库看。`std::vector`、`std::allocator` 等会在编译期用 `noexcept` 检查（`std::is_nothrow_move_constructible`）来决定策略。

## 面试常见问题

- **Q: noexcept 的作用是什么？**
  **A**: noexcept 标记函数承诺不抛异常。这让编译器能做更好的优化（不需要生成异常处理代码），更重要的是让标准库容器在编译期检查后敢用移动而非拷贝。如果 noexcept 函数真的抛异常，会触发 std::terminate 终止程序。

- **Q: 为什么移动构造函数要加 noexcept？**
  **A**: vector 扩容搬元素时需要保证异常安全——如果移动到一半抛异常，已移动的元素源对象空了，无法回滚。所以 vector 只有在移动操作是 noexcept 时才敢用移动，否则退化为拷贝。不加 noexcept 等于白写了移动构造。

- **Q: noexcept 函数抛异常会怎样？**
  **A**: 调用 std::terminate 直接终止程序，异常不会被 catch 捕获，也不会向上传播。因为 noexcept 是一个承诺，违反承诺意味着程序状态不可恢复。

## 关联

- [Move Semantics](move-semantics.md) — 移动构造/赋值必须加 noexcept 才能被 vector 使用，否则退化为拷贝
- [Value Categories](value-categories.md) — 值类别决定了编译器选拷贝还是移动，noexcept 决定了 vector 敢不敢用移动
