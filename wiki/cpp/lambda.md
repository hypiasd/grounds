---
title: Lambda
topic: cpp
tags: [lambda, closure, functional-programming, cpp11, cpp14, stl, capture, generic-lambda]
summary: lambda 是创建匿名函数对象的语法糖——编译器生成匿名类加 operator()，捕获列表里的变量变成类的成员。闭包类型匿名必须用 auto 存储，operator() 默认 const 需 mutable 才能改捕获副本。C++14 泛型 lambda 的 auto 参数本质是模板。std::function 通过类型擦除统一接口但付出虚函数调用和堆分配代价。
created: 2026-07-19
updated: 2026-07-19
---

## TL;DR

lambda 是创建匿名函数对象（闭包）的语法糖。你写 `[capture](params) { body }`，编译器生成一个匿名类，捕获变量变成成员，函数体变成 `operator()`。和手写仿函数相比，lambda 把逻辑写在使用处——就地表达，不需要跳转到文件别处看定义。

六个核心要点：捕获列表 vs 参数列表是两回事、捕获发生在构造时不是调用时、闭包类型匿名只能用 auto 存、`operator()` 默认 const 需 `mutable`、`std::function` 的类型擦除有代价、C++14 泛型 lambda 的 `auto` 参数是模板的语法糖。

## 核心概念

### 1. 基础语法

完整解剖：

```cpp
[capture](params) mutable noexcept -> return_type { body }
//  ↑        ↑       ↑        ↑          ↑           ↑
//  捕获    参数   允许修改   不抛异常   显式返回类型   函数体
```

最简形式 `[]{}` 合法——无捕获、无参数、无返回、空函数体。各部分省略规则：

| 部分 | 何时可省 | 示例 |
|------|---------|------|
| 捕获列表 | 永远不能省（至少写 `[]`） | — |
| 参数列表 | 无参数时 | `[]{ return 42; }` |
| `mutable` | 不需要修改按值捕获的变量时 | 省 |
| `-> 返回类型` | 能被推导或返回 void 时 | `[](int x) { return x * 2; }` |
| 函数体 | 永远不能省 | — |

**捕获 vs 参数的分界线**：捕获是 lambda 构造时从外面抓进去的东西，参数是每次调用时传进来的东西。捕获只发生一次，参数每次调用都发生。

```cpp
int threshold = 10;
auto lam = [threshold](int x) { return x > threshold; };
//           ↑捕获（一次）  ↑参数（每次调用）
```

**无捕获 lambda 才可转函数指针**：

```cpp
auto lam = [](int x) { return x * 2; };
int (*fp)(int) = lam;              // ✅ 无捕获可隐式转换

int n = 10;
auto lam2 = [n](int x) { return x * n; };
int (*fp2)(int) = lam2;            // ❌ 有捕获不能转函数指针
```

### 2. 捕获语义

**捕获发生在构造时，不是调用时。** 按值捕获是拍一张照片放进去——之后外面原件怎么变都不影响闭包内的副本；按引用捕获是放一个对讲机——始终指向原变量。

```cpp
int x = 10;
auto by_val = [x] { return x; };   // 拍照——拷贝当时 x=10
auto by_ref = [&x] { return x; };  // 对讲机——始终指向原 x

x = 20;
by_val();  // 10 —— 照片不变
by_ref();  // 20 —— 对讲机那头是当前值
```

**默认捕获：**

```cpp
int a = 1, b = 2, c = 3;
[=] { return a + b + c; };       // 全按值
[&] { a++; b++; c++; };          // 全按引用
[=, &c] { return a + b + c; };   // 默认按值，c 按引用
[&, a] { return a + b + c; };    // 默认按引用，a 按值
```

**`mutable`：** 去掉 `operator()` 的 const 限定，让按值捕获的副本在闭包内部可修改——改的是副本，不影响外部变量。

```cpp
int x = 0;
auto lam = [x]() mutable { return ++x; };
lam(); lam(); lam();  // 1, 2, 3
// 外部 x 仍然是 0
```

**`this` 捕获：** `[this]` 按指针捕获当前对象。对象销毁后 lambda 的 `this` 失效——异步回调的经典陷阱。C++17 `[*this]` 把整个对象拷贝一份进闭包，彻底安全。

**C++14 初始化捕获（init capture）：** 捕获时可以执行任意表达式。

```cpp
auto p = std::make_unique<int>(42);
auto lam = [p = std::move(p)] { return *p; };  // unique_ptr 移进闭包
// 外层 p 被移空，内层 p 是闭包里的 unique_ptr

auto lam2 = [upper = std::toupper('a')] { return upper; };  // 'A'
```

**按引用捕获的经典陷阱——for 循环 + `[&]`：**

```cpp
std::vector<std::function<int()>> funcs;
for (int i = 0; i < 5; i++) {
    funcs.push_back([&i] { return i; });  // 💥 i 出循环即销毁，悬垂引用
}
// 修复：按值捕获 [i] 或初始化捕获 [j = i]
```

### 3. 闭包类型与调用

每个 lambda 表达式的类型是**编译器生成的全局唯一匿名类**——即使两个 lambda 函数体一模一样，类型也不同。这意味着只能用 `auto`、模板参数、或 `std::function` 来存储 lambda。

**`operator()` 默认 const：** 不加 `mutable` 的 lambda，其 `operator()` 是 const 成员函数，不能修改捕获的成员变量。`mutable` 去掉了这个 const 限定——改的是闭包内部副本，外部不受影响。

**lambda 是对象，可拷贝可移动：**

```cpp
auto lam = [v = std::vector<int>{1,2,3}] { return v.size(); };
auto lam2 = lam;           // 拷贝构造
auto lam3 = std::move(lam); // 移动构造——lam 变空壳
```

捕获了 `unique_ptr` 的 lambda 只能移动不能拷贝。

**`std::function` 的类型擦除代价：** `std::function` 内部用虚函数实现类型擦除——能装任何满足签名的可调用物，代价是每次调用走虚表跳转，编译器无法内联。对于 STL 算法热路径（如 `std::sort`），直接传 lambda（模板实例化、零开销内联）vs 转成 `std::function` 再传——排序可能慢 3-10 倍。

原则：默认用 `auto` 存 lambda，只在必须类型擦除（存到容器、跨编译单元传递）时才转 `std::function`。

### 4. 泛型 lambda（C++14）

`auto` 参数本质是模板——编译器生成模板化的 `operator()`。

```cpp
auto add = [](auto a, auto b) { return a + b; };
// 等价于：
struct __anonymous {
    template<typename T, typename U>
    auto operator()(T a, U b) const { return a + b; }
};

add(1, 2);      // T=int, U=int
add(1.5, 2);    // T=double, U=int
```

每个 `auto` 参数是**独立**的模板参数——`auto a, auto b` 不是同类型约束，a 和 b 可以不同类型。想要求同类型需 C++20 concept 约束。

**`auto&&` 参数 = 转发引用：**

```cpp
auto forwarder = [](auto&& x) {
    return std::forward<decltype(x)>(x);
};
// 等价于 template<typename T> decltype(auto) operator()(T&& x) const
```

**变参泛型 lambda：**

```cpp
auto printer = [](auto&&... args) {
    (std::cout << ... << args);  // C++17 fold expression
};
```

**C++20 进一步提升：** 可以在 lambda 中写显式模板参数，拿到类型名做类型运算。

```cpp
auto add_vec = []<typename T>(std::vector<T> const& a, std::vector<T> const& b) {
    using value_type = T;  // C++14 泛型 lambda 做不到——拿不到 T 的名字
    // ...
};
```

### 5. lambda 与 STL 算法

lambda 是 STL 算法的标配搭档——就地表达判断逻辑，零开销内联。

```cpp
std::vector<int> v = {3, 1, 4, 1, 5};

// 排序——自定义比较器
std::sort(v.begin(), v.end(), [](int a, int b) { return a > b; });

// 查找——自定义条件
auto it = std::find_if(v.begin(), v.end(), [](int x) { return x > 3 && x % 2 == 0; });

// 变换——生成新容器
std::transform(v.begin(), v.end(), v.begin(), [](int x) { return x * 2; });

// 遍历——修改原数据（注意 int&）
std::for_each(v.begin(), v.end(), [](int& x) { x *= 2; });

// C++20 一步到位删除
std::erase_if(v, [](int x) { return x < 0; });

// 带捕获——外部阈值驱动
int threshold = 10;
auto it2 = std::find_if(v.begin(), v.end(), [threshold](int x) { return x > threshold; });
int count = std::count_if(v.begin(), v.end(), [threshold](int x) { return x > threshold; });
```

lambda vs 传统方式：函数指针（无法内联、不能捕获状态）、仿函数（可内联但样板代码冗长）、lambda（可内联 + 就地定义 + 可捕获）——唯一同时满足三者的方案。

## 直觉 / 类比

lambda 是一次性的函数小便签——和普通函数一样有参数、有返回、有函数体，只是没有名字，贴在用的地方就行。捕获是打包行李：lambda 出生时把外面需要的变量塞进背包。按值捕获是拍一张照片放进去，按引用捕获是放一个对讲机。

为什么需要它？C++98 时想给 `std::sort` 传自定义比较规则，得在文件别处写一个完整的仿函数类——起名、写 `operator()`，再回到调用处传进去。lambda 让你把"怎么比"写在调用 `sort` 的地方，一行搞定。

## 常见误区

- **误区一：混淆捕获列表和参数列表** —— `[a, b]{}` 是从外部抓 a、b，`[](int a, int b){}` 是调用时传入 a、b。捕获是构造时一次性的，参数是每次调用传入的。
- **误区二：`[=]` 就是安全的** —— `[=]` 拷贝了指针值，没拷贝指向的对象。多个 lambda 共享同一个指针指向的资源，可能 double free。
- **误区三：以为 `mutable` 能影响外部变量** —— `mutable` 只去掉 operator() 的 const，改的是闭包内部副本，外部变量纹丝不动。
- **误区四：拿 `std::function` 存所有 lambda** —— 多了一次堆分配加虚函数调用，STL 算法热路径上直接用 lambda 快 3-10 倍。
- **误区五：按引用捕获的 lambda 逃逸出作用域** —— lambda 作为返回值或存到容器、抛到另一个线程时，捕获的局部变量引用变成悬垂引用。典型场景：for 循环里 `[&i]` 塞进 function vector。
- **误区六：`this` 悬垂** —— 对象销毁后 lambda 的 `this` 失效，但 lambda 可能还在异步回调队列里。C++17 `[*this]` 是解法：拷贝整个对象进闭包。

## 关联

- [Templates](templates.md) — 泛型 lambda 的 `auto` 参数本质是模板参数，理解模板后泛型 lambda 就是语法糖
- [Move Semantics](move-semantics.md) — C++14 初始化捕获 `[p = std::move(p)]` 依赖移动语义将不可拷贝对象转移进闭包
- [STL](stl.md) — lambda 是 STL 算法的标配搭档，sort/find_if/transform/erase_if 全用 lambda 就地表达判断逻辑
- [Value Categories](value-categories.md) — 理解 `auto&&` 参数（转发引用）需要值类别基础
- [auto / decltype](auto-decltype.md) — lambda 闭包类型匿名 → 必须用 auto 存储；泛型 lambda 的 auto 参数是模板推导

## 面试常见问题

- **Q**: 什么是 Lambda 表达式？底层实现原理是什么？
  **A**: Lambda 是 C++11 引入的匿名函数对象语法糖。编译器为每个 lambda 表达式生成一个唯一的匿名类，捕获列表里的变量变成该类的成员变量，函数体变成 `operator()` 的实现。因此 lambda 本质是一个**带状态的小对象**，不是函数指针。无捕获的 lambda 可隐式转换为函数指针，有捕获的则不能。
  *来源：知乎 • 竹一 • https://zhuanlan.zhihu.com/p/2049981388129035327*

- **Q**: 捕获方式有哪些？`[=]` 和 `[&]` 怎么选？
  **A**: 捕获分按值（`[x]`、`[=]`）和按引用（`[&x]`、`[&]`）两大类，外加 C++14 初始化捕获 `[name = expr]`。选择原则：默认按值更安全——适用于返回 lambda、异步回调、存到容器等 lambda 生命周期超过被捕获变量的场景。需要修改外部变量、或变量本身不可拷贝时才用按引用。面试标准答法：「默认 `[=]` 更安全，需要改外部才用 `[&]`；返回或异步一定要用按值。」
  *来源：知乎 • 竹一 • https://zhuanlan.zhihu.com/p/2049981388129035327；知乎 • 卓木子 • https://zhuanlan.zhihu.com/p/2039252121191698493*

- **Q**: mutable 关键字的作用是什么？
  **A**: 按值捕获的变量在 lambda 内部默认是 const 的（因为 `operator()` 是 const 成员函数），不能修改。加 `mutable` 去掉 `operator()` 的 const 限定，允许修改按值捕获的副本——但改的是闭包内部的副本，不影响外部原变量。记忆法：「复印的稿子改了，原稿不会变。」如果确实要改外部变量，用按引用捕获 `[&n]`。
  *来源：知乎 • 卓木子 • https://zhuanlan.zhihu.com/p/2039252121191698493；牛客 • daemon_007 • https://www.nowcoder.com/discuss/*

- **Q**: 为什么 Lambda 会崩？最常见的三个坑是什么？
  **A**: (1) **返回按引用捕获的 lambda**——被捕获的局部变量在函数返回后销毁，lambda 持有悬垂引用。修复：按值捕获 `[=]` 或 `[x=a]`。(2) **异步 + `[&]`**——线程 `detach()` 后主线程先退出，lambda 里捕获的局部变量没了。修复：异步场景用按值或 `shared_ptr`。(3) **`mutable` 以为能改外部变量**——只改了闭包内部副本。修复：需要改外部用 `[&n]`。
  *来源：知乎 • 卓木子 • https://zhuanlan.zhihu.com/p/2039252121191698493*

- **Q**: Lambda 和仿函数（函数对象）有什么区别？什么时候用哪个？
  **A**: Lambda 是仿函数的语法糖——编译器为 lambda 生成的匿名类本质上就是仿函数。区别在于写法：lambda 就地定义、代码在使用处，适合简短的回调和 STL 算法参数；仿函数需要单独定义类、有名字、可复用、可继承。性能上两者等价（都走模板实例化零开销内联）。实际中优先用 lambda，只有需要多次复用同一逻辑、或逻辑复杂到需要多个成员函数时才写仿函数类。
  *来源：知乎 • 竹一 • https://zhuanlan.zhihu.com/p/2049981388129035327；牛客 • daemon_007 • https://www.nowcoder.com/discuss/*

- **Q**: 泛型 lambda（C++14）是什么？和普通模板函数有什么区别？
  **A**: 泛型 lambda 用 `auto` 作为参数类型——`[](auto a, auto b) { return a + b; }`，编译器生成模板化的 `operator()`。每个 `auto` 参数是独立的模板参数（`auto a, auto b` 可以是不同类型，不像 `template<typename T> void f(T, T)` 要求同类型）。C++20 进一步支持显式模板语法 `[]<typename T>(T a, T b) {}` 和 concept 约束。和普通模板函数的区别：泛型 lambda 是匿名函数对象，可捕获外部变量；普通模板函数不能捕获。
  *来源：知乎 • 竹一 • https://zhuanlan.zhihu.com/p/2049981388129035327*

- **Q**: `std::function` 和 `auto` 存 lambda 有什么区别？
  **A**: `auto` 存 lambda 保留编译器生成的唯一类型——零开销、可内联、无额外内存分配。`std::function` 通过类型擦除统一接口（内部用虚函数），能装任何满足签名的可调用物——代价是每次调用走虚表跳转（编译器无法内联）+ 可能堆分配。STL 算法热路径上直接用 lambda 比转成 `std::function` 快 3-10 倍。原则：默认用 `auto`，只在必须类型擦除时（存到容器、跨编译单元 API）才转 `std::function`。
