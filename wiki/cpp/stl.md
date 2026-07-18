---
title: STL
topic: cpp
tags: [stl, containers, algorithms, iterators, practical-tips]
summary: STL（Standard Template Library）是 C++ 标准库的核心三件套——容器存数据、算法操作数据、迭代器连接二者。序列容器（vector/deque/list）各有不同的内存布局和迭代器失效规则；关联容器（set/map）基于红黑树有序存储，operator[] 会意外插入默认值；无序容器基于哈希表 O(1) 但不排序；容器适配器（stack/queue/priority_queue）在底层容器上限制接口；算法库 100+ 个，配合五种迭代器类别实现容器与算法的自由组合。Erase-Remove Idiom 是删除元素的标准写法。
created: 2026-07-18
updated: 2026-07-18
---

# STL

## TL;DR

STL 六件套：序列容器、关联容器（有序+无序）、容器适配器、迭代器、算法、pair/tuple。核心设计：容器存数据，算法操作数据，迭代器是粘合剂。选容器的第一岔路口——要不要排序？要不要随机访问？元素唯一吗？——决定了性能特征和可用 API。

## 序列容器

### 内存布局（关键差异）

```
vector:  [elem0][elem1][elem2][elem3][_______][_______]
          begin                              end-of-storage
                     end (one past last)
         一块连续堆内存，三个指针管理

deque:   [map] -> [block0][block1][block2][block3]
                  [a][b][c]  [d][e][f]  [g][h][i]  ...
         指针数组（map）指向多个等大的连续块，元素不连续

list:    [prev|data|next] <-> [prev|data|next] <-> [prev|data|next]
         每个节点独立分配，双向指针连接

forward_list: [data|next] -> [data|next] -> [data|next] -> nullptr
         单向指针，省一个指针大小，没有 size()
```

### 操作复杂度

| 操作 | vector | deque | list | forward_list |
|------|--------|-------|------|--------------|
| 随机访问 `[]` | O(1) | O(1)* | O(n) | O(n) |
| 尾部插入 `push_back` | 摊销 O(1) | O(1) | O(1) | O(n) |
| 头部插入 `push_front` | O(n) | O(1) | O(1) | O(1) |
| 中间插入 | O(n) | O(n) | O(1)** | O(1)** |
| 缓存友好 | 最好 | 好 | 差 | 差 |
| 内存开销 | 最低 | 低-中 | 高（2 指针/节点） | 中（1 指针/节点） |

\* deque 的 O(1) 随机访问需要一次指针间接跳转，常数比 vector 大。
\** 前提是已有指向该位置的迭代器。

### vector 扩容策略

`push_back` 超出容量时：分配更大内存（GCC 2x，MSVC 1.5x）→ 移动/拷贝旧元素到新内存 → 释放旧内存。**移动构造不加 `noexcept`，扩容退化为拷贝**（见 [noexcept](noexcept.md)）。摊销分析：

$$\text{扩容因子 } k \text{ 时，每次 push\_back 摊销移动 } \frac{k}{k-1} \text{ 个元素}$$

1.5x 的好处：旧内存块更可能被新分配复用，减少碎片。

### 迭代器失效规则

| 操作 | vector | deque | list |
|------|--------|-------|------|
| `push_back` | 扩容时全部失效 | 全部失效 | 不失效 |
| `insert/erase` | 插入/删除点及之后全部失效 | 同左 | 仅被删节点失效 |

### 常用 API

```cpp
// ---- vector ----
v.push_back(x); v.emplace_back(args...); v.pop_back();
v[i]; v.at(i);          // at 检查越界
v.front(); v.back();
v.size(); v.empty(); v.clear();
v.reserve(n); v.capacity(); v.shrink_to_fit();
v.data();               // 底层数组指针，传给 C API
v.insert(pos, x); v.erase(pos); v.erase(first, last);

// ---- deque ----
// 比 vector 多了头部：push_front / emplace_front / pop_front
// 少了 data()、capacity()、reserve()

// ---- list ----
// 无 operator[]，但有自己的 sort/merge/splice/reverse/remove/unique

// ---- forward_list ----
// 只有头部操作，insert_after / erase_after / before_begin()

// ---- array ----
std::array<int, 5> a = {1,2,3,4,5};  // 编译期大小，无 push_back 等
a.fill(x);
```

## 有序关联容器 — set / map / multiset / multimap

底层都是红黑树（自平衡二叉搜索树），O(log n) 操作，元素按 key 排序。

### operator[] vs find —— 最核心的陷阱

```cpp
std::map<std::string, int> m;

int x = m["bob"];               // key 不存在 → 插入 {"bob", 0}，返回 0
m["alice"] = 30;                // 存在则赋值，不存在则先插默认值再赋值

// 只想查询不想插入 → 用 find
if (auto it = m.find("bob"); it != m.end()) {
    int x = it->second;         // 安全，不会意外插入
}
```

判断标准：**插入副作用是不是你想要的。** 读操作 → `find`（或 C++20 `contains`）；写/更新操作 → `operator[]`。

### Key 的要求

有序容器要求**严格弱序**：默认 `std::less<Key>` 调用 `operator<`。`a < b` 和 `b < a` 不能同时为 true。

```cpp
// 自定义类型需要 operator<
struct Point { int x, y; };
bool operator<(const Point& a, const Point& b) {
    return std::tie(a.x, a.y) < std::tie(b.x, b.y);
}
std::set<Point> s;  // OK

// 或传自定义比较器
auto cmp = [](const Point& a, const Point& b) { return a.x < b.x; };
std::set<Point, decltype(cmp)> s2(cmp);
```

注意：`double` 的 NaN 不满足严格弱序，不能直接当 key；裸指针默认比较地址而非内容。

### 常用 API

```cpp
s.insert(x);             // 返回 pair<iterator, bool>，key 已存在则插入失败
s.emplace(args...);
s.erase(key); s.erase(it);
s.find(key);             // 找不到返回 end()
s.contains(key);         // C++20
s.lower_bound(x);        // 第一个 >= x
s.upper_bound(x);        // 第一个 > x
s.equal_range(x);        // 等于 x 的区间 [lo, hi)

// multiset/multimap：count 可 > 1，erase(key) 删除所有等于 key 的元素
```

### 与 unordered_set / unordered_map 的对比

| | ordered (set/map) | unordered |
|--|-------------------|-----------|
| 底层 | 红黑树 | 哈希表 |
| 排序 | 有序 | 无序 |
| 查找 | O(log n) | O(1) 平均 |
| Key 要求 | `operator<`（严格弱序） | `std::hash` + `operator==` |
| 内存 | 较低 | 较高（桶+节点） |

已有关联笔记：[unordered_set](unordered-set.md)

## 容器适配器 — stack / queue / priority_queue

不是独立容器，在底层容器上限制接口。`pop()` **不返回元素**——原因是异常安全：如果返回值拷贝过程中抛异常，元素已从容器中删除，无法回滚。所以拆成两步：先 `top()`/`front()` 看一眼，再 `pop()`。

```cpp
// ---- stack（默认底层 deque）----
std::stack<int> s;
s.push(x); s.pop(); s.top(); s.empty(); s.size();

// ---- queue（默认底层 deque）----
std::queue<int> q;
q.push(x); q.pop(); q.front(); q.back(); q.empty(); q.size();

// ---- priority_queue（默认底层 vector，最大堆）----
std::priority_queue<int> pq;                              // 大的先出
std::priority_queue<int, std::vector<int>, std::greater<int>> min_pq; // 最小堆
pq.push(x); pq.pop(); pq.top(); pq.empty(); pq.size();
```

**priority_queue 比较器语义反转**：`std::greater` 得到最小堆。因为优先队列默认比较 `a < b` 意味着 a 优先级低于 b，最大值在顶；传 `greater`（即 `a > b`）反转后最小值在顶。

## 算法 + 迭代器

### 迭代器五级分类

```
Input --> Forward --> Bidirectional --> Random-Access
              Output（独立一支，只写）
```

| 类别 | 支持的操作 | 哪些容器 |
|------|-----------|---------|
| Input | `++`，`*`（只读一次） | 输入流迭代器 |
| Forward | `++`，`*`（可多次读） | forward_list |
| Bidirectional | `++`，`--` | list, set, map |
| Random-Access | `+n`，`[n]`，`<`，`>` | vector, deque, array, string |

这就是 `std::sort` 能用于 vector 但不能用于 list 的原因——`sort` 要求 Random-Access。

### 常用算法速查

```cpp
#include <algorithm>
#include <numeric>

// 不修改序列 — 传的是值，不是谓词
std::find(v.begin(), v.end(), val);
std::find_if(v.begin(), v.end(), pred);
std::count(v.begin(), v.end(), val);
std::count_if(v.begin(), v.end(), pred);
std::all_of / any_of / none_of(v.begin(), v.end(), pred);

// 修改序列
std::copy(src.begin(), src.end(), dst.begin());
std::transform(v.begin(), v.end(), out, [](int x) { return x * 2; });
std::replace(v.begin(), v.end(), old_val, new_val);
std::fill(v.begin(), v.end(), val);
std::reverse(v.begin(), v.end());

// 排序
std::sort(v.begin(), v.end());
std::sort(v.begin(), v.end(), std::greater{});
std::stable_sort(v.begin(), v.end());               // 保持等价元素相对顺序
std::partial_sort(v.begin(), v.begin()+5, v.end()); // 前 5 小排好
std::nth_element(v.begin(), v.begin()+5, v.end());  // 第 5 小到位，前后不排序
std::lower_bound(v.begin(), v.end(), val);          // 二分查找，要求有序

// 数值 <numeric>
int sum = std::accumulate(v.begin(), v.end(), 0);
```

### Erase-Remove Idiom

`std::remove` / `std::remove_if` **不改变容器大小**——只把不要的元素挪到末尾，返回新末尾迭代器。必须配合 `erase`：

```cpp
v.erase(std::remove_if(v.begin(), v.end(), pred), v.end());
```

### remove vs remove_if / find vs find_if

带 `_if` 后缀的接受**谓词**（lambda/函数），不带后缀的接受**值**：

```cpp
std::remove(v.begin(), v.end(), 5);                   // 删除值等于 5 的
std::remove_if(v.begin(), v.end(), [](int x) { ... }); // 删除满足条件的
std::find(v.begin(), v.end(), 5);                     // 找值等于 5 的
std::find_if(v.begin(), v.end(), [](int x) { ... });  // 找满足条件的
```

## Pair, Tuple & Structured Bindings

### pair

```cpp
auto p = std::make_pair(1, "hello");
p.first;  p.second;

// map 的元素就是 pair<const Key, T>
for (const auto& [key, value] : m) { /* C++17 结构化绑定 */ }
```

### tuple

```cpp
auto t = std::make_tuple(1, 3.14, "hello");
auto x = std::get<0>(t);              // 编译期索引

// 结构化绑定（C++17）
auto [a, b, c] = t;                   // 拷贝整个 tuple，a/b/c 是引用到临时变量
auto& [a, b, c] = t;                  // 零拷贝，a/b/c 直接引用 t 内部元素
const auto& [a, b, c] = t;            // 零拷贝，只读

// tie + ignore
int a; std::string s;
std::tie(a, std::ignore, s) = t;     // 跳过第二个元素
```

### decltype

`decltype(expr)` 是编译期运算符，获取表达式的静态类型而不执行。常用在需要写出 lambda 匿名类型的场景：

```cpp
auto cmp = [](int a, int b) { return a > b; };
// cmp 的类型是编译器生成的匿名类，无法手写 → 用 decltype 拿到
std::priority_queue<int, std::vector<int>, decltype(cmp)> pq(cmp);
```

纯编译期，零运行时开销。

### 结构化绑定的拷贝开销

`auto [a, b, c] = t` 会把 `t` 整体拷贝一份到隐藏临时变量，然后 a/b/c 绑定到临时变量的元素引用上——**整个 tuple 一份拷贝，每个元素不单独拷贝**。想避免开销就加 `&`：`auto& [a, b, c] = t`。

## 容器选型速记

| 需求 | 选什么 |
|------|--------|
| 动态数组，需要随机访问 | `vector`（默认首选） |
| 两端都要高效插入 | `deque` |
| 频繁在中间插入删除，迭代器不能失效 | `list` |
| 排序 + 去重 | `set` |
| key-value 映射，需要有序 | `map` |
| key-value 映射，追求速度，无需排序 | `unordered_map` |
| LIFO | `stack` |
| FIFO | `queue` |
| 优先出队 | `priority_queue` |
| 固定大小数组，STL 接口 | `array` |

## 直觉 / 类比

- **vector** 像一整排连续车位——查第 K 个车位 O(1)，但中间插一辆后面全得挪。车位满了得换更大的空地整体搬迁。
- **list** 像每辆车带着前后邻居的纸条——任意位置插入只改两张纸条，但没法直接跳到第 K 辆，得从头数。
- **map 的 operator[]** 像酒店前台——你说"把 Alice 房间的行李给我"，如果 Alice 没有房间，前台会**先给她开一间空房**再把行李给你。
- **Erase-Remove** 像搬家时把不要的家具推到墙角——房间大小没变，只是"有用的"区域缩小了，最后再叫搬家公司（erase）把墙角的东西清走。

## 常见误区

- **"list 插入 O(1) 所以比 vector 快"**：只看了大 O 忽略了缓存。遍历百万 int，vector 可能比 list 快 10-50 倍——连续内存让 CPU 预取极其高效。
- **"C++ map 就是 Python dict"**：Python dict 是哈希表（无序，O(1)），`std::map` 是红黑树（有序，O(log n)）。要 Python dict → 用 `std::unordered_map`。
- **用 `m[key]` 检查 key 是否存在**：`if (m["alice"] == 0)` 不仅慢，而且 key 不存在时会悄悄插入。用 `m.find(key) != m.end()` 或 C++20 的 `m.contains(key)`。
- **`std::remove` 之后容器大小就变了**：`remove` 不缩容器，必须接 `erase`。
- **priority_queue 的 `std::greater` 是最小堆**：语义反转——默认最大堆，传 `greater`（`a > b` 时 a 优先级低）得到最小堆。

## 关联

- [Move Semantics](move-semantics.md) — `push_back(T&&)` 调用移动构造，vector 扩容依赖 noexcept 保证
- [noexcept](noexcept.md) — 移动构造不加 noexcept 导致 vector 扩容退化为拷贝
- [Value Categories](value-categories.md) — 左值/右值决定 `push_back` 走拷贝还是移动重载
- [Perfect Forwarding](perfect-forwarding.md) — `emplace` 系列函数依赖完美转发原地构造，省一次移动/拷贝
- [unordered_set](unordered-set.md) — 无序关联容器的哈希表实现，和有序 set 构成选型岔路口
- [std::ranges::sort](ranges-sort.md) — C++20 ranges 版排序，投影和比较器分离；传统 `std::sort` 是算法库中最常用的接口
- [Range-Based For with auto&](range-based-for-reference.md) — 遍历容器时的 `auto`/`auto&`/`const auto&` 选择

## 面试常见问题

- **Q**: vector 的底层是什么？优缺点？
  **A**: 底层是动态数组（连续堆内存，三个指针管理 begin/end/end-of-storage）。优点：随机访问 O(1)，缓存友好，尾部插入摊销 O(1)。缺点：中间插入 O(n)，扩容时需要整体搬迁，迭代器在扩容时全部失效。
  *来源：小红书 · 攸宁 · 波克城市一面；小红书 · Andy · STL 八股文*

- **Q**: list 的底层是什么？优缺点？
  **A**: 底层是双向链表（每个节点独立分配，含 prev/data/next）。优点：任意位置插入删除 O(1)，迭代器不因其他节点操作而失效。缺点：随机访问 O(n)，缓存不友好（节点不连续），每节点额外存两个指针。
  *来源：小红书 · 攸宁 · 波克城市一面*

- **Q**: deque 的底层是什么？优缺点？
  **A**: 底层是分段连续数组——一个指针数组（map）指向多个等大的连续内存块。优点：头尾插入删除 O(1)，随机访问仍是 O(1)（多一次指针间接）。缺点：中间插入 O(n)，元素非连续存储（不能安全传给 C API），随机访问常数比 vector 大。
  *来源：小红书 · 攸宁 · 波克城市一面；小红书 · Andy · STL 八股文*

- **Q**: map 和 unordered_map 的区别？什么场景选哪个？
  **A**:  基于红黑树，key 有序，O(log n) 操作，内存较低； 基于哈希表，无序，O(1) 平均操作，内存较高。选型：需要有序遍历/范围查询（如排行榜按分数区间）→ map；只需要快速查找不需要排序（如缓存、词频统计）→ unordered_map。另外 map 的 key 只需要 operator<，unordered_map 的 key 需要 std::hash 和 operator==，自定义类型可能只为其中一个特化。
  *来源：小红书 · 攸宁 · 波克城市一面；小红书 · Andy · STL 八股文*

- **Q**: vector 扩容过程是怎样的？
  **A**: push_back 且 size() == capacity() 时触发扩容：分配一块更大的内存（GCC 2x，MSVC 1.5x）→ 将旧元素移动（或拷贝，如果移动构造非 noexcept）到新内存 → 析构旧元素并释放旧内存。摊销后每次 push_back 仍为 O(1)。扩容因子 1.5x 的好处是旧内存块更可能被新分配复用。
  *来源：小红书 · Andy · STL 八股文*

- **Q**: sort 是稳定的吗？底层是什么？
  **A**: std::sort 是非稳定排序（相等元素的相对顺序可能改变）。底层是 Introsort（内省排序）——先用快速排序，递归深度超过阈值时切换为堆排序（避免快排最坏 O(n^2)），子数组小于阈值时切换为插入排序（小数组上常数更优）。时间复杂度 O(n log n)。需要稳定排序用 std::stable_sort。
  *来源：小红书 · Andy · STL 八股文*

- **Q**: 利用迭代器删除元素时，哪些容器的迭代器会失效？
  **A**: vector：删除点及之后的所有迭代器失效（后续元素往前移动，地址变了）。deque：删除点及之后的所有迭代器失效（头尾删除除外，仅被删元素迭代器失效）。list/forward_list：仅被删除节点的迭代器失效，其他不受影响。set/map 等关联容器：仅被删除节点的迭代器失效。所以遍历删除时，vector 需要用返回的新迭代器（it = v.erase(it)），list 可用 it = l.erase(it) 或后置变种。
  *来源：小红书 · Andy · STL 八股文；牛客 · 爱打球的程小员许乔丹 · 嵌入式面经*

- **Q**: 为什么 list 有自己的 sort 成员函数，不能用 std::sort？
  **A**: std::sort 要求 Random-Access 迭代器（支持 it + n、it[n]），list 只提供 Bidirectional 迭代器（仅支持 ++/--），编译期就无法通过。list 的成员 sort() 利用链表特性实现归并排序，同样 O(n log n)，且只用指针重连不移动元素。
  *来源：牛客 · 爱打球的程小员许乔丹 · 嵌入式面经*

- **Q**: std::remove 真的删除了元素吗？
  **A**: 没有。std::remove / std::remove_if 只是把不删除的元素往前覆盖、返回新末尾迭代器，容器大小不变。必须配合 erase 才能真正删除：v.erase(std::remove_if(v.begin(), v.end(), pred), v.end())——这就是 Erase-Remove Idiom。该设计的原因是 remove 只操作迭代器区间，不知道底层容器的具体实现。
  *来源：牛客 · 爱打球的程小员许乔丹 · 嵌入式面经*
