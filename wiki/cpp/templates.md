---
title: Templates
topic: cpp
tags: [templates, generic-programming, compile-time, sfinae, concepts, variadic-templates, type-traits, template-specialization, nttp, ctad]
summary: C++ 模板是编译期泛型编程机制——函数/类模板通过参数推导在实例化时生成具体代码，运行时零开销。涵盖基础机制（实例化、两阶段编译、依赖名）、特化（全特化/偏特化模式匹配）、变参模板（参数包递归展开）、SFINAE/Type Traits/Concepts（约束与类型操纵的演化线）、非类型模板参数与编译期计算、CTAD。
created: 2026-07-18
updated: 2026-07-20
---

## TL;DR

模板是 C++ 的编译期泛型机制——一份代码适配所有类型，编译器在实例化时根据具体类型参数自动生成专属版本，运行时零开销。类比：模板是菜谱，类型参数是食材，编译器是厨师——一份"炒 X"的菜谱，传牛肉或豆腐进去自动变成对应的菜。

模板贯穿整个 C++ 类型系统：STL 容器是类模板、`std::move` 和 `std::forward` 依赖模板参数推导、C++20 ranges 的投影靠 concept 约束。理解模板是理解现代 C++ 的前提。

八个核心方向：基础机制 → 两阶段编译/依赖名 → 特化 → 变参模板 → SFINAE/Type Traits → Concepts → 非类型模板参数 → CTAD。

## 核心概念

### 1. 基础模板机制

**函数模板**——最简单的入口：

```cpp
template<typename T>
T max(T a, T b) {
    return a > b ? a : b;
}
```

`typename` 和 `class` 在模板参数声明中等价。编译器看到 `max(3, 5)` 时推导 `T = int`，生成 `int max(int, int)` 实例。这个过程叫**实例化（instantiation）**——调用前 `max<int>` 不存在。

**类模板**——容器的基础：

```cpp
template<typename T>
class Box {
    T value;
public:
    Box(T v) : value(v) {}
    T get() const { return value; }
};
```

`Box` 不是类型——`Box<int>` 才是。只有尖括号填上参数后，模板才变成一个真正的类。

**模板实参推导（TAD）**：编译器拿实参类型匹配形参声明中的 T，取一个能让所有 T 位置一致的解。关键规则：**推导阶段不触发隐式类型转换**——`max(3, 4.0)` 报错（T 不能同时是 int 和 double），必须显式指定 `max<double>(3, 4.0)`。

**为什么模板定义必须在头文件中**：模板不是代码，是蓝图。`max<int>` 在被调用前不存在于世界上任何地方——编译 `max.cpp` 时如果没有人用 `int` 调用它，编译器不生成任何机器码。当 `main.cpp` 调用 `max(3,5)` 时，编译器需要蓝图现场生成 `max<int>`——如果只 `#include` 了声明没有实现体，编译器拿不到蓝图，生成失败，链接时报 `undefined reference`。

更深层的根因在 [编译模型](compilation-model.md)：C++ 每个翻译单元独立编译、编译器只看得见自己 TU 内的定义，模板实例化发生在「用到它的那个 TU」，定义必须在现场可见；同时靠 ODR 规则 3 例外让多个 TU 的同款实例合法合并——这正是 `inline` 和模板能安全放在头文件的底层机制。

对比普通函数：普通函数在编译实现文件时就已经生成机器码，链接器直接找地址即可。

### 2. 两阶段编译与依赖名

编译器读模板代码时**检查两遍**：

- **第一阶段（定义时）**：检查非依赖名——语法错误、括号不匹配、不存在的全局名字，这阶段就报错。即使模板从未实例化。
- **第二阶段（实例化时）**：检查依赖名——`T::value`、`x.someMethod()` 等依赖模板参数的东西，拿到具体类型后才检查。

**依赖名 vs 非依赖名**：

```cpp
template<typename T>
void foo(T x) {
    int a = 42;        // 非依赖名：和 T 完全无关
    T b = x;           // 依赖名
    x.someMethod();    // 依赖名
}
```

**`typename` 关键字（第二用途）**：当依赖名是类型时，编译器默认不知道——必须显式声明：

```cpp
template<typename T>
void foo() {
    T::value_type x;           // ❌ 编译错误
    typename T::value_type x;  // ✅ 告诉编译器 value_type 是类型
}
```

同理，当依赖名是模板时用 `template` 关键字：`x.template bar<int>()`。

最常踩的坑：`std::vector<T>::const_iterator` 必须加 `typename`。

### 3. 模板特化

**全特化**——针对某个具体类型完全替换实现。`template<>` 表示不再泛型：

```cpp
template<typename T>
struct TypeInfo { static const char* name() { return "unknown"; } };

template<>  // 全特化：尖括号为空
struct TypeInfo<int> { static const char* name() { return "int"; } };
```

函数模板的全特化几乎不用——函数重载更直观且行为更可预测。

**偏特化**——不写死具体类型，而是写死一个**模式**。只适用于类模板：

```cpp
// is_pointer 实现：主模板默认 false，偏特化匹配指针模式返回 true
template<typename T> struct is_pointer { static constexpr bool value = false; };
template<typename T> struct is_pointer<T*> { static constexpr bool value = true; };

// remove_const 实现
template<typename T> struct remove_const { using type = T; };
template<typename T> struct remove_const<const T> { using type = T; };

// is_same 实现——偏特化版本比主模板少一个参数，但占两个位置
template<typename T, typename U> struct is_same { static constexpr bool value = false; };
template<typename T> struct is_same<T, T> { static constexpr bool value = true; };
```

`is_same<T, T>` 的关键：偏特化用同一个 T 填两个位置——"两个类型相同时才匹配"。编译器遇到 `is_same<int, int>` 时两个位置对得上 → 命中偏特化；`is_same<int, double>` 对不上 → 回退主模板。

**匹配规则**：多个特化都匹配时选最特化（最挑剔）的那个。`const T*` 比 `T*` 更挑剔 → 冲突时前者胜出。

### 4. 变参模板

接受任意数量的模板参数。核心机制：参数包 + 递归解包。

```cpp
// 终止：没有参数了
void print() { std::cout << std::endl; }

// 递归：取第一个，剩下的展开传下去
template<typename T, typename... Rest>
void print(T first, Rest... rest) {
    std::cout << first << " ";
    print(rest...);  // rest... 将参数包展开为逗号分隔的列表
}
```

调用 `print(1, 2.5, "hi")` 的展开过程：

```
print(1, 2.5, "hi")
  → first=1, rest={2.5, "hi"} → 打印 1，递归 print(2.5, "hi")
    → first=2.5, rest={"hi"}  → 打印 2.5，递归 print("hi")
      → first="hi", rest={}    → 打印 "hi"，递归 print()
        → 空参数版，换行，终止
```

**折叠表达式（C++17）**——对参数包做统一运算，告别递归：

```cpp
template<typename... Args>
auto sum(Args... args) { return (args + ...); }  // 展开为 a₀ + a₁ + a₂ + ...

template<typename... Args>
bool all(Args... args) { return (... && args); }  // 展开为 a₀ && a₁ && a₂ && ...
```

`sizeof...(Args)` 返回参数包的元素个数。

参数包是纯编译期概念——运行时完全不存在，和 `std::vector` 不同，无堆内存分配。参数包不能索引（`args[0]`）也不能遍历（`for (auto x : args)`），只能通过递归展开或折叠表达式处理。

### 5. SFINAE 与 Type Traits

**SFINAE** = Substitution Failure Is Not An Error（替换失败不是错误）。编译器尝试把模板参数代入函数签名时，如果代入失败，不报错，而是静默淘汰该重载，继续试下一个。

**`std::enable_if`**——控制重载参与海选的条件：

```cpp
// 版本 A：只对整数生效
template<typename T, typename = std::enable_if_t<std::is_integral_v<T>>>
void process(T x) { std::cout << "整数: " << x << std::endl; }

// 版本 B：只对浮点生效
template<typename T, typename = std::enable_if_t<std::is_floating_point_v<T>>>
void process(T x) { std::cout << "浮点: " << x << std::endl; }
```

调用 `process(42)` → 版本 B 替换失败淘汰，版本 A 留下；`process(3.14)` → 反过来。

`enable_if` 必须放在函数签名里（模板参数默认值或返回类型），不能放在函数体里——SFINAE 只在声明部分生效，函数体里的错误是硬错误。

**常用 Type Traits（`<type_traits>`）**：

| 类别 | 示例 | 作用 |
|------|------|------|
| 类型判断 | `is_integral_v<T>`、`is_pointer_v<T>`、`is_class_v<T>` | 返回 bool |
| 类型关系 | `is_same_v<T,U>`、`is_base_of_v<B,D>` | 判断类型关系 |
| 类型变换 | `remove_const_t<T>`、`add_pointer_t<T>`、`decay_t<T>` | 输入类型，输出变换类型 |
| 条件选择 | `conditional_t<B, T, F>` | B 为 true 返回 T，否则 F |

**`if constexpr`（C++17）**——替代 SFINAE 约 80% 的日常场景：

```cpp
template<typename T>
void process(T x) {
    if constexpr (std::is_integral_v<T>) {
        std::cout << "整数: " << x << std::endl;
    } else if constexpr (std::is_floating_point_v<T>) {
        std::cout << "浮点: " << x << std::endl;
    } else {
        std::cout << "其他: " << x << std::endl;
    }
}
```

不匹配的分支完全不编译，所以 `else` 里用 T 不支持的操作也没关系。但 `if constexpr` 只能在一个函数内部分支——需要多个重载且签名不同时，仍需要 SFINAE。

### 6. Concepts（C++20）

给模板参数加约束——"T 必须支持 + 和 <"，替代 SFINAE 的大部分场景，编译器报错从 300 行变成 3 行。

```cpp
#include <concepts>

template<std::integral T>      // T 必须是整数
T add(T a, T b) { return a + b; }
```

**常用标准 Concepts**：`std::integral`、`std::floating_point`、`std::same_as<T,U>`、`std::derived_from<T,B>`、`std::convertible_to<T,U>`、`std::movable`、`std::copyable`、`std::totally_ordered`。

**自定义 Concept**：

```cpp
template<typename T>
concept Addable = requires(T a, T b) {
    { a + b } -> std::convertible_to<T>;  // a+b 合法且结果能转成 T
};

template<Addable T>
T add(T a, T b) { return a + b; }
```

三种等价写法：

```cpp
template<std::integral T> void foo(T x);        // concept 名代替 typename
template<typename T> requires std::integral<T> void foo(T x);  // requires 子句
void foo(std::integral auto x);                  // 缩写函数模板（C++20）
```

Concept 可约束参数包：`std::integral... Rest` 要求 Rest 里每个元素都满足 integral。

### 7. 非类型模板参数（NTTP）与编译期计算

模板参数不一定是类型——可以是**值**。`std::array<T, N>` 是典型：`N` 是 `size_t` 值，不同 N 产生不同类型。

```cpp
template<typename T, std::size_t N>
class array {
    T data[N];
public:
    constexpr std::size_t size() const { return N; }
};
```

C++17 引入 `auto` NTTP：`template<auto Value> struct Constant { static constexpr auto value = Value; };`

**模板元编程（TMP）**——用模板递归在编译期做计算：

```cpp
template<int N> struct Factorial {
    static constexpr int value = N * Factorial<N - 1>::value;
};
template<> struct Factorial<0> { static constexpr int value = 1; };
```

实际开发中优先用 `constexpr` 函数替代 TMP，写法直观得多：

```cpp
constexpr int factorial(int n) { return n <= 1 ? 1 : n * factorial(n - 1); }
```

`constexpr` 函数覆盖了大部分编译期计算场景。真正离不开 TMP 的场景是对**类型本身**做计算（如 `remove_const`）——但 `<type_traits>` 已经写好了。

### 8. CTAD（C++17）

Class Template Argument Deduction——类模板也能自动推导参数：

```cpp
std::pair p{3, 4.0};      // 推导为 std::pair<int, double>（不再需要写尖括号）
std::vector v{1, 2, 3};   // 推导为 std::vector<int>
std::array a{1, 2, 3};    // 推导为 std::array<int, 3>（NTTP 也能推导）
```

编译器对每个构造函数做隐式函数模板推导。自定义推导指引（deduction guide）极少需要手写。

## 直觉 / 类比

- **模板是菜谱，类型参数是食材，编译器是厨师**——一份"炒 X"的菜谱传牛肉进去自动生成炒牛肉的代码。
- **两阶段编译是编辑审稿**——第一遍看语法和格式（非依赖名），第二遍看内容逻辑对不对（依赖名）。
- **SFINAE 是海选机制**——几个候选人挨个试镜，不合适的悄悄淘汰，从剩下的里选最好的。
- **特化是定制菜谱**——大部分食材走通用流程，豆腐（bool）先焯水去腥，单独一份专版。
- **变参模板是俄罗斯套娃**——每次打开最外层（取 first），把里面剩下的（rest）原样传下去，直到最里面空的。
- **Concepts 是模板参数的接口规范**——以前靠 SFINAE 隐式约束，现在直接写 "T 必须支持 + 和 <"。

## 常见误区

- **"模板代码可以像普通代码一样声明放 .h、实现放 .cpp"**：模板实例化发生在调用方编译单元，编译器需要完整的蓝图才能生成代码。只有声明不够，链接时报 `undefined reference`。本质原因：模板先有调用后有机器码，普通函数先有机器码后有调用。
- **"`typename` 和 `class` 在模板参数里有区别"**：`template<typename T>` 和 `template<class T>` 完全等价。但 `typename T::value_type` 中 `typename` 是声明依赖类型的，不能换成 `class`。
- **"函数模板可以偏特化"**：只支持全特化，且实践中几乎不用——函数重载是更好的替代。
- **"偏特化就是给部分模板参数指定值"**：偏特化的本质是模式匹配，不是参数填充。`template<typename T> struct Foo<T*>` 没有固定任何类型，只是加了"T 是指针"的模式约束。
- **"`enable_if` 可以放在函数体里"**：SFINAE 只在函数模板声明部分生效（返回类型、参数类型、模板参数默认值）。函数体里的错误是硬错误。
- **"`if constexpr` 和 SFINAE 可以完全互相替代"**：`if constexpr` 只能在一个函数内部分支，需要不同的函数签名或返回类型时仍需 SFINAE。
- **"模板元编程是写 C++ 的必备技能"**：日常开发中 `constexpr` 函数 + `<type_traits>` 成品已覆盖绝大多数场景，只有库作者需要手写 TMP。
- **"有 Concepts 就不用 SFINAE 了"**：日常场景确实如此，但底层机制仍在（编译器仍靠替换失败淘汰重载），偏底层的库代码 SFINAE 仍比 Concepts 灵活。

## 关联

- [编译模型](compilation-model.md) — 模板必须放头文件的底层根因：翻译单元单 TU 可见性 + ODR 规则 3 例外；那篇讲构建期规则，本篇讲模板自身的实例化机制
- [Perfect Forwarding](perfect-forwarding.md) — 万能引用 + `std::forward` 依赖模板参数推导和引用折叠
- [STL](stl.md) — STL 容器、算法、迭代器全部基于模板实现
- [std::ranges::sort](ranges-sort.md) — C++20 ranges 的投影和比较器参数依赖 concept 约束
- [Move Semantics](move-semantics.md) — `std::move` 是函数模板，依赖模板参数推导
- [Value Categories](value-categories.md) — 左值/右值区分是理解万能引用 `T&&` 的前提

## 面试常见问题

- **Q**: 模板的类型替换发生在编译期还是运行时？
  **A**: 编译期。模板实例化完全在编译阶段完成，调用模板前对应类型的代码根本不存在——编译器根据蓝图和具体类型参数现场生成。运行时零额外开销，但代价是编译时间更长、错误信息更难读。
  *来源：牛客 • Siaospeed • 柠檬微趣 AI 面试*

- **Q**: 模板全特化和偏特化的区别？函数模板能偏特化吗？
  **A**: 全特化为所有模板参数指定具体类型（`template<> struct Foo<int>`），尖括号为空表示不再泛型。偏特化不写死具体类型，而是对参数做模式约束（`template<typename T> struct Foo<T*>`），匹配时选最特化的版本。函数模板不能偏特化，有定制需求时用函数重载替代——行为更可预测。
  *来源：知乎 • 竹一 • [【C++经典面试题】模板与泛型编程(Q15)](https://zhuanlan.zhihu.com/p/2048676529593496594)*

- **Q**: SFINAE 是什么？`std::enable_if` 的实现原理是什么？
  **A**: SFINAE = Substitution Failure Is Not An Error。编译器尝试把模板参数代入函数签名时，如果替换失败（如 `T::value` 在 `T=int` 时不存在），不直接报错，而是静默淘汰该重载，继续找下一个候选。`enable_if` 利用偏特化实现：主模板在条件为 false 时不给 `::type`，偏特化在条件为 true 时才定义 `::type`。替换时 `::type` 不存在 → SFINAE 淘汰该重载。C++17 的 `if constexpr` 和 C++20 的 Concepts 是更现代的替代方案。
  *来源：知乎 • 竹一 • [Q16](https://zhuanlan.zhihu.com/p/2048676529593496594)；知乎 • 深入浅出cpp • [快手C++一面](https://zhuanlan.zhihu.com/p/1956467330805641681)*

- **Q**: 可变参数模板如何递归展开？C++17 的折叠表达式解决了什么问题？
  **A**: 先定义空参数的终止版本（递归出口），再定义递归版本分离第一个参数和剩余参数包（`T first, Rest... rest`）。函数体内处理 `first` 后以 `rest...` 调用自身，层层剥离直到参数包为空。折叠表达式（`(args + ...)`）让整段递归化简为一行，编译器自动展开，无需手写终止版本和递归版本两个重载。
  *来源：知乎 • 竹一 • [Q17](https://zhuanlan.zhihu.com/p/2048676529593496594)*

- **Q**: 模板元编程是什么？有什么优缺点？现代 C++ 有哪些替代方案？
  **A**: 利用模板递归实例化在编译期做计算的技术（如编译期阶乘 `Factorial<5>::value`）。优点：零运行时开销、类型安全编译期检查。缺点：代码可读性差、编译时间长、错误信息晦涩。现代替代：C++11 `constexpr` 函数替代值计算，C++17 `if constexpr` 替代类型分支，C++20 Concepts 替代约束——日常开发基本不需要手写 TMP。
  *来源：知乎 • 深入浅出cpp • [快手C++一面](https://zhuanlan.zhihu.com/p/1956467330805641681)*

- **Q**: C++20 的 Concepts 和 SFINAE 是什么关系？为什么说 Concepts 是更好的替代？
  **A**: Concepts 是在 SFINAE 之上构建的语法层封装。底层仍靠替换失败淘汰重载，但写法从 `enable_if<is_integral_v<T>>` 变成 `template<std::integral T>`，语义直接可读。报错从几百行模板展开变成"T 不满足 integral"——这是日常开发最大的体验提升。SFINAE 在偏底层库代码中仍保留灵活性优势。
  *来源：知乎 • 深入浅出cpp • [快手C++一面](https://zhuanlan.zhihu.com/p/1956467330805641681)*

- **Q**: 为什么模板的定义和实现要放在头文件中？
  **A**: 模板实例化发生在调用方编译单元——编译器看到 `max(3,5)` 时需要蓝图才能生成 `max<int>`。如果头文件只有声明没有实现体，编译器拿不到蓝图、无法实例化，链接时报 `undefined reference`。必须把实现全放头文件，或通过 `#include` 把实现文本拉入调用方。唯一例外是显式实例化（`template class vector<int>;`），但只适用于知道所有使用场景的库作者。
  *来源：牛客 • Siaospeed • 柠檬微趣 AI 面试*

- **Q**: 写一个比较大小的模板函数。
  **A**: `template<typename T> T mymax(T a, T b) { return a > b ? a : b; }`。使用 `>` 而非 `<`（更符合直觉），注意两个参数类型必须一致——`mymax(3, 4.0)` 报错，因为推导阶段不触发隐式类型转换。需要混用不同类型时显式指定：`mymax<double>(3, 4.0)`。
  *来源：牛客 • 八分七月 • 平旦科技-c++*
