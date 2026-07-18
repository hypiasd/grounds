---
title: Smart Pointers
topic: cpp
tags: [cpp, memory-management, raii, ownership, cpp11]
summary: unique_ptr 独占所有权、零开销、不可拷贝只可移动。shared_ptr 共享所有权、引用计数（原子操作）、控制块。weak_ptr 旁观不持有、用于打破循环引用。默认用 unique_ptr，只在真正需要共享所有权时才升级到 shared_ptr。make_unique / make_shared 优于直接用 new。
created: 2026-07-18
updated: 2026-07-18
---

## TL;DR

智能指针是 RAII 在堆内存管理上的落地——把裸指针包进类，析构时自动 `delete`。C++11 引入三种：`unique_ptr`（独占，零开销），`shared_ptr`（共享引用计数），`weak_ptr`（旁观，打破循环引用）。铁律：默认用 `unique_ptr`，只有真正需要共享所有权时才升级到 `shared_ptr`。工厂函数 `make_unique` / `make_shared` 优于手写 `new`。

## 核心概念

### unique_ptr — 独占所有权，零开销

```cpp
auto p = std::make_unique<int>(42);  // 构造
*p = 10;                             // 像裸指针一样用
auto q = std::move(p);               // 转移所有权，p 变成 nullptr
// p 离开作用域——safe，delete nullptr 是空操作
// q 离开作用域——自动 delete
```

- **大小等于一个裸指针**（默认删除器下零开销）
- **不可拷贝，只可移动**——类型层面保证独占
- `make_unique<T>(args...)` 优于 `new T(args...)`：异常安全 + 少写一次类型名
- 支持数组：`std::unique_ptr<int[]>` 内部用 `delete[]`

### shared_ptr — 共享所有权，引用计数

```cpp
auto p = std::make_shared<int>(42);  // refcount = 1
auto q = p;                          // refcount = 2
p.reset();                           // refcount = 1，p 变成 nullptr
// q 离开作用域 → refcount = 0 → delete
```

**内部结构**：每个 `shared_ptr` 包含**两个指针**——一个指向托管对象，一个指向控制块。

控制块（control block）里存着：

| 字段 | 用途 |
|------|------|
| 强引用计数 | 当前有几个 shared_ptr 指向对象 |
| 弱引用计数 | 当前有几个 weak_ptr 观察对象 |
| 删除器 | 析构时怎么释放（默认 `delete`） |
| 分配器 | 控制块自己的内存怎么分配 |

引用计数的增减是**原子操作**——多线程下安全。

**`make_shared` vs `new + shared_ptr`**：

```cpp
// new + shared_ptr：两次分配
auto p = std::shared_ptr<int>(new int(42));
// 分配 1: new int(42) → 对象
// 分配 2: 内部 new control_block → 控制块

// make_shared：一次分配
auto p = std::make_shared<int>(42);
// 单次分配：对象 + 控制块紧挨在一起——少一次 malloc，缓存更友好
```

### weak_ptr — 旁观不持有

```cpp
auto sp = std::make_shared<int>(42);
std::weak_ptr<int> wp = sp;        // 不增加引用计数
// sp.reset() 或 sp 离开作用域 → refcount = 0，对象被 delete
if (auto locked = wp.lock()) {     // 尝试获取 shared_ptr
    *locked = 10;                  // 对象还活着
} else {
    // 对象已经死了
}
```

weak_ptr 的两个用途：
1. **打破 shared_ptr 循环引用**（见 [Memory Pitfalls](memory-pitfalls.md)）
2. **缓存/观察者模式**——引用一个对象但不阻止它被释放

weak_ptr 只能从 `shared_ptr` 构造（需要控制块来检查引用计数），不能从 `unique_ptr` 创建。

### 三兄弟速查

| | unique_ptr | shared_ptr | weak_ptr |
|---|---|---|---|
| 所有权 | 独占 | 共享 | 无 |
| 拷贝 | 否 | 是（refcount+1） | 是 |
| 移动 | 是 | 是 | 是 |
| 大小 | 1 指针（默认删除器） | 2 指针 | 2 指针 |
| 开销 | 零 | 原子引用计数 + 控制块 | 零（使用时 lock） |
| 工厂函数 | `make_unique` | `make_shared` | 从 shared_ptr 构造 |

### 如何选择

```cpp
// 默认：unique_ptr——你有一个所有者
std::unique_ptr<Widget> owner = std::make_unique<Widget>();

// 需要共享所有权时：shared_ptr——多个所有者，最后走的关灯
std::shared_ptr<Cache> cache = std::make_shared<Cache>();

// 打破循环引用/缓存观察时：weak_ptr
std::weak_ptr<Node> parent;  // 子节点不拥有父节点
```

**原则**：shared_ptr 不是"更安全"的 unique_ptr——引用计数有代价（原子操作 + 控制块内存），更重要的是它模糊了所有权。当每个人都持有 shared_ptr，没人清楚"谁负责释放"。能独占就独占。

### make_shared 的隐形陷阱

`make_shared` 把对象和控制块分配在同一块内存中。好处是少一次 `malloc`。代价：

```cpp
auto sp = std::make_shared<HugeObject>(/* 100MB */);
std::weak_ptr<HugeObject> wp = sp;
sp.reset();  // 引用计数归零，但 100MB 内存还在——weak_ptr 活着，控制块不能释放
// 100MB 只有等所有 weak_ptr 也析构后才回收
```

如果 weak_ptr 长期持有或存入全局结构，这 100MB 就长期卡着。此时用 `shared_ptr<T>(new T(...))`——两次分配，对象和控制块分开，shared_ptr 清零后对象内存立即释放，只剩控制块等着 weak_ptr。

## 直觉 / 类比

- `unique_ptr` 像一本日记本——只有一个人持有，要给别人就得交出去（移动），不能再偷看。
- `shared_ptr` 像共享单车的电子锁——好几个人扫了码都能骑，最后一个还车的人才负责锁车。
- `weak_ptr` 像你记着那辆单车停在哪——但不扫码，不参与还车计数。去看一眼如果车还在就能骑，不在就算了。

## 常见误区

- **误区一："能 share 就用 shared_ptr，安全。"** — shared_ptr 有代价（原子计数 + 控制块），更重要的是模糊了所有权。默认 unique_ptr，只在确实需要共享所有权时升级。
- **误区二："weak_ptr 可以指向任何东西。"** — weak_ptr 只能从 shared_ptr 构造，不能从 unique_ptr 创建。
- **误区三："make_shared 永远是首选。"** — 需要自定义删除器时 `make_shared` 不支持（内部只支持默认 `delete`）。另外 `make_shared` + `weak_ptr` 长期持有会导致大对象内存滞留。
- **误区四："把智能指针用上了就内存安全了。"** — 智能指针消灭了"忘记 delete"，但不能消灭"悬垂指针"：`unique_ptr::get()` 返回裸指针，如果 unique_ptr 先析构了，裸指针照样悬垂。

## 关联

- [RAII](raii.md) — 智能指针是 RAII 在堆内存上的直接落地
- [Move Semantics](move-semantics.md) — unique_ptr 的可移动性 = 移动语义 + 所有权转移
- [Memory Pitfalls](memory-pitfalls.md) — shared_ptr 循环引用、悬垂指针、use-after-move 等陷阱
- [Stack vs Heap](stack-vs-heap.md) — 智能指针管理的对象在堆上，指针本身通常在栈上
- [Perfect Forwarding](perfect-forwarding.md) — `make_unique` / `make_shared` 内部用完美转发将参数传给构造函数


## 面试常见问题

- **Q: unique_ptr、shared_ptr、weak_ptr 分别有什么特征和用途？**
  **A**: unique_ptr 独占所有权，不可拷贝只可移动，零额外开销，适合明确单一所有者的场景。shared_ptr 共享所有权，通过原子引用计数管理生命周期，最后一个持有者释放资源。weak_ptr 不持有所有权，不增加引用计数，通过 `lock()` 尝试获取 shared_ptr，主要用于打破循环引用和实现缓存/观察者模式。
  *来源：知乎 • LLQuant • [链接](https://zhuanlan.zhihu.com/p/638292065)；牛客 • 茶叶蛋在拧螺丝 • 固生堂面试*

- **Q: shared_ptr 是线程安全的吗？使用时需要注意什么？**
  **A**: shared_ptr 的引用计数操作（拷贝/析构）是线程安全的——底层使用原子变量。但 shared_ptr 指向的对象本身不是线程安全的，需要额外同步。另外，向另一个线程传递 shared_ptr 时不要传引用——传引用不会增加引用计数，原线程释放后悬垂。应通过拷贝传值。
  *来源：知乎 • LLQuant • [链接](https://zhuanlan.zhihu.com/p/638292065)*

- **Q: 为什么不能用同一个裸指针初始化多个智能指针？**
  **A**: 每个智能指针都认为自己独占/共享管理这个资源，析构时各自 `delete` 一次——double free。正确做法是从 `new` 或 `make_unique`/`make_shared` 直接初始化，不要让裸指针经过多个智能指针之手。
  *来源：知乎 • LLQuant • [链接](https://zhuanlan.zhihu.com/p/638292065)*

- **Q: 循环引用是怎么产生的？如何解决？**
  **A**: 两个对象各自持有对方的 shared_ptr——引用计数各为 2。离开作用域后各减 1 变为 1，但都等着对方先释放，形成死锁。解决方案是把其中一方的 shared_ptr 改为 weak_ptr——weak_ptr 不增加引用计数，打破循环。
  *来源：知乎 • LLQuant • [链接](https://zhuanlan.zhihu.com/p/638292065)；小红书 • 牛马日记 • [链接](https://www.xiaohongshu.com/explore/6a0aa2b1000000003502df62)*

- **Q: 一个类如何安全地返回指向自己的 shared_ptr？为什么要用 `enable_shared_from_this`？**
  **A**: 继承 `std::enable_shared_from_this<T>`，方法内调用 `shared_from_this()`。直接 `return shared_ptr<T>(this)` 会导致同一对象被多个独立的控制块管理——每个控制块的引用计数各自归零后各自 `delete`，double free。`shared_from_this` 确保返回的 shared_ptr 和已有的 shared_ptr 共享同一个控制块。
  *来源：知乎 • LLQuant • [链接](https://zhuanlan.zhihu.com/p/638292065)*
