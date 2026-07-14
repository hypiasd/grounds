---
title: std::ranges::sort
topic: cpp
tags: [algorithm, cpp20, ranges]
summary: C++20 引入的 ranges::sort 直接接受容器而非迭代器对，语法更简洁且避免 std::sort(v.begin(), w.end()) 这种迭代器配错的隐蔽 bug。sort 在 std 下仍然存在，ranges::sort 是对 std::sort 的 ranges 封装。
created: 2026-07-14
updated: 2026-07-14
---

# std::ranges::sort

## TL;DR

`std::sort(begin, end)` 需要手动传一对迭代器，`std::ranges::sort(container)` 直接把整个容器扔过去，内部自动调 begin/end。好处：少打字 + 避免迭代器配错的隐蔽 bug。

## 核心概念

### 语法对比

```cpp
// C++98：需要手动传迭代器对
std::sort(v.begin(), v.end());

// C++20：直接传容器（需 #include <algorithm>）
std::ranges::sort(v);
```

### 为什么 ranges 版更安全

`std::sort(v.begin(), w.end())` 迭代器来自不同容器——编译器不报错，运行时行为未定义。`std::ranges::sort(v)` 不给你犯这个错的机会：容器和迭代器的配对由库内部保证。

### 代码中写 `ranges::sort` 的前提

通常代码某处有 `using namespace std::ranges;` 或 `namespace ranges = std::ranges;`，否则完全限定名应是 `std::ranges::sort`。LeetCode 的在线评测环境可能预先导入了 ranges 命名空间。

### ranges 的其他排序能力

```cpp
std::ranges::sort(v, std::greater{});          // 降序
std::ranges::sort(v, {}, &Person::age);        // 按成员排序（投影）
std::ranges::stable_sort(v);                   // 稳定排序
```

投影（projection）是 ranges 的独特优势：`&Person::age` 告诉 sort"比较之前先取 age 字段"，不需要手写 lambda。

## 直觉 / 类比

`std::sort` 像叫外卖时必须报"从第三个货架到第七个货架"——你得知道仓库内部布局。`std::ranges::sort` 像直接说"把这箱东西排好"——仓库布局是库的事，你只关心结果。

## 常见误区

- **误区一：以为 sort 被移到了 ranges 里，`std::sort` 不能用了**——`std::sort` 仍然存在且正常工作。ranges 是新增的封装层，不是替代。
- **误区二：写 `ranges::sort` 不写 `std::` 前缀也能编过**——必须有人帮你导入了命名空间（`using namespace std::ranges;`），否则会报找不到。在 LeetCode 环境之外写代码时记得补全。
- **误区三：以为 ranges 只是省几个字**——投影（projection）能力是 `std::sort` 没有的，`std::ranges::sort(v, {}, &Person::age)` 不需要手写比较器。

## 面试常见问题

- **Q: `std::sort` 和 `std::ranges::sort` 有什么区别？**
  **A**: `std::sort` 接受迭代器对 `(begin, end)`，`std::ranges::sort` 直接接受 range（容器）。ranges 版更简洁、更安全（不会配错迭代器对），还支持投影（projection）——可以用 `&Person::age` 指定排序依据而无需写 lambda。`std::ranges::sort` 是 C++20 新增，`std::sort` 仍然可用。

- **Q: 为什么说 `std::ranges::sort` 比 `std::sort` 更安全？**
  **A**: `std::sort(v.begin(), w.end())` 传了两个不同容器的迭代器，编译器不报错但运行时是未定义行为。`std::ranges::sort(v)` 整个 range 内部自动配对 begin/end，这种错误不可能发生。

- **Q: C++20 ranges 除了 sort 还有哪些常用算法？**
  **A**: 几乎所有 `<algorithm>` 的算法都有对应的 ranges 版本：`std::ranges::find`、`std::ranges::copy`、`std::ranges::transform`、`std::ranges::for_each` 等。它们统一接受 range 而非迭代器对，并支持投影。

## 关联

- [Range-Based For with auto&](range-based-for-reference.md) — 同样是 C++ 现代特性，让循环和算法调用更简洁
