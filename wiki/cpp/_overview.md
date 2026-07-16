# cpp 总览

## 这个主题是什么 / 学习目标

C++ 语言层面的语法特性、惯用法和容易踩坑的细节。重点不是 C++ 教程，而是实际写题/写项目中遇到的"为什么能这样写"的问题。

## 包含笔记

- [Braced-Init-List](braced-init-list.md) — 花括号初始化列表本身无类型，编译器根据目标类型决定调用哪个构造函数
- [Value Initialization](value-initialization.md) — `T{}` 触发值初始化（非默认初始化），对内置类型执行零初始化；级联链、Most Vexing Parse、initializer_list 陷阱
- [Range-Based For with auto&](range-based-for-reference.md) — auto / auto& / const auto& 的选择依据：修改意图 + 拷贝成本
- [std::ranges::sort](ranges-sort.md) — C++20 ranges 版 sort，直接收容器而非迭代器对，更简洁安全
- [Move Semantics](move-semantics.md) — 移动语义用指针交接代替深拷贝，std::move 是 cast 而非操作
- [unordered_set](unordered-set.md) — 基于哈希表的集合，平均 O(1) 查找，emplace 比 insert 省一次临时对象构造
- [Value Categories](value-categories.md) — 左值有名字有地址，右值是临时值；判断方法：能否取地址
- [Perfect Forwarding](perfect-forwarding.md) — 万能引用 + 引用折叠 + std::forward，保持参数原始值类别传递
- [noexcept](noexcept.md) — 承诺不抛异常的标记，移动构造必须加否则 vector 扩容退化为拷贝

## 知识脉络

- **基础语法**: [Braced-Init-List](braced-init-list.md) → [Value Initialization](value-initialization.md) → [Range-Based For with auto&](range-based-for-reference.md) — 先理解初始化语法，再理解值初始化语义，再理解循环中的值/引用选择
- **引用到移动**: [Range-Based For with auto&](range-based-for-reference.md) → [Move Semantics](move-semantics.md) — 引用是 move 的前提，理解 auto& 后再看 std::move 才能搞懂"为什么不能 move 副本"
- **值类别到移动**: [Value Categories](value-categories.md) → [Move Semantics](move-semantics.md) → [Perfect Forwarding](perfect-forwarding.md) — 左值右值是 move 的类型基础，move 是无条件转换，forward 是条件转换
- **移动与异常安全**: [Move Semantics](move-semantics.md) → [noexcept](noexcept.md) — 移动构造必须 noexcept 才能被 vector 使用
- **容器应用**: [unordered_set](unordered-set.md) — 综合运用值类别（insert 重载选择）和完美转发（emplace 原地构造）
- **算法简化**: [std::ranges::sort](ranges-sort.md) — 独立主题，和以上笔记平行学习
- **容器使用**: [unordered_set](unordered-set.md) — 独立主题，刷题常用

## 未解问题

- （暂无）
