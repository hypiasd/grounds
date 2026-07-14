# cpp 总览

## 这个主题是什么 / 学习目标

C++ 语言层面的语法特性、惯用法和容易踩坑的细节。重点不是 C++ 教程，而是实际写题/写项目中遇到的"为什么能这样写"的问题。

## 包含笔记

- [Braced-Init-List](braced-init-list.md) — 花括号初始化列表本身无类型，编译器根据目标类型决定调用哪个构造函数
- [Range-Based For with auto&](range-based-for-reference.md) — auto / auto& / const auto& 的选择依据：修改意图 + 拷贝成本
- [std::ranges::sort](ranges-sort.md) — C++20 ranges 版 sort，直接收容器而非迭代器对，更简洁安全
- [Move Semantics](move-semantics.md) — 移动语义用指针交接代替深拷贝，std::move 是 cast 而非操作

## 知识脉络

- **基础语法**: [Braced-Init-List](braced-init-list.md) → [Range-Based For with auto&](range-based-for-reference.md) — 先理解初始化，再理解循环中的值/引用选择
- **引用到移动**: [Range-Based For with auto&](range-based-for-reference.md) → [Move Semantics](move-semantics.md) — 引用是 move 的前提，理解 auto& 后再看 std::move 才能搞懂"为什么不能 move 副本"
- **算法简化**: [std::ranges::sort](ranges-sort.md) — 独立主题，和以上笔记平行学习

## 未解问题

- （暂无）
