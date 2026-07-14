---
title: Move Semantics
topic: cpp
tags: [cpp11, performance, reference, rvalue]
summary: 移动语义用指针交接代替深拷贝，将 vector 等资源的转移从 O(n) 降为 O(1)。std::move 本身是 cast 而非操作——它把左值转为右值引用，触发移动构造函数。移动后源对象处于 valid-but-unspecified 状态（标准库容器通常为空）。
created: 2026-07-14
updated: 2026-07-15
---

# Move Semantics

## TL;DR

拷贝是"照着你的东西重新造一份"（O(n)），移动是"你把东西给我，你自己不要了"（O(1)，只交接指针）。`std::move` 不是函数——它是一个 cast，把变量转成右值引用，触发移动构造函数。移动后源对象处于 valid-but-unspecified 状态，不应再使用。

## 核心概念

### 拷贝 vs 移动

```cpp
vector<string> a = {"cat", "dog", "bird"};
vector<string> b = a;              // 拷贝：分配新内存，逐元素复制 → O(n)
vector<string> c = std::move(a);   // 移动：a 的内部指针交给 c，a 变空 → O(1)
// 此后 a.size() == 0，不要再碰 a
```

移动的本质：`vector` 内部有一个指向堆内存的指针。拷贝需要分配新堆内存 + 复制所有元素；移动只需把指针从源对象"偷"过来，然后把源对象的指针置空。

### std::move 是 cast

`std::move(x)` 本身不产生任何机器码。它只是把 `x` 的类型从"左值引用"转成"右值引用"，让编译器选择移动构造/赋值而非拷贝构造/赋值。真正干活的是接收方的移动构造函数。

### 移动后源对象状态

C++ 标准保证：移动后的对象处于 **valid-but-unspecified** 状态。可以安全销毁或重新赋值，但不应读取其值（除非先检查）。实践中，标准库容器（`vector`、`string`、`map` 等）移动后为空。

### range-based for 中引用 + move 的组合

```cpp
unordered_map<string, vector<string>> m;
vector<vector<string>> ans;

// 拷贝版：每个分组的 vector 被完整复制
for (auto& [_, value] : m) {
    ans.push_back(value);              // copy
}

// 移动版：直接从 map 抢走 vector，零拷贝
for (auto& [_, value] : m) {
    ans.push_back(std::move(value));   // move: value 变空壳，数据转交 ans
}

// 错误版：没有 &，value 是副本——move 抢的是即将销毁的临时量
for (auto [_, value] : m) {
    ans.push_back(std::move(value));   // 白抢，map 原数据不动
}
```

关键规则：**要用 move 从容器里搬东西，循环变量必须有 `&`——否则你搬的是复印件。**

### 移动构造函数的编写

移动构造的本质是"偷指针 + 置空源对象"：

```cpp
class Buffer {
    int*  data_;
    size_t size_;
public:
    Buffer(Buffer&& other) noexcept
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;   // 置空源对象，防止双重释放
        other.size_ = 0;
    }
    ~Buffer() { delete[] data_; }
};
```

三个要点：偷指针（不分配新内存，直接拿地址）、置空源对象（否则析构时双重释放）、`noexcept`（否则 vector 扩容退化为拷贝，详见 [noexcept](noexcept.md)）。

### 移动赋值 vs 移动构造

两者本质一样——偷指针、置空源对象。区别在于目标对象的状态：

- **移动构造**：target 刚诞生，是空的，直接偷就行
- **移动赋值**：target 已存在，可能持有资源，需先释放自己的旧资源再偷

```cpp
Buffer& operator=(Buffer&& other) noexcept {
    if (this != &other) {           // 防自赋值
        delete[] data_;             // 先释放自己的旧资源
        data_ = other.data_;        // 再偷别人的
        size_ = other.size_;
        other.data_ = nullptr;
        other.size_ = 0;
    }
    return *this;
}
```

移动构造像搬进新家——房子是空的，直接放东西。移动赋值像换房——先清掉旧家具再搬新的。所以移动赋值多了两件事：**释放自身旧资源** 和 **防自赋值**。

### return std::move 的危害

函数返回局部变量时，编译器自动处理隐式移动或 NRVO。手写 `return std::move(result);` 不仅多余，还**有害**——它阻止 NRVO。NRVO 是编译器直接在调用者的内存里构造 `result`，连移动都省了，比移动还快。手写 `std::move` 等于告诉编译器"我要移动"，把更好的优化路径堵死了。

所以函数返回值是最不需要 `std::move` 的场景——编译器已经在帮你做了。

### std::move 的刚需场景

真正刚需 `std::move` 的是：**源对象是左值（有名字），编译器不敢偷，但你确实不需要它了**。

1. **把局部变量塞进容器**：`result.push_back(std::move(line));`
2. **从容器里搬走元素**：`auto data = std::move(cache["key"]);`
3. **给已有对象重新赋值**：`target = std::move(big);`

共同点：源对象活着、有名字、编译器默认保护它。`std::move` 是你向编译器签的"放弃所有权"声明。

## 直觉 / 类比

拷贝是复印一本书——费时费纸，原书还在。移动是直接把书从你桌上搬到我桌上——一秒搞定，你桌上空了。`std::move` 不是搬家工人，它只是你贴在书上的一张标签"此书可搬"——真正搬书的是接收方（移动构造函数）。

## 常见误区

- **误区一：以为 `std::move` 会移动数据**——`std::move` 是 cast，不是操作。它不移动任何东西，只是改变了编译器选择重载的偏好。
- **误区二：移动后继续使用源对象**——移动后源对象的状态不确定。标准库容器通常变空，但不应假设或依赖；唯一安全操作是销毁或重新赋值。
- **误区三：对 const 对象用 `std::move`**——`std::move(const_obj)` 返回 `const T&&`，无法匹配 `T(T&&)` 移动构造（因为移动构造需要非 const 右值引用以修改源对象）。结果：静默退化为拷贝。
- **误区四：range-based for 中不用 `&` 就想 move**——`for (auto [_, v] : m) ans.push_back(std::move(v))` 移动的是副本，原容器纹丝不动。必须先有 `auto&` 指到原数据。

## 面试常见问题

- **Q: `std::move` 做了什么？**
  **A**: 它只是一个类型转换——把传入的参数无条件转为右值引用。本身不产生任何代码，不移动任何数据。它的作用是告诉编译器"选移动构造/赋值而不是拷贝"。真正的移动发生在接收方的移动构造函数里（交换指针、置空源对象等）。

- **Q: 移动语义和右值引用的关系？**
  **A**: 右值引用（`T&&`）是语法机制，移动语义是利用这个机制实现的优化策略。`std::move` 把左值转成右值引用，编译器据此选择移动构造而非拷贝构造——而移动构造内部用右值引用"偷"走资源。

- **Q: `std::move` 一个 const 对象会怎样？**
  **A**: 静默退化为拷贝。`std::move(const_obj)` 返回 `const T&&`，移动构造函数签名是 `T(T&&)`（非 const），无法匹配。编译器回退到拷贝构造 `T(const T&)`。const 和 move 是矛盾的——move 需要修改源对象，const 不允许修改。

- **Q: 移动后源对象还能用吗？**
  **A**: 处于 valid-but-unspecified 状态。可以安全销毁（析构函数正常运行）或重新赋值（`a = some_new_value`），但不应读取其内容（除非类型文档明确保证移动后状态）。实践中标准库容器移动后为空。

- **Q: 移动构造和移动赋值有什么区别？**
  **A**: 移动构造的目标对象刚诞生、是空的，直接偷指针就行。移动赋值的目标对象已存在、可能持有资源，必须先释放自身旧资源再偷，还要防自赋值（`this != &other`）。构造是"从无到有"，赋值是"先扔旧的再换新的"。

- **Q: `return std::move(result);` 是好是坏？**
  **A**: 是坏的。编译器看到局部变量被返回会自动隐式移动或 NRVO，手写 `std::move` 反而阻止 NRVO——NRVO 直接在调用者的内存里构造对象，连移动都省了，比移动还快。函数返回值是最不需要 `std::move` 的场景。

- **Q: 什么场景需要手动写 `std::move`？**
  **A**: 源对象是左值（有名字、编译器默认保护）、但你确认不再需要它的场景：把局部变量塞进容器、从容器搬走元素、给已有对象重新赋值。共同点是"编译器不敢偷，但你声明可以偷"。函数返回值不需要——编译器自动处理。

## 关联

- [Range-Based For with auto&](range-based-for-reference.md) — range-based for 中的引用是 move 的前提：`auto&` 才能 move 原数据，`auto` move 的是副本
- [Value Categories](value-categories.md) — 左值/右值是 move 的类型系统基础，std::move 把左值 cast 成右值（xvalue）
- [noexcept](noexcept.md) — 移动构造/赋值必须加 noexcept 才能被 vector 使用，否则扩容退化为拷贝
- [Perfect Forwarding](perfect-forwarding.md) — std::move 是无条件转换，std::forward 是条件转换，两者都是 cast
- [unordered_set](unordered-set.md) — insert 的重载选择依赖参数是左值还是右值
