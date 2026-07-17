---
title: Range-Based For with auto&
topic: cpp
tags: [syntax, reference, cpp11, performance]
summary: Range-based for loop 中 auto / auto& / const auto& / auto&& 的选择取决于两个维度：是否修改原数据和元素拷贝成本。对 int 等小类型用值拷贝即可；对 string、vector 等大类型必须用引用避免 O(n) 拷贝。
created: 2026-07-14
updated: 2026-07-14
---


## TL;DR

`for (auto x : v)` 每次迭代拷贝一份元素，`for (auto& x : v)` 直接操作原数据零拷贝。选择哪种取决于两件事：要不要改原数据、元素大不大（值不值得拷贝）。`const auto&` 是读大元素的最优解——零拷贝且防误改。

## 核心概念

Range-based for 的四种写法与选择矩阵：

| 写法 | 拷贝开销 | 可修改原数据 | 适用场景 |
|------|----------|-------------|---------|
| `for (auto x : v)` | 每次拷贝 | 否（改的是副本） | `int`、`char` 等小类型，拷贝比解引用还快 |
| `for (auto& x : v)` | 零 | **是** | 需要修改原容器元素 |
| `for (const auto& x : v)` | 零 | 否（const 保护） | 读大元素（`string`、`vector`、自定义类） |
| `for (auto&& x : v)` | 零 | 取决于 constness | 万能写法，转发引用绑定一切——包括 `vector<bool>` 代理对象 |

### auto&& 的独特地位

`auto&&` 是转发引用（forwarding reference），能绑定左值、右值、const、非 const——**总是编译通过且零拷贝**。它也是解决 `vector<bool>` 陷阱的唯一通用写法：

```cpp
vector<bool> vb = {true, false};
for (auto&& x : vb) x = false;  // OK：转发引用绑定代理对象
// for (auto& x : vb)  ...      // 编译错误！vector<bool>::reference 是临时量
```

### 底层展开

编译器把 `for (auto& x : v)` 展开为等价于：

```cpp
for (auto it = begin(v); it != end(v); ++it) {
    auto& x = *it;  // 引用绑定到解引用结果
    // 循环体
}
```

这解释了为什么引用能避免拷贝——`x` 直接绑定到 `*it`（迭代器解引用的结果），没有发生赋值。

## 直觉 / 类比

`for (auto x : v)` 像每次借书前先复印一本给你——你看完复印本，原书不动。`for (auto& x : v)` 是直接把原书递过来——你在原书上批注（改数据），或者只看不写（读数据），但始终操作的是一本书。`const auto&` 是给你一本塑封的原书——能看不能写。

## 常见误区

- **误区一：以为 `for (auto x : v) x = 5;` 能修改原容器**——改的是副本，原数据纹丝不动。想修改必须用 `auto&`。
- **误区二：读大元素也用 `auto`**——`for (auto s : strs)` 对 `vector<string>` 每次迭代完整拷贝一个 string，O(n) 的隐藏开销。应该用 `const auto&`。
- **误区三：引用就是用来修改的**——其实引用更常用的场景是读大元素时零拷贝。`const auto&` 在读场景比 `auto&` 更好：语义更清晰（别人一看就知道只读），且防止你不小心改了。
- **误区四：`vector<bool>` 能用 `auto&`**——`vector<bool>` 是特化，元素不是 `bool&` 而是代理对象 `vector<bool>::reference`，非 const 左值引用绑不上临时代理对象。通用解法是 `auto&&`。

## 面试常见问题

- **Q: `for (auto x : v)` 和 `for (auto& x : v)` 的区别？什么时候用哪个？**
  **A**: 两个维度。一是能不能改原数据——`auto&` 能改，`auto` 改的是副本。二是拷贝开销——`auto` 每次迭代拷贝一份，对于 `string`、`vector` 等大类型很贵，应用 `const auto&` 零拷贝只读。`int`、`char` 等小类型用 `auto` 即可，拷贝一个 int 比解引用指针还快。

- **Q: `auto&` 和 `const auto&` 怎么选？**
  **A**: 绝大多数读场景用 `const auto&`——零拷贝 + 语义明确（只读）+ 编译器能做更多优化。只有确实要修改原数据时才用 `auto&`。

- **Q: 为什么 `vector<bool>` 不能用 `for (auto& x : vb)`？**
  **A**: `vector<bool>` 是标准库的特殊优化——用位压缩存储，每个"元素"不是真正的 `bool` 对象，而是代理对象 `vector<bool>::reference`。`*it` 返回的是临时代理对象，非 const 左值引用不能绑定到临时量。用 `auto&&`（转发引用）可以绑定任何值类别，这是通用解法。

## 关联

- [Move Semantics](move-semantics.md) — range-based for 中引用是对原数据 `std::move` 的前提：无引用则 move 的是副本，原数据不动
- [std::ranges::sort](ranges-sort.md) — 同样是 C++ 现代特性的简化，减少样板代码
