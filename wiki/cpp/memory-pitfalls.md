---
title: Memory Pitfalls
topic: cpp
tags: [cpp, memory-management, debugging, ownership, exception-safety]
summary: C++ 内存管理的六大常见陷阱：悬垂指针（智能指针也不能消灭）、shared_ptr 循环引用（weak_ptr 破环）、use-after-move、构造中裸 new 的异常安全漏洞、shared_ptr 指向栈对象、make_shared + weak_ptr 的内存滞留。每个陷阱的根因都是"所有权不清"或"生命周期假设错误"。
created: 2026-07-18
updated: 2026-07-18
---

## TL;DR

C++ 的内存陷阱常常不会立刻崩溃——它们是不确定行为，可能在周二的生产环境才爆炸。六类最常见陷阱：悬垂指针、循环引用、use-after-move、构造异常安全、shared_ptr 指向栈对象、make_shared 内存滞留。核心原因是所有权模糊和生命周期假设错误。

## 陷阱一：悬垂指针——活过了主人

```cpp
int* p;
{
    int x = 42;
    p = &x;   // p 指向栈上的 x
}             // x 死了，p 变成悬垂指针
*p = 10;     // 未定义行为——可能崩溃，也可能悄悄写坏别人的栈帧
```

**智能指针也不消灭所有悬垂**：

```cpp
auto p = std::make_unique<int>(42);
int* raw = p.get();  // 裸观察指针
p.reset();           // 对象被释放
*raw = 10;           // 悬垂——智能指针管不了裸指针
```

**解法**：持有裸观察指针的代码，必须保证其生命周期短于拥有者。这需要在设计层面保证，不是语法层面能自动检查的。

## 陷阱二：shared_ptr 循环引用——经典泄漏

```cpp
struct B;
struct A { std::shared_ptr<B> b; };
struct B { std::shared_ptr<A> a; };

auto a = std::make_shared<A>();
auto b = std::make_shared<B>();
a->b = b;   // B 的引用计数 = 2（b 持有，a->b 持有）
b->a = a;   // A 的引用计数 = 2（a 持有，b->a 持有）
// a 和 b 离开作用域 → 引用计数各减 1 → 各剩 1 → 互相等对方先释放 → 泄漏
```

**解法**：打破循环的一方用 `weak_ptr`：

```cpp
struct B;
struct A { std::shared_ptr<B> b; };
struct B { std::weak_ptr<A> a; };  // 不增加引用计数
```

**原则**：拥有者用 shared_ptr，被拥有者回指拥有者用 weak_ptr（或裸指针，如果被拥有者保证不比拥有者活得久）。

## 陷阱三：use-after-move——资源已经走了

```cpp
auto p = std::make_unique<int>(42);
auto q = std::move(p);  // p 的内部指针被置为 nullptr
*p = 10;                // 解引用空指针——未定义行为
```

编译器通常不警告（`[[clang::consumed]]` 注解可以辅助检查，但标准库没用）。好习惯：`std::move` 之后不要碰被移动的对象，除非你显式赋了新值。

## 陷阱四：构造函数中的裸 new——异常安全漏洞

```cpp
class Widget {
    int* a;
    int* b;
public:
    Widget() : a(new int(1)), b(new int(2)) {}
    // 如果 new int(2) 抛异常——a 已分配但构造未完成，析构不会被调用 → 泄漏
    ~Widget() { delete a; delete b; }
};
```

C++ 规则：构造函数如果没执行完（中途抛异常），析构函数不会被调用。而已经完整构造的成员子对象（如 `a` 是 `int*`，已赋值）不会自动清理。

**解法**：成员用 `unique_ptr`：

```cpp
class Widget {
    std::unique_ptr<int> a;
    std::unique_ptr<int> b;
public:
    Widget() : a(std::make_unique<int>(1)), b(std::make_unique<int>(2)) {}
    // 如果 b 构造失败，a 作为已完整构造的子对象，其析构函数自动被调用
};
```

## 陷阱五：shared_ptr 指向栈对象

```cpp
int x = 42;
std::shared_ptr<int> p(&x);  // 危险！p 析构时会 delete &x
```

shared_ptr 默认用 `delete` 释放——它假设你指的东西是 `new` 出来的。指向栈地址时，析构时的 `delete` 是未定义行为。可以用空操作删除器规避，但这样做仍然容易出错（p 的生命周期必须短于 x）。**智能指针只管理堆对象，栈对象不需要管。**

## 陷阱六：make_shared + weak_ptr 的内存滞留

```cpp
auto sp = std::make_shared<HugeObject>(/* 100MB */);
std::weak_ptr<HugeObject> wp = sp;
sp.reset();  // 引用计数归零——但 100MB 内存还在！
// make_shared 把对象和控制块分配在一块内存里
// weak_ptr 需要控制块，所以整块内存（含 100MB 对象）都释放不了
```

**解法**：如果 weak_ptr 会长期持有，用 `shared_ptr<T>(new T(...))` 替代 `make_shared`——两次分配，对象和控制块分开，shared_ptr 清零后对象立即释放。

## 关联

- [Smart Pointers](smart-pointers.md) — 陷阱一到六的根因大多在所有权不清，智能指针是正解
- [RAII](raii.md) — 陷阱四的正解是用 RAII 成员替代裸指针成员
- [Move Semantics](move-semantics.md) — 陷阱三的根因是对 move 后状态的假设


## 面试常见问题

- **Q: 什么是内存泄漏？C++ 中如何检测和避免？**
  **A**: 内存泄漏是程序分配了堆内存但失去了对它的控制（没有指针指向它），导致无法释放。检测工具：Linux 下用 Valgrind，Windows 下用 CRT 库的 `_CrtDumpMemoryLeaks()`。避免方法：优先使用智能指针和 RAII，保证 `new/delete` 和 `malloc/free` 成对出现，基类析构函数声明为虚函数。
  *来源：知乎 • linux • [链接](https://zhuanlan.zhihu.com/p/688916716)*

- **Q: 智能指针的循环引用怎么发生的？如何排查？**
  **A**: 循环引用发生在两个对象互相持有对方的 shared_ptr。排查方法：检查类中包含 shared_ptr 成员的类型是否也被对方持有；关注 parent-child 和 observer 模式中的双向引用；使用工具（如 Valgrind、AddressSanitizer）检测程序退出时未释放的内存。修复：将其中一方的 shared_ptr 替换为 weak_ptr。
  *来源：小红书 • 牛马日记 • [链接](https://www.xiaohongshu.com/explore/6a0aa2b1000000003502df62)*

- **Q: 为什么 `delete` 之后建议把指针设为 `nullptr`？**
  **A**: `delete` 后指针的值（地址）不会自动变成 `nullptr`——它仍然指向已释放的内存，成为"野指针"。设为 `nullptr` 后，后续任何对它的 `delete` 都是安全的空操作（`delete nullptr` 由标准保证无副作用），解引用时也能更快暴露问题。但这不是银弹——如果有多个指针指向同一块内存，只置空一个是不够的。
  *来源：知乎 • linux • [链接](https://zhuanlan.zhihu.com/p/688916716)*

- **Q: 构造函数中分配资源失败会发生什么？如何避免？**
  **A**: 构造函数中如果某个成员初始化失败抛异常，构造函数未完成——析构函数不会被调用。但之前已经完全构造的子对象（包括基类子对象和已初始化的成员）的析构函数会被自动调用。因此应该用智能指针或 RAII 包装类作为成员，而不是裸指针——确保每个已构造的成员都能自己清理自己。
  *来源：牛客 • 服务端老cpp • 影石 C++ 一面面经*
