---
title: 编译模型
topic: cpp
tags: [compilation-model, translation-unit, odr, inline, linking, build, header]
summary: C++ 源码从 .cpp/.h 变可执行文件的规则网——翻译单元（#include 是文本粘贴）、编译/链接两阶段、头文件守卫、ODR、inline、模板分离编译、标准库 .a/.so 辨析。核心洞察：定义在头文件 + 多 TU 包含 = multiple definition（非模板）/ undefined reference（模板）。类比：每个 .cpp 是一道菜，#include 是拆调料包，编译器厨师只看自己这盘；链接器是总装厂，按零件编号拼整车。
created: 2026-07-20
updated: 2026-07-20
---

## TL;DR

C++ 不是"把源码编译成程序"那么简单——它是**每个 `.cpp` 被独立编译成目标文件，再由链接器按符号拼成可执行文件**的两阶段过程。这套规则解释了你日常所有"玄学"报错：`#include` 本质是文本粘贴（改一个头文件一大片都要重编）、链接期才报 `undefined reference`、模板必须放头文件。不懂模型，这些只能靠记结论。

六个环环相扣的方向：翻译单元 → 头文件守卫 → ODR → inline → 模板分离编译，外加标准库 `.a`/`.so` 两种交付形态。它们是一个环，不是一个清单。

## 核心概念

### 1. 翻译单元（Translation Unit）与 `#include` 文本粘贴

`#include` **不是"导入库"**，而是把头文件**原封不动地文本复制粘贴**进 `.cpp`。一个 `.cpp` 把所有 include 展开后，得到一整块纯 C++ 文本——这就是一个**翻译单元（TU）**。

```cpp
// math.h
int add(int, int);

// main.cpp
#include "math.h"
int main() { return add(1, 2); }
```

预处理后 `main.cpp` 变成：`int add(int,int); int main(){...}`。`add` 在这里**只有声明，没有定义**。`main.cpp` 这个 TU 并不知道 `add` 的实现在哪。

**关键推论**：编译器**只看得见一个 TU**。它不跨文件看定义，跨文件可见性靠链接器，且只认名字不认类型细节。

### 2. 编译 / 链接两阶段

```
预处理 → 编译 → 链接 → 可执行
.cpp+#include 展开成单个TU   每个TU独立 → .o    链接器合并 .o
(文本替换,宏展开)           (机器码+符号表)   (解析符号,分配地址)
```

- **编译**：每个 TU 独立编译成 `.o`。`.o` 记录两类符号——**导出的（Defined, `T`/`D`）**：本 TU 写了定义；**待解析的（Undefined, `U`）**：用到了但本 TU 没定义（如上面的 `add`）。用 `nm main.o` 能看到 `U _Z3addii` 和 `T main`。
- **链接**：链接器在所有 `.o` 里找 `add` 的定义并接上。**找不到** → `undefined reference to 'add'`；**找到两个** → `multiple definition`（违反 ODR）。

### 3. 头文件守卫（Include Guard / `#pragma once`）

**为什么会同一 TU 内出现多次？** 直接：`#include "b.h"` 写两遍；间接（更常见）：`a.h` 含 `b.h`、`c.h` 也含 `b.h`，`main.cpp` 同时 include `a.h` 和 `c.h` → `b.h` 被粘两次。

**解法一：include guard（标准、可移植）**
```cpp
#ifndef MYLIB_B_H
#define MYLIB_B_H
// ... 内容 ...
#endif
```
第一次展开时 `MYLIB_B_H` 未定义 → 定义它并展开内容；同一 TU 内第二次遇到 → 标记已存在 → 整块跳过。

**解法二：`#pragma once`（简洁、非标准但全主流支持）**
```cpp
#pragma once
// ... 内容 ...
```
编译器基于文件路径保证该文件只展开一次。

### 4. 标准库的两种形态：头文件 vs `.a` / `.so`

`#include <iostream>` 让你在**编译期**拿到标准库的**声明**；标准库的**实现**在**链接期**才从 `libstdc++`（`libc++`）接进来。`iostream` 是标准库的"嘴"（文本接口），`libstdc++.a` / `libstdc++.so` 是标准库的"身体"（机器码）——两者都是标准库，只是两个阶段生效。

- **`.a` 静态库（archive）**：链接器从 `.a` 抽取需要的 `.o`，**复制进**你的可执行文件。生成时定死，程序独立可运行，但体积大、多进程不共享。
- **`.so` 共享库（shared object）**：链接器只记录"需要 `libstdc++.so` 里的某符号"，**运行时**由动态链接器（`ld-linux.so` / macOS `dyld`）加载。体积小、多进程共享同一物理页，但运行时必须有对应 `.so`，否则启动报错（`ldd a.out` 可查依赖）。

无论 `.a` 还是 `.so`，链接器解决的都是"未定义符号去哪找定义"——符号解析本身无区别，区别只在找来之后是焊死进文件还是留张提货单等运行时取。

### 5. ODR（One Definition Rule，单一定义规则）

ODR 是链接器的**户籍制度**：整个程序（不是单个 TU，是最终拼起来的可执行文件）里，每个"实体"（函数、全局变量、类、模板实例）——**声明**可以无数份，**定义**必须恰好一个。多了 → `multiple definition`；少了 → `undefined reference`。

**先分清声明 vs 定义**（ODR 的地基）：

| | 声明（Declaration） | 定义（Definition） |
|---|---|---|
| 作用 | 告诉编译器"名字存在、类型长啥样" | 真正分配存储 / 生成代码 |
| 函数 | `int add(int,int);` | `int add(int a,int b){return a+b;}` |
| 变量 | `extern int x;` | `int x;` 或 `int x=0;` |
| 数量 | 每个 TU 可多次 | 全程序恰好一次 |

**ODR 三条规则**：
1. **任何 TU 内**：一个实体最多一个定义（③ 的守卫就是保这条）。
2. **整个程序内**：非 inline 的函数/变量，定义恰好一个。
3. **可跨 TU 重复定义的例外**（class、inline 函数/变量、模板）：允许在多个 TU 各有一份定义，但要求**每份逐字节完全相同**，链接器合并时只留一份。这条例外是 ⑥ inline 和 ⑤ 模板能工作的根基。

**为什么类定义能放头文件、被多个 TU 各包一次却不报错？** 因为 `class` 属于规则 3 例外——每份类定义只要完全相同就合法。但类的**成员函数若在类外定义**（`.h` 里 `void Foo::bar(){...}`）且没加 inline，就退回普通函数 → 多 TU 包含即 `multiple definition`。这就是"成员函数要么类内（隐式 inline），要么放 `.cpp`"的来历。

### 6. `inline` 真面目

`inline` 最被误解：90% 的人以为它是"建议编译器把函数展开、别调用"的**性能提示**。其实那是历史起源、今天的**次要副作用**。它的**本职工作是户籍特赦**——告诉链接器：「这个实体允许在多个 TU 里各有一份**完全相同**的定义，你合并时随便留一份，别报 `multiple definition`。」

- **打破 ODR（本职）**：`inline` 实体允许在多 TU 各有定义，链接器合并。这正是 ④ 修复方法一、⑤ 头文件模板能安全的底层机制。
- **提示内联展开（次要）**：编译器*可能*把调用点替换成函数体——但**只是提示，可忽略**（递归、虚函数、体积过大时不展开）。现代编译器自己会做内联决策，写不写 `inline` 对性能几乎无影响。

**C++17 起：`inline` 变量**
```cpp
inline int g_debug = 0;        // 跨 TU 共享一个可变全局，链接不冲突
inline constexpr int kMax = 100;
```
以前全局变量想放头文件只能 `const`（内部链接、各 TU 副本），`inline` 变量让"头文件里放一个真正共享的可变全局"成为可能。

**隐式 inline 的地方**：类内定义的成员函数（隐式 inline）；所有模板（函数模板、类模板成员）隐式 inline（享受 ODR 例外）。

### 7. 模板分离编译（为什么必须放头文件）

模板不是"代码"，是"代码生成配方"（蓝图）。`template<typename T> class Vector {...};` 只说明"给我 T 我能造 `Vector<int>`"。**实例化发生在"用到它的那个 TU"里，且要求定义可见。**

```cpp
// vector.h —— 若只放声明，定义藏进 vector.cpp
template<typename T> class Vector { public: void push_back(const T&); };
// vector.cpp: template<typename T> void Vector<T>::push_back(const T&) {...}

// main.cpp
#include "vector.h"
int main() { Vector<int> v; v.push_back(1); }
```
编译 `main.cpp` 时只看见 `push_back` 的**声明**，需要 `Vector<int>::push_back` 的实例化代码却看不见定义 → 无法生成 → `main.o` 留未解析符号 `U ...`。而 `vector.cpp` 从没人要求它实例化 `Vector<int>` → `vector.o` 里也**没有**这个实例 → 链接报 `undefined reference to Vector<int>::push_back`。

**解法**：把模板的整个定义放进头文件，使每个用到 `Vector<int>` 的 TU 都能当场实例化，再靠 ODR 规则 3 例外合并同款实例。

> **recurring pattern（全模型收口）**：**定义在头文件 + 被多个 TU `#include` = 多个 TU 各持一份定义**。
> - 非模板实体 → 链接期 `multiple definition`（违反 ODR 规则 2）。
> - 模板实体 → 制造机不在现场，根本没生成代码 → 链接期 `undefined reference`（违反实例化可见性）。
> 两条出路通用：**`inline`**（ODR 规则 3 例外）或"声明留头、定义放唯一 `.cpp`"（满足规则 2）。

## 直觉 / 类比

- **翻译单元 = 一道菜的食材清单**：`#include` 是把调料包拆开倒进自己这盘；编译器厨师只看得见自己这道菜，不知道别人在做什么。
- **编译/链接 = 零件厂 + 总装厂**：编译阶段每个工厂独立把图纸变成零件（`.o`）；链接阶段总装厂按零件编号（符号名）把零件拼成整车。
- **头文件守卫 = 门口防盗门**："桌上已有这份说明书就别再发一份"。
- **ODR = 户籍制度**：声明是身份证复印件（随便印），定义是户口（全国只能一个）。
- **inline = 户籍特赦**："允许这人持证在全国多个派出所各登一份完全相同的户口，合并时留一份。"
- **模板 = 零件制造机（不是现成零件）**：必须现场、看得见完整图纸才能开工；把图纸藏起来，链接器连"该造什么"都不知道。

## 常见误区

- **「加了 `#include "xxx.h"` 库就链接进来了」**：错。include 只让声明可见，真正机器码在链接期才拼。忘了加 `-lxxx` 会 `undefined reference`。include 解决"编译器认不认得名字"，链接解决"名字的实现在哪"。
- **「改一个 `.h` 只影响自己」**：错。所有 `#include` 它的 `.cpp` 都是不同 TU，都得重编——大项目"改一行编译十分钟"的根因。
- **「编译器能跨文件看定义」**：不能。单个 TU 内必须有可见声明才能用；跨 TU 可见性靠链接器，只认名字。
- **「include guard 能解决 ODR / 重复定义」**：错。守卫只防**单 TU 内**重复粘贴；跨 TU 的"一个实体一个定义"由 ODR 管。两层不同维度。
- **「ODR 违规编译器一定会报错」**：不一定。规则 3 要求多份定义逐字节相同；若两个 TU 给同一 inline 函数写了**不同**定义（比如靠宏切换），编译各自通过、链接器随便留一份 → **UB 且不报错**，最阴的 ODR 违规。
- **「声明和定义是一回事」**：不是。`extern int x;` 是声明（不分配存储），`int x;` 是定义；函数只有带函数体才是定义。
- **「`inline` 能提速」**：几乎不。内联展开由编译器自主决定，和写不写 `inline` 基本无关；它的价值是破 ODR / 解决链接。
- **「模板放头文件是因为 inline」**：错。真正原因是实例化要求定义在现场，不是 inline。头文件里的模板确实享受 ODR 例外才不冲突——这是结果，不是原因。
- **「`vector.cpp` 里加 `template class Vector<int>;` 显式实例化不就行了」**：行，但是特例——只能为已知会用到的 T 手动实例化，丧失泛型意义；STL 不可能这么干。
- **「`iostream` 不是标准库吗，怎么又分头文件和 `.a`/`.so`」**：`iostream` 是标准库的**头文件形态**（编译期给声明文本），`libstdc++.a/.so` 是标准库的**二进制形态**（链接期给实现）。同一个标准库的两种形态、两个阶段生效。

## 面试常见问题

- **Q**: 从源码（`.cpp` / `.h`）到可执行文件经历了哪些阶段？

  **A**: 四阶段流水线：预处理（`#include` 文本粘贴、`#define` 宏展开、条件编译）→ 编译（每个翻译单元独立解析类型、生成机器码，产出 `.o` 含符号表）→ 汇编（落定目标文件）→ 链接（链接器解析跨 TU 的符号、合并 `.o` 与库、分配最终地址，产出可执行文件）。可用 `g++ -E` / `-S` / `-c` 分别停在预处理/汇编/目标文件阶段。区分阶段的关键：编译器一次只看一个翻译单元，跨文件的事都留给链接器。

  *来源：GitHub • nminhchau/Q-A • [11-c-preprocessor-compilation-model](https://github.com/nminhchau/Q-A/blob/main/11-c-preprocessor-compilation-model/README.md)*

- **Q**: 编译错误和链接错误怎么区分？为什么 `undefined reference` 和 `multiple definition` 往往在链接期才报？

  **A**: 编译器只校验单个翻译单元内的语法和类型，看到声明就能通过编译（不一定需要定义）。真正的定义在别的 `.o` 里——这份"对账"由链接器做。于是「声明在、定义在别处（或丢了）」→ `undefined reference`；「同一个非 inline 实体被多个 `.o` 各定义一份」→ `multiple definition`。两者本质都是 ODR 在链接期的体现。常见诱因还有：源文件没加进构建、库没链或链接顺序错、声明与定义签名不匹配。

  *来源：GitHub • nminhchau/Q-A • [11-c-preprocessor-compilation-model](https://github.com/nminhchau/Q-A/blob/main/11-c-preprocessor-compilation-model/README.md)*

- **Q**: `#include <file>` 和 `#include "file"` 有什么区别？

  **A**: 尖括号通常用于系统/库头文件，引号用于项目头文件。具体搜索顺序是实现定义的，但惯例是：引号先搜当前文件目录、再走配置的 include 路径；尖括号直接搜系统 include 路径。实战坑：本地文件意外遮蔽系统头文件会导致诡异行为，所以不要混用。

  *来源：GitHub • nminhchau/Q-A • [11-c-preprocessor-compilation-model](https://github.com/nminhchau/Q-A/blob/main/11-c-preprocessor-compilation-model/README.md)*

- **Q**: 头文件为什么要加 include guard？`#pragma once` 和它有什么区别？

  **A**: 头文件常被别的头文件间接包含，同一份声明（类型、inline 函数、模板）在一个翻译单元内被粘贴多次会触发 `redefinition`。include guard（`#ifndef X_H` / `#define X_H` / `#endif`）让第二次粘贴时整块跳过；`#pragma once` 让编译器基于文件路径保证只展开一次，更简洁。前者是标准、全可移植；后者非标准但主流全支持。两者都只防**单 TU 内**重复，管不到跨 TU 的 ODR。

  *来源：GitHub • nminhchau/Q-A • [11-c-preprocessor-compilation-model](https://github.com/nminhchau/Q-A/blob/main/11-c-preprocessor-compilation-model/README.md)*

- **Q**: 静态链接和动态链接的区别？动态链接的原理是什么？

  **A**: 静态链接（`.a`）把库里需要的 `.o` **复制进**最终可执行文件，程序独立可跑但体积大、多进程不共享。动态链接（`.so` / `.dylib` / `.dll`）只让可执行文件记录"我需要 `libxxx.so` 里的某符号"，真正的机器码在**运行时**由动态链接器（`ld-linux.so` / macOS `dyld`）加载，体积小、多进程共享同一物理页，但运行时必须能找到对应 `.so`（`ldd` 可查依赖）。注意：成功编译不代表运行时库找得到。

  *来源：GitHub • nminhchau/Q-A • [11-c-preprocessor-compilation-model](https://github.com/nminhchau/Q-A/blob/main/11-c-preprocessor-compilation-model/README.md)*

- **Q**: 普通全局变量写在头文件会导致 `multiple definition`，为什么 `inline` 变量或 `const` 全局不会？

  **A**: 非 inline 的全局变量定义在头文件被多个 `.cpp` 包含时，每个翻译单元各生成一份定义，链接器看到多份 → `multiple definition`。两条出路：① `inline int x = 0;`（C++17）让同一变量允许在多个 TU 各有一份相同定义，链接器去重留一份；② `const` 全局默认**内部链接**，每个 TU 各留一份互不冲突（但语义上是副本，不再共享同一状态）。所以"头文件里放共享可变全局"的正确写法是 `inline` 变量。

  *来源：GitHub • nminhchau/Q-A • [11-c-preprocessor-compilation-model](https://github.com/nminhchau/Q-A/blob/main/11-c-preprocessor-compilation-model/README.md)*

- **Q**: ODR（单一定义规则）说"任何东西只能定义一次"，这种说法准确吗？

  **A**: 不准确。ODR 分两层防守：① **TU 级铁律**——同一个 `.cpp` 及其展开的头文件里，任何实体严禁多份定义，否则编译期 `redefinition`；② **全程序级博弈**——普通非 inline 函数/变量全程序只能一份定义（否则 `multiple definition`），但**类、枚举、模板、inline 函数/变量**被允许在多个 TU 各有一份定义（这是头文件能放类/模板的根因）。深渊前提：这些特权实体必须满足**逐词法一致（token-by-token identical）**，否则链接器通常不报错、随机折叠留一份，造成跨文件内存布局错配的未定义行为（幽灵 Bug）。

  *来源：技术栈 • 心猿意码 • [C++ 链接陷阱与底层溯源：ODR、inline 与匿名命名空间的那些坑](https://jishuzhan.net/article/2038806022100881410)*

- **Q**: 现代 C++ 中 `inline` 关键字的真正语义是什么？它在底层链接中有什么"特权"？

  **A**: 现代 C++ 里 `inline` 的优化内联含义已让位给编译器自主决策（LTO 等），它的**真身是控制链接行为的指令**，而非性能提示。底层特权：`inline` 函数在编成目标文件时生成的是**弱符号**（ELF 弱符号 / MSVC 的 `COMDAT` 节），链接时多个同名 inline 定义不再报 `multiple definition`，而是被链接器"去重"合并只留一份。这也正是头文件里的类内成员函数、模板、C++17 inline 变量能安全被多 TU 包含的机制。

  *来源：技术栈 • 心猿意码 • [C++ 链接陷阱与底层溯源：ODR、inline 与匿名命名空间的那些坑](https://jishuzhan.net/article/2038806022100881410)*

## 关联

- [Templates](templates.md) — 那篇讲模板实例化/特化；本篇讲"为什么实例化迫使模板定义放头文件"的底层根因（翻译单元单 TU 可见 + ODR 规则 3 例外）
- [Move Semantics](move-semantics.md) — `std::move` 是函数模板；标准库 header-only 设施靠 inline + ODR 例外安全
- [Smart Pointers](smart-pointers.md) — unique_ptr/shared_ptr 的 header-only 实现同样建立在 inline + ODR 例外之上
- [Value Categories](value-categories.md) — 值类别是类型系统基础，本篇是构建系统基础，两者正交
