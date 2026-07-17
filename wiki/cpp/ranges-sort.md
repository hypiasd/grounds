---
title: std::ranges::sort
topic: cpp
tags: [algorithm, cpp20, ranges, sorting, comparator, projection]
summary: C++20 的 ranges::sort 直接接受容器，支持投影（projection）和自定义比较器（comparator），把"比什么"和"怎么比"拆成两个独立参数。四种投影形式覆盖 lambda、成员指针、成员函数和自由函数；三种比较器形式覆盖默认、标准函数对象和自定义 lambda。
created: 2026-07-14
updated: 2026-07-17
---


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


### Comparator（比较器）

比较器是 `ranges::sort` 的第二个参数，回答"a 应该排在 b 前面吗？"这个问题。签名：

```cpp
ranges::sort(range, comparator, projection);
//                  ^^^^^^^^^^
```

**形式一：默认比较器 `{}`**

`{}` 值初始化出一个 `std::ranges::less`，内部就是 `a < b`（升序）。传 `{}` 的唯一场景是：不需要自定义比较逻辑，但第三个参数投影必须传，所以用 `{}` 占位。

```cpp
ranges::sort(v, {});           // 等价于 ranges::sort(v)
ranges::sort(v, {}, &proj);    // 带投影的默认升序
```

**形式二：标准函数对象**

```cpp
ranges::sort(v, std::greater{});   // 降序
ranges::sort(v, std::less{});      // 升序，等价于 {}，显式写出来而已
```

`std::greater{}` 和 `std::less{}` 是函数对象（functor），空类、零开销、编译器可整段内联。

**形式三：自定义 lambda**

```cpp
// 按绝对值升序
ranges::sort(v, [](int a, int b) { return abs(a) < abs(b); });

// 多级排序：先按左端点升序，相同则右端点降序
ranges::sort(intervals, [](const auto& a, const auto& b) {
    if (a[0] != b[0]) return a[0] < b[0];   // 第一优先级
    return a[1] > b[1];                       // 第二优先级
});
```

多级排序用 if-return 链：先比第一优先级，不等就出结果；相等再比第二优先级。

**比较器的铁律：严格弱序（strict weak ordering）**

| 规则 | 含义 | 违反后果 |
|------|------|----------|
| 非自反 | `comp(x, x)` 必须为 false | sort 死循环或越界 |
| 非对称 | 若 `comp(a, b)` 为 true，则 `comp(b, a)` 必为 false | 排序结果不确定 |
| 传递 | 若 `comp(a, b)` 且 `comp(b, c)`，则 `comp(a, c)` | 排序结果不一致 |

最常见的违规是用 `<=` 当比较器——`comp(x, x)` 为 true，不满足非自反。

```cpp
// 错误！
ranges::sort(v, [](int a, int b) { return a <= b; });
```

### Projection（投影）

投影是 `ranges::sort` 的第三个参数，回答"比之前，把元素变成什么？"。sort 内部每次比较 `a` 和 `b` 时，实际执行 `comp(proj(a), proj(b))`。元素本身不被修改——投影只是比较时的临时映射。

**形式一：lambda 投影（最灵活）**

```cpp
vector<vector<int>> intervals = {{1,3}, {8,10}, {2,6}, {15,18}};

// 按左端点升序
ranges::sort(intervals, {}, [](const auto& a) { return a[0]; });

// 按区间长度升序
ranges::sort(intervals, {}, [](const auto& a) { return a[1] - a[0]; });

// 投影返回 pair，利用字典序实现多级排序（全部升序）
ranges::sort(intervals, {}, [](const auto& a) {
    return pair{a[0], a[1]};  // 先左端点，再右端点，全部升序
});
```

注意 lambda 参数用 `const auto&` 而非 `auto`：避免拷贝每个元素（对 `vector<int>` 这很重要），且 const 表达了"投影不该修改元素"的意图。

**形式二：成员指针（最简洁）**

```cpp
struct Person { string name; int age; };
vector<Person> people = {{"Alice",30}, {"Bob",25}};

ranges::sort(people, {}, &Person::age);
// 结果：Bob(25), Alice(30)
```

`&Person::age` 的类型是 `int Person::*`（指向成员的指针），ranges 内部对元素 `p` 调用 `p.*pm`，等价于 `p.age`。

**形式三：成员函数**

```cpp
vector<string> words = {"hello", "a", "world", "ab"};

ranges::sort(words, {}, &std::string::size);
// 结果：{"a", "ab", "hello", "world"}
```

`&std::string::size` 是成员函数指针。ranges 内部对元素 `s` 调用 `(s.*pmf)()`，等价于 `s.size()`。任何无参 const 成员函数都可以用。

**形式四：自由函数 / 函数指针**

```cpp
ranges::sort(v, {}, abs);  // 按绝对值排序，abs 是 <cstdlib> 的自由函数
```

### 投影 vs 比较器：何时用哪个

投影只能映射每个元素到**单个值**——这是它和比较器之间最根本的边界。任何需要同时取两个元素的不同字段来比较的场景，投影做不到。

| 场景 | 用投影 | 用比较器 |
|------|--------|----------|
| 按元素自身属性排（年龄、首元素、绝对值） | ✅ | 可以，但投影更清晰 |
| 多级全升序（先 A 再 B） | ✅ 投影返回 `pair`/`tuple` | ✅ if-return 链 |
| 多级混方向（先 A 升序，再 B 降序） | ❌ 符号翻转 hack 仅适用数值 | ✅ |
| 比的逻辑依赖两个元素的**关系**或**不同字段** | ❌ | ✅ |

投影无法表达的典型例子——按"a 的右端点 < b 的左端点"排序：

```cpp
// 必须用比较器：比较逻辑涉及 a[1] 和 b[0]——两个元素的不同字段
ranges::sort(intervals, [](const auto& a, const auto& b) {
    if (a[1] < b[0]) return true;   // a 完全在 b 左边
    return a[0] < b[0];             // 否则按左端点
});
```

关于符号翻转 hack：`pair{a[0], -a[1]}` 用取负实现"按右端点降序"，这对 `int` 有效（`-y < -x` 等价于 `x < y`），但换成 `string` 就编译失败——`string` 没有一元 `-` 运算符。多级排序混了不同方向时，比较器是通用方案。

### 子区间排序

`ranges::sort` 同时接受 range 和 iterator-sentinel 对——后者的两参数重载仍存在，用于只排容器的局部：

```cpp
vector<int> v = {5, 1, 4, 2, 3, 8, 6};

ranges::sort(v.begin() + 1, v.begin() + 5);
// 只排 v[1..5)，v → {5, 1, 2, 3, 4, 8, 6}
```

也可以用 views 切子区间，但不如迭代器对直接：

```cpp
ranges::sort(v | views::drop(1) | views::take(4));  // 效果相同，更啰嗦
```

## 直觉 / 类比

`std::sort` 像叫外卖时必须报"从第三个货架到第七个货架"——你得知道仓库内部布局。`std::ranges::sort` 像直接说"把这箱东西排好"——仓库布局是库的事，你只关心结果。
投影则是"只看每件商品的价格标签来排"——你不需要把商品换成标签，只需要临时看一眼。

## 常见误区

- **误区一：以为 sort 被移到了 ranges 里，`std::sort` 不能用了**——`std::sort` 仍然存在且正常工作。ranges 是新增的封装层，不是替代。
- **误区二：写 `ranges::sort` 不写 `std::` 前缀也能编过**——必须有人帮你导入了命名空间（`using namespace std::ranges;`），否则会报找不到。在 LeetCode 环境之外写代码时记得补全。
- **误区三：以为 ranges 只是省几个字**——投影（projection）能力是 `std::sort` 没有的，`std::ranges::sort(v, {}, &Person::age)` 不需要手写比较器。

- **误区四：用 `<=` 当比较器**——`[](int a,int b){return a<=b;}` 编译过但运行时行为未定义。`<=` 不满足严格弱序的非自反性（`comp(x,x)` 为 true），会导致排序死循环或越界。比较器必须是严格小于 `<` 或严格大于 `>`，永远不带等号。

- **误区五：投影里写副作用**——投影在排序期间被调用 O(n log n) 次（取决于比较次数），且调用次数和顺序是未指定的。不要在投影里做计数、日志、修改等有副作用的操作。

- **误区六：`-a[1]` 符号翻转取巧降序**——`pair{a[0], -a[1]}` 只在数值类型上碰巧工作。`-INT_MIN` 是有符号溢出（未定义行为），且对 `string` 等没有 `-` 运算符的类型完全无效。多级排序混方向时，直接用比较器的 if-return 链是通用方案。

- **误区七：试图链式成员指针**——`&X::y::z` 编译不过，C++ 成员指针不支持链式访问。嵌套字段的投影用 lambda：`[](const auto& x) { return x.y.z; }`。

- **误区八：投影 lambda 按值捕获导致多余拷贝**——`[](auto a){return a[0];}` 每次调用拷贝整个 `vector<int>`。投影不应修改元素，用 `const auto&`：`[](const auto& a){return a[0];}`。

## 面试常见问题

- **Q: `std::sort` 和 `std::ranges::sort` 的核心区别？**
  **A**: `std::sort` 接受迭代器对 `(begin, end)`，`std::ranges::sort` 直接接受 range（容器或迭代器对均可）。ranges 版多了投影（projection）能力，把"取什么字段"和"怎么比"拆成两个独立参数——例如 `ranges::sort(v, {}, &Person::age)` 按 age 升序，无需手写比较器。

- **Q: 为什么说 `std::ranges::sort` 比 `std::sort` 更安全？**
  **A**: `std::sort(v.begin(), w.end())` 传了两个不同容器的迭代器，编译器不报错但运行时是未定义行为。`std::ranges::sort(v)` 整个 range 内部自动配对 begin/end，这种错误不可能发生。

- **Q: `ranges::sort` 的比较器必须满足什么条件？**
  **A**: 严格弱序（strict weak ordering）——非自反（`comp(x,x)` 必须 false）、非对称（`comp(a,b)` 则 `!comp(b,a)`）、传递。常见陷阱是用 `<=` 当比较器，违反非自反导致未定义行为。

- **Q: projection 和 comparator 什么时候该用哪个？**
  **A**: 按单个字段排序 → 投影更清晰（`ranges::sort(v, {}, &X::field)`）。多级排序有不同方向 → 比较器的 if-return 链（投影的符号翻转 hack 仅限数值）。比较逻辑涉及两个元素的不同字段 → 只能用比较器。

- **Q: 如何用 `ranges::sort` 只排容器的局部？**
  **A**: 传迭代器对：`ranges::sort(v.begin() + k, v.begin() + m)` 只排 `v[k..m)`。也可以用 views（`views::drop(k) | views::take(n)`），但迭代器对更简洁。

- **Q: C++20 ranges 除了 sort 还有哪些常用算法？**
  **A**: 几乎所有 `<algorithm>` 的算法都有对应的 ranges 版本：`std::ranges::find`、`std::ranges::copy`、`std::ranges::transform`、`std::ranges::for_each` 等。它们统一接受 range 而非迭代器对，并支持投影。

## 关联

- [Range-Based For with auto&](range-based-for-reference.md) — 同样是 C++ 现代特性，让循环和算法调用更简洁
