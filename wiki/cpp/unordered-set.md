---
title: unordered_set
topic: cpp
tags: [stl, hash-table, container, cpp11]
summary: 基于哈希表的集合容器，不排序、自动去重，平均 O(1) 查找/插入/删除。与 std::set（红黑树，有序，O(log n)）相对。emplace 比 insert 省一次临时对象构造——但只在传构造参数时成立，对象已造好则两者等价。
created: 2026-07-15
updated: 2026-07-15
---


## TL;DR

哈希表底层的集合：不排序、自动去重、平均 O(1) 操作。需要"查得快且不在乎顺序"时首选。`emplace` 在传构造参数时比 `insert` 少一次临时对象构造，但对象已造好则两者等价。

## 核心概念

### 底层结构与复杂度

每个元素经哈希函数算出桶号：$\text{bucket} = \text{hash}(x) \bmod \text{bucket\_count}$，塞进对应桶里。

- 平均：插入 / 查找 / 删除 $O(1)$
- 最坏：$O(n)$（所有元素哈希冲突，挤进同一个桶，退化成链表）

### 与 std::set 的区别

| | `unordered_set` | `std::set` |
|---|---|---|
| 底层 | 哈希表 | 红黑树 |
| 顺序 | 无序 | 有序 |
| 复杂度 | 平均 $O(1)$，最坏 $O(n)$ | 稳定 $O(\log n)$ |
| 适用 | 只要查得快 | 需要排序/范围查询 |

### 成员函数分类

**查存在性**（都平均 $O(1)$，返回类型不同）：

- `contains(x)` — C++20，返回 `bool`，最直白
- `count(x)` — 返回 `size_t`，set 去重后只会是 0 或 1；C++20 之前只能靠它查存在性
- `find(x)` — 返回迭代器，找不到等于 `end()`；需要拿位置操作时用它

**插入**：

- `insert(x)` — 接收已构造对象，拷贝或移动进容器；返回 `pair<iterator, bool>`
- `emplace(args...)` — 接收构造参数，原地构造，省掉临时对象

**删除**：

- `erase(x)` — 按值删，返回删了几个（0 或 1）
- `erase(iter)` — 按迭代器删，返回下一个迭代器

**大小**：`size()`、`empty()`

**遍历**：`for (int x : st)` — 顺序不保证与插入顺序一致，按桶排列

### emplace vs insert

```cpp
unordered_set<string> st;

// insert：先构造临时 string，再移动进容器
st.insert(string("hello"));

// emplace：参数直接转发给 string 构造函数，原地构造，无临时对象
st.emplace("hello");
```

emplace 的优势**只在传构造参数时成立**。如果对象已经造好了，两者等价——都要从已存在的对象拷贝或移动。

### 迭代器范围构造自动去重

```cpp
unordered_set<int> st(nums.begin(), nums.end());
```

即使 `nums` 有重复元素，`st` 里每个值只存一份。

## 直觉 / 类比

想象一个有很多格子的信件分拣架。扔一封信进去，先看邮编（哈希值）决定放哪格（桶），不关心格子里信的顺序。查的时候也一样——算邮编直接去那格翻，不用一格一格扫。

## 常见误区

- **以为永远是 $O(1)$**：哈希冲突严重时退化到 $O(n)$。刷题里有人专门构造能卡 `unordered_set` 的测试数据，逼你改用 `std::set`。
- **和 `std::set` 搞混**：要排序选 `set`（$O(\log n)$），只要查得快选 `unordered_set`（平均 $O(1)$）。
- **以为 emplace 永远比 insert 快**：对象已造好时两者等价，emplace 只在传构造参数时省一次临时对象构造。
- **遍历时依赖顺序**：`unordered_set` 的遍历顺序由桶决定，不保证与插入顺序一致。

## 面试常见问题

- **Q: `unordered_set` 和 `set` 的区别？什么时候选哪个？**
  **A**: `unordered_set` 底层哈希表，无序，平均 $O(1)$ 最坏 $O(n)$；`set` 底层红黑树，有序，稳定 $O(\log n)$。需要排序或范围查询选 `set`，只要快速查找且不在乎顺序选 `unordered_set`。注意 `unordered_set` 最坏情况会被恶意构造的数据卡到 $O(n)$。

- **Q: `unordered_set` 哈希冲突时怎么处理？为什么会退化到 $O(n)$？**
  **A**: 冲突元素挂在同一个桶里（链表或开放寻址）。如果大量元素哈希到同一个桶，查找退化为链表遍历 $O(n)$。标准库会在负载因子超阈值时自动 rehash 扩容，但如果哈希函数本身差（或被恶意构造），扩容也救不了。

- **Q: `emplace` 和 `insert` 有什么区别？**
  **A**: `insert` 接收已构造的对象，再拷贝或移动进容器；`emplace` 接收构造参数，通过完美转发在容器内部原地构造，省掉临时对象。但对 `int` 等平凡类型没区别，且对象已造好时两者等价。

## 关联

- [Move Semantics](move-semantics.md) — emplace 内部用完美转发实现，是移动语义的应用场景
- [Perfect Forwarding](perfect-forwarding.md) — emplace 的"原地构造"靠完美转发把参数转发给构造函数
- [Range-Based For with auto&](range-based-for-reference.md) — 遍历 unordered_set 用的就是 range-based for 语法
