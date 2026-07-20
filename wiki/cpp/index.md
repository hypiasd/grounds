---
title: C++ 总览
topic: cpp
tags: [cpp]
summary: C++ 语言层面的语法特性、惯用法和容易踩坑的细节。
created: 2026-07-17
updated: 2026-07-20
---

## 这个主题是什么 / 学习目标

C++ 语言层面的语法特性、惯用法和容易踩坑的细节。重点不是 C++ 教程，而是实际写题/写项目中遇到的"为什么能这样写"的问题。

## 包含笔记

- [编译模型](compilation-model.md) — C++ 源码变可执行文件的规则网：翻译单元、编译/链接两阶段、头文件守卫、ODR、inline、模板分离编译、标准库 .a/.so 辨析
- [Namespace](namespace.md) — 编译期作用域包裹器：声明/定义/跨文件合并、:: 作用域解析、using 声明 vs 指令（头文件禁忌）、匿名命名空间（内部链接避 ODR）

- [Templates](templates.md) — C++ 编译期泛型编程全景：基础实例化、特化、变参模板、SFINAE/Type Traits/Concepts、非类型模板参数与编译期计算
- [Braced-Init-List](braced-init-list.md) — 花括号初始化列表本身无类型，编译器根据目标类型决定调用哪个构造函数
- [Value Initialization](value-initialization.md) — `T{}` 触发值初始化（非默认初始化），对内置类型执行零初始化；级联链、Most Vexing Parse、initializer_list 陷阱
- [Range-Based For with auto&](range-based-for-reference.md) — auto / auto& / const auto& 的选择依据：修改意图 + 拷贝成本
- [std::ranges::sort](ranges-sort.md) — C++20 ranges 版 sort，支持投影和比较器，把"比什么"和"怎么比"拆成独立参数；覆盖四种投影形式和比较器选择原则
- [Move Semantics](move-semantics.md) — 移动语义用指针交接代替深拷贝，std::move 是 cast 而非操作；含智能指针所有权转移、工厂模式、传参原则
- [unordered_set](unordered-set.md) — 基于哈希表的集合，平均 O(1) 查找，emplace 比 insert 省一次临时对象构造
- [Value Categories](value-categories.md) — 左值有名字有地址，右值是临时值；判断方法：能否取地址
- [Perfect Forwarding](perfect-forwarding.md) — 万能引用 + 引用折叠 + std::forward，保持参数原始值类别传递
- [STL](stl.md) — STL 全景：序列容器、有序关联容器、容器适配器、算法与迭代器、pair/tuple/结构化绑定，含容器选型速记和面试常见问题
- [noexcept](noexcept.md) — 承诺不抛异常的标记，移动构造必须加否则 vector 扩容退化为拷贝

- [Stack vs Heap](stack-vs-heap.md) — 栈和堆两种分配方式的本质区别：速度、大小、生命周期、LIFO 约束，以及选择堆的三个硬条件
- [RAII](raii.md) — Resource Acquisition Is Initialization：构造获取 + 析构释放，用栈展开实现异常安全，不只管内存还管文件、锁、连接
- [Smart Pointers](smart-pointers.md) — unique_ptr（独占/零开销）、shared_ptr（引用计数/控制块）、weak_ptr（旁观/破循环引用），选型原则和 make 函数陷阱
- [Memory Pitfalls](memory-pitfalls.md) — 六大常见陷阱：悬垂指针、循环引用、use-after-move、构造异常安全、shared_ptr 指栈对象、make_shared 内存滞留

- [auto / decltype](auto-decltype.md) — auto 类型推导规则（剥引用/剥顶层 const/保留底层 const/initializer_list 例外）、decltype 镜像规则、decltype(auto) 缝合怪；泛型 lambda 和完美转发的前置基础
- [Lambda](lambda.md) — 匿名函数对象的语法糖：捕获 vs 参数、闭包类型与 operator()、C++14 泛型 lambda、STL 算法搭档、六大常见陷阱

- [面向对象 (OOP)](object-oriented.md) — 类/封装、继承(is-a+基类子对象在前)、多态(运行期动态分发)；虚函数机制 vtable+vptr、virtual/override/=default 角色、虚析构陷阱、vptr 存在条件、派生类虚属性继承、何时需要虚函数的决策框架；组合优于继承

## 知识脉络


- **模板 — 类型系统的基础**: [Templates](templates.md) — 模板是 STL、移动语义、完美转发的底层机制，建议在所有容器/算法类笔记之前先过一遍

- **命名空间 — 编译期作用域管理**: [Namespace](namespace.md) — 与 [编译模型](compilation-model.md) 强相关：匿名命名空间的"内部链接/ODR 规避"建立在其翻译单元与 ODR 概念上，`inline` 共享方案也呼应其单一定义规则；模板隐含 inline，故定义可放头文件（见 [Templates](templates.md)）
- **基础语法**: [Braced-Init-List](braced-init-list.md) → [Value Initialization](value-initialization.md) → [Range-Based For with auto&](range-based-for-reference.md) — 先理解初始化语法，再理解值初始化语义，再理解循环中的值/引用选择
- **引用到移动**: [Range-Based For with auto&](range-based-for-reference.md) → [Move Semantics](move-semantics.md) — 引用是 move 的前提，理解 auto& 后再看 std::move 才能搞懂"为什么不能 move 副本"
- **值类别到移动**: [Value Categories](value-categories.md) → [Move Semantics](move-semantics.md) → [Perfect Forwarding](perfect-forwarding.md) — 左值右值是 move 的类型基础，move 是无条件转换，forward 是条件转换
- **移动与异常安全**: [Move Semantics](move-semantics.md) → [noexcept](noexcept.md) — 移动构造必须 noexcept 才能被 vector 使用
- **容器应用**: [unordered_set](unordered-set.md) — 综合运用值类别（insert 重载选择）和完美转发（emplace 原地构造）
- **算法简化**: [std::ranges::sort](ranges-sort.md) — 独立主题，和以上笔记平行学习
- **容器使用**: [unordered_set](unordered-set.md) — 独立主题，刷题常用

- **STL 全景**: [STL](stl.md) — 总览所有容器、算法、迭代器、适配器，选型速查，覆盖多数 STL 面试题

- **内存管理**: [Stack vs Heap](stack-vs-heap.md) → [RAII](raii.md) → [Smart Pointers](smart-pointers.md) → [Memory Pitfalls](memory-pitfalls.md) — 先理解两种分配方式，再学 RAII 用栈驱动堆释放，然后掌握智能指针（RAII 在堆内存上的落地），最后了解常见陷阱
- **移动与智能指针**: [Move Semantics](move-semantics.md) → [Smart Pointers](smart-pointers.md) — 移动语义是智能指针所有权转移的底层机制，unique_ptr 的可移动性是移动语义最经典的应用

- **类型推导**: [auto / decltype](auto-decltype.md) — auto 和 decltype 是理解 lambda 闭包类型、泛型 lambda、完美转发返回类型的前提；和模板参数推导共用同一套规则
- **lambda 与现有笔记**: [auto / decltype](auto-decltype.md) → [Lambda](lambda.md) — lambda 闭包类型匿名必须用 auto 存，泛型 lambda 的 auto 参数是模板推导 → 结合 [Templates](templates.md) 理解泛型 lambda 的底层模板机制 → 结合 [Move Semantics](move-semantics.md) 理解初始化捕获 move → 结合 [STL](stl.md) 理解 lambda 在算法中的实战地位


- **面向对象 (OOP)**: [面向对象 (OOP)](object-oriented.md) — 类/继承/多态/虚函数的全景；与 [Templates](templates.md) 对照（静态多态 vs 动态多态）、与 [Smart Pointers](smart-pointers.md) / [Move Semantics](move-semantics.md) / [RAII](raii.md) 配合（多态对象的所有权管理与安全释放）

## 未解问题

- （暂无）
