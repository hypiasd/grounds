---
title: LeetCode C++ 常用写法
topic: cpp
tags: [cpp, leetcode, practical-tips]
summary: 把 C++ 语言特性（STL、lambda、引用）组合成刷题代码的实战写法——覆盖堆/二分/位运算/浮点精度/迭代器失效/有序容器/链表技巧七大方向，每个方向给可直接搬的写法与常见坑。
created: 2026-07-20
updated: 2026-07-20
---

## TL;DR

力扣不考语言深度，考"手速和边界"。本笔记把仓库里已学的 STL、lambda、value-initialization、move 等机制**组合成解题代码**，覆盖七个最高频的实战方向：优先队列、二分、位运算、浮点精度、迭代器失效、有序容器、链表技巧。每个方向给"能直接搬上题的写法 + 最容易踩的坑"。核心纪律只有一条：**边界不变量一致、类型宽度够、别用 `==` 比浮点**。

---

## 优先队列（堆）

**直觉**：`priority_queue` 是个"自动按优先级出队"的容器——默认大根堆（最大的先出），要小根堆得自己告诉它"什么叫大"。

**写法**：
```cpp
#include <queue>
priority_queue<int> maxHeap;                       // 默认大根堆
priority_queue<int, vector<int>, greater<int>> minHeap; // 小根堆

// 自定义类型进堆：比较器语义与 sort 相反！
struct Node { int id, score; };
auto cmp = [](const Node& a, const Node& b) {
    return a.score > b.score;   // a.score 更大 → a 优先级更低 → 小根堆（score 小的先出）
};
priority_queue<Node, vector<Node>, decltype(cmp)> pq(cmp);

// top 取顶、pop 弹出（两个独立操作，pop 无返回值）
int top = pq.top(); pq.pop();
```

**常见误区**：
- **比较器语义和 `sort` 相反**：`sort` 里 `a<b` 是升序；`pq` 里 `comp(a,b)==true` 表示 `a` 排在 `b` 后面（优先级更低）。新手常在这里搞反符号。
- `pq.top()` 取顶后必须再 `pq.pop()` 才能弹出——`pop` 返回 `void`，不能 `pq.pop().top()`。
- 声明带比较器的堆时，`decltype(cmp)` 和后缀 `(cmp)` 都要写，少一个编译失败。

**关联**：比较器语法依赖 [Lambda](lambda.md)；`greater<int>` 是 `functional` 里的函数对象。

---

## 二分查找

**直觉**：二分是在有序区间上"每次砍掉一半"，核心纪律是**循环不变量**——`[left, right]` 的语义每次循环前后必须一致，否则差一位（off-by-one）。

**写法**：
```cpp
// 找 >= target 的第一个位置（左闭右开 [l, r)）
int l = 0, r = n;
while (l < r) {
    int mid = l + (r - l) / 2;   // 防溢出，别写 (l+r)/2
    if (nums[mid] < target) l = mid + 1;
    else r = mid;
}
// 结束 l == r，即第一个 >= target 的下标

// 二分答案（答案在连续区间，实数用 eps 退出）
double lo = 0, hi = 1e9;
while (hi - lo > 1e-7) {
    double mid = (lo + hi) / 2;
    if (check(mid)) lo = mid; else hi = mid;
}
```

**常见误区**：
- `mid = (l + r) / 2` 在 `l, r` 很大时**溢出**——用 `l + (r - l) / 2`。
- 边界写错常因"闭区间 vs 半开区间"混用。固定一种约定（推荐 `[l, r)` 半开）贯穿全程。
- 实数二分循环靠 `hi - lo > eps` 退出，退出后取 `(lo+hi)/2` 作答案。
- `lower_bound`/`upper_bound` 是 STL 现成二分（见 [STL](stl.md)），前提是有序。

**关联**：和 [STL](stl.md) 的 `lower_bound` 同源；实数版本依赖浮点精度（见下节）。

---

## 位运算技巧

**直觉**：整数是 32/64 个开关排成一排。位运算直接拨开关——比加减乘除更底层、更省事，适合"状态""去重""子集"类题。

**写法**：
```cpp
// 消掉最低位的 1（统计二进制里 1 的个数）
int cnt = 0; while (n) { n &= n - 1; cnt++; }

// 取最低位的 1（得到 2 的幂，lowbit）
int lowbit = n & -n;            // -n 是 n 的补码（~n+1）

// 异或：相同为 0，不同为 1 → 找落单的数、两数交换
int single = 0; for (int x : nums) single ^= x;
a ^= b; b ^= a; a ^= b;         // 不用临时变量交换（a,b 不能同地址）

// 状态压缩：枚举所有子集
for (int mask = 0; mask < (1 << n); ++mask) { /* 处理 mask 表示的子集 */ }
int ones = __builtin_popcount(mask);   // 数 1 的个数（GCC/Clang 内建）
```

**常见误区**：
- 异或交换法当 `a`、`b` 是**同一变量**时会清零——别在 `swap(nums[i], nums[i])` 用。
- `1 << n` 当 `n >= 31`（int）时溢出，子集枚举用 `1LL << n` 或 `long long`。
- `__builtin_popcount` 参数是 `unsigned int`；`long long` 用 `__builtin_popcountll`。

**关联**：与浮点/整数边界同属"数值技巧"；`__builtin_popcount` 是编译器内建，非标准库。

---

## 浮点精度

**直觉**：浮点像"用有限个格子近似实数"。`0.1` 在二进制里是无限循环，存进 `double` 已被舍入——所以 `0.1 + 0.2 != 0.3`。精度分散在**计算、比较、显示**三个独立环节，各自机制不同。

**写法**：
```cpp
#include <cmath>
#include <iomanip>
#include <limits>

// 1) 比较必须用 eps（绝对误差）
const double EPS = 1e-9;
bool eq(double a, double b) { return fabs(a - b) < EPS; }
// 量级大时用相对误差
bool eqRel(double a, double b) {
    return fabs(a - b) <= EPS * max(fabs(a), fabs(b));
}

// 2) 显示：fixed 的有无天壤之别
cout << setprecision(2) << pi;          // 无 fixed → 2 位有效数字（如 3.1）
cout << fixed << setprecision(2) << pi; // 有 fixed → 小数点后 2 位（3.14）

// 3) 绕开浮点：比例比较用交叉相乘（整数化）
bool lessRatio(int a, int b, int c, int d) {
    return (long long)a * d < (long long)b * c;  // 代替 (double)a/b < (double)c/d
}

// 4) 取整家族（符号不同结果差很多）
floor(2.7);   // 2    floor(-2.7); // -3  向下
ceil(2.7);    // 3    ceil(-2.7);  // -2  向上
trunc(2.7);   // 2    trunc(-2.7); // -2  向零（截断）
round(2.7);   // 3    round(-2.7); // -3  远离零（四舍五入）
```

**常见误区**：
- **用 `==` 比浮点几乎永远不稳**——走 `eps`，或转成整数（交叉相乘）彻底规避。
- **漏写 `fixed`**：想保留两位小数却得到 `3.1e+00` 之类的有效数字格式。
- `round` 不是 `trunc`：要"四舍五入取 int"用 `round(x)`，别用 `(int)x`。
- `NaN` 参与比较全 false（`nan == nan` 也是 false），判缺失用 `isnan()`。
- 大数相减会"灾难性抵消"丢精度——换算法或升 `long double`。

**关联**：与整数溢出/类型宽度（[Value Initialization](value-initialization.md) 的 `T{}` 零初始化）同源，都属"类型与精度意识"。

---

## 迭代器失效与 erase

**直觉**：`vector` 在内存里连续排。删中间一个元素，后面全体前移——原来的迭代器就"指错地方"了，这是经典 UB 来源。

**写法**：
```cpp
vector<int> v = {1,2,3,4,5};

// 删除满足条件的元素（C++11+ 推荐）
for (auto it = v.begin(); it != v.end(); ) {
    if (*it % 2 == 0) it = v.erase(it);  // erase 返回下一个有效迭代器
    else ++it;
}

// erase-remove 惯用法：删掉所有等于 x 的元素
v.erase(remove(v.begin(), v.end(), x), v.end());

// 区间删除 / 倒序删除
v.erase(v.begin() + 1, v.begin() + 3);
for (int i = v.size() - 1; i >= 0; --i)
    if (v[i] == x) v.erase(v.begin() + i);
```

**常见误区**：
- ❌ `for (auto it = v.begin(); it != v.end(); ++it) if (...) v.erase(it);` —— `erase` 后 `it` 失效，再 `++it` 是 **UB**。
- `erase-remove` 里 `remove` 不真删元素，只把保留的往前挪并返回新尾迭代器，必须再 `erase` 才缩容。
- `erase(it++)` 旧写法在 C++11 后对 `vector` 不保证安全，用 `it = v.erase(it)` 更清晰。
- `string` 的 `erase(s.begin()+i)` 同样失效规则；删字符串里字符推荐 `erase-remove` 或倒序下标法。

**关联**：连续容器语义呼应 [Stack vs Heap](stack-vs-heap.md)；悬垂指针风险见 [Memory Pitfalls](memory-pitfalls.md)。

---

## 有序关联容器（map / set / multiset）

**直觉**：`unordered_map` 像乱序抽屉，查得快但顺序不可预测；`map`/`set` 是排好序的文件柜，牺牲一点速度换来**永远有序、能按范围/key 查**。

**写法**：
```cpp
#include <map>
#include <set>

set<int> s; s.insert(3); s.insert(1); s.insert(2);
// 遍历得到 1 2 3（已排序）
multiset<int> ms; ms.insert(2); ms.insert(2);   // 允许重复

map<string, int> m; m["apple"] = 3;             // 按 key 字典序
auto it = m.lower_bound("apple");                // 第一个 key >= "apple"（O(log n)）
// 删掉所有小于 3 的元素（有序容器才能按值范围删）
s.erase(s.begin(), s.lower_bound(3));
```

**常见误区**：
- `set` 不能存重复值；要重复用 `multiset`。
- `set`/`multiset` 没有 `operator[]`（元素即 key）；想改得先 `erase` 再 `insert`（排序位置依赖值）。
- `map::operator[]` 对不存在的 key 会**插入默认值**——只读判断用 `m.find(k) != m.end()` 或 `m.count(k)`。
- 要"按 value 排序"得倒出来放进 `vector<pair>` 再 `sort`（见 [Lambda](lambda.md) 比较器）。

**关联**：与 [unordered_set](unordered-set.md) 同族，区别在"有序+红黑树" vs "无序+哈希"；选型依据是"要不要按顺序/按范围遍历"。

---

## 链表技巧

**直觉**：链表没有下标，全靠指针接力。几个固定套路（哨兵、快慢指针、反转）能解一大半链表题。

**写法**：
```cpp
struct ListNode {
    int val; ListNode *next;
    ListNode(int x) : val(x), next(nullptr) {}
};

// dummy 哨兵：避免处理头节点特例
ListNode* dummy = new ListNode(0); dummy->next = head;
ListNode* cur = dummy;
while (cur->next) { /* ... */ cur = cur->next; }
return dummy->next;     // 返回真正的头，不是 dummy

// 快慢指针：找中点 / 判环
ListNode *slow = head, *fast = head;
while (fast && fast->next) { slow = slow->next; fast = fast->next->next; }

// 反转链表（迭代）：必须先存 nxt 再改 next
ListNode *prev = nullptr, *cur = head;
while (cur) {
    ListNode* nxt = cur->next;   // 先存下一个
    cur->next = prev; prev = cur; cur = nxt;
}
return prev;
```

**常见误区**：
- 忘了 `return dummy->next` 而是返回 `dummy`——会把值为 0 的哨兵节点带进去。
- 反转链表时**必须先存 `nxt = cur->next`** 再改 `cur->next`，否则断链后找不到后续。
- 快慢指针循环条件 `fast && fast->next`——漏 `fast->next` 判空会在偶数长度/`fast->next` 为 null 时崩。
- 力扣一般不要求 `delete dummy`，但本地多次运行注意内存（见 [Memory Pitfalls](memory-pitfalls.md)）。

**关联**：指针/动态内存语义见 [Stack vs Heap](stack-vs-heap.md)；`new` 与 [RAII](raii.md) 的取舍。

---

## 面试常见问题

- **Q**: 用 `priority_queue` 实现小根堆，元素是 `Node{int id; int score;}`，按 score 升序（最小的先出）。写出比较器并指出和 `sort` 的符号差异。

  **A**: 比较器写 `return a.score > b.score;`（a.score 更大表示 a 优先级更低，于是小 score 先出）。关键差异：`sort` 的 `a<b` 是"升序排列"，而 `priority_queue` 的 `comp(a,b)==true` 是"a 排在 b 后面（优先级更低）"——两者语义相反，所以排序升序的 `<` 对应堆里的 `>`。声明：`priority_queue<Node, vector<Node>, decltype(cmp)> pq(cmp);`

- **Q**: `int ans = (a * b) % mod;`（`a,b,mod` 都是 `int`，可能接近 `INT_MAX`）有什么问题？怎么改？

  **A**: `a * b` 在 `int` 里先溢出（UB/错误值）再取模，结果错。必须先把操作数升到 `long long`：`long long ans = (long long)a * b % mod;`（取模本身在 `long long` 范围内安全，若 `mod` 也很大且可能 `(a*b)%mod` 仍超 `long long`，需用 `__int128` 或快速幂）。

- **Q**: `set<int> s = {1,2,3,4,5}`，删掉所有小于 3 的元素，怎么写？

  **A**: 利用有序容器的按值范围删除：`s.erase(s.begin(), s.lower_bound(3));` —— `lower_bound(3)` 返回第一个 `>= 3` 的迭代器，`[begin, 该位置)` 即所有 `< 3` 的元素。这正是 `set` 相比 `unordered_set` 的独有能力。

- **Q**: 判断 `a/b < c/d`（正整数）用 `(double)a/b < (double)c/d` 还是 `(long long)a*d < (long long)b*c`？

  **A**: 后者更稳。`(double)` 版本有浮点精度误差（尤其数值大或接近时），可能误判；交叉相乘把除法转成整数乘法，零精度损失。注意两边乘前把操作数转 `long long` 防溢出。

- **Q**: 想输出 `pi` 保留两位小数，写 `cout << setprecision(2) << pi;` 为什么得到 `3.1` 而不是 `3.14`？

  **A**: `setprecision` 不带 `fixed` 时控制的是"有效数字位数"而非"小数点后位数"。`3.14159` 取 2 位有效数字是 `3.1`。要小数点后两位必须 `cout << fixed << setprecision(2) << pi;`（输出 `3.14`）。

---

## 关联

- [STL](stl.md) — 容器/算法/迭代器全景，本文的 `lower_bound`、`erase-remove` 都建立在它之上
- [Lambda](lambda.md) — 比较器、自定义 `sort`/`pq` 的闭包写法
- [unordered_set](unordered-set.md) — 哈希集合，与本文 `map`/`set` 有序版对照选型
- [Value Initialization](value-initialization.md) — `T{}` 零初始化，避免局部变量未初始化（力扣常见 WA 源）
- [Range-Based For with auto&](range-based-for-reference.md) — 范围 for 的 `auto&` 选择，避免改到副本
- [Stack vs Heap](stack-vs-heap.md) / [Memory Pitfalls](memory-pitfalls.md) — 链表 `new`/指针/悬垂的底层语义
- [Move Semantics](move-semantics.md) — `emplace_back`/移动在容器性能里的角色（防 TLE）
