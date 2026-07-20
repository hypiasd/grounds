---
title: 面向对象 (OOP)
topic: cpp
tags: [cpp, oop, polymorphism, virtual-functions, class-design]
summary: 用蓝图/家族基因/万能遥控器类比讲清 C++ 面向对象：类与封装、继承(is-a + 基类子对象在前的布局)、多态(运行期动态分发)。核心是虚函数机制——vtable + vptr（编译期建表、运行期查表），以及 virtual / override / =default 各自的角色、虚析构陷阱、vptr 存在条件、派生类虚属性继承，和"何时需要虚函数"的决策框架。组合优于继承。
created: 2026-07-20
updated: 2026-07-20
---

## TL;DR

面向对象 (OOP) 在 C++ 里由三块组成：**类（封装数据与行为）**、**继承（is-a 关系 + 代码复用）**、**多态（同一调用按对象实际类型表现不同）**。多态靠**虚函数**实现，机制是**编译期为每类建一张虚函数表 vtable、运行期通过对象内藏的 vptr 查表找函数（动态分发 / 晚绑定）**。

关键判断：**虚函数是"可选的超能力"**——只有当你要"用基类指针/引用操作运行期才确定的派生对象、并要它自动干派生类的活"时才需要；否则普通类更轻更快。

## 核心概念

### 1. 类与封装

`class` 把**数据（成员）**和**操作（成员函数）**打包，用访问控制收口内部状态：

- `public` 对外接口、`private` 内部实现（封装 = 你只管按按钮，不用懂引擎）、`protected` 对派生类可见。

```cpp
class BankAccount {
private:
    double balance_;                 // 内部状态，外部不能直接改
public:
    explicit BankAccount(double init) : balance_(init) {}
    void deposit(double x) { if (x > 0) balance_ += x; }  // 唯一合法改余额入口
    double balance() const { return balance_; }             // 只读接口（const = 不修改状态）
};
```

封装 = 把"能改什么、怎么改"收口到少数接口，防止内部状态被随意破坏。

### 2. 继承：is-a 与内存布局

```cpp
class Vehicle {
public:
    int wheels = 4;
    virtual void start() { std::cout << "vehicle start\n"; }
    virtual ~Vehicle() = default;     // 划重点：析构是 virtual
};

class ElectricCar : public Vehicle {
public:
    double battery = 75.0;
    void start() override { std::cout << "electric hum\n"; }
};
```

派生类对象在内存里 = **基类子对象在前 + 派生类新增在后**：

```
ElectricCar 对象:
┌─────────────────────────────────────┐
│ Vehicle 子对象 (wheels, vptr)      │ ← (Vehicle*)&ec 指向这里
├─────────────────────────────────────┤
│ ElectricCar 新增 (battery)         │
└─────────────────────────────────────┘
```

正因为"基类部分在最前面"，基类指针 `Vehicle* p = &ec` 看到的恰好是一个合法的 `Vehicle` 子对象——这是继承在内存层面的物理保证。

### 3. 多态：动态分发（晚绑定）

通过 `Base*`/`Base&` 调用 `virtual` 函数时，C++ **不在编译期决定调哪个版本**，运行期看 `p` 实际指向的对象类型，调它自己的版本：

```cpp
void test(Vehicle* v) { v->start(); }   // 编译期不知道 v 到底是什么，运行期才决定

Vehicle v; ElectricCar ec;
test(&v);    // vehicle start
test(&ec);   // electric hum  ← 同一行表现不同
```

前置陷阱：按值 `Vehicle v2 = ec;` 会**对象切片**——只拷走 `Vehicle` 部分，电动车信息丢失，调用永远是基类版本。必须走指针/引用。

### 4. 虚函数表（vtable）—— 多态的机器实现

- **编译期**：每个含虚函数的类生成一张 `vtable`，里面一排函数指针，`slot i` 对应第 i 个虚函数。
- **运行期**：每个该类对象（通常）内部藏一个 `vptr`，构造时指向自己类的 `vtable`。
- 调用 `p->foo()` 真实发生的是三步：

```cpp
// 伪代码：虚调用等价于
p->vptr->vtable[foo_slot](p);   // 1. 取对象 vptr → 2. 找到 vtable → 3. 取槽位函数指针并调用
```

- 派生类 `override` 时，它的 `vtable` 对应 `slot` 被**换成派生版**；没 override 的槽位保持基类版本。于是同一行 `p->foo()`，对 `Base` 查到基类函数、对 `Derived` 查到派生函数——这就是多态。

> `vptr`（每个**对象**一份，指向表）与 `vtable`（每个**类**一份，所有同类对象共享）是两样东西。对象自己带身份信息（vptr），所以编译期不知道 `p` 是谁也没关系——运行期对象自己"指着"自己的方法表。

### 5. 纯虚函数与抽象类

```cpp
class Shape {                       // 抽象类，不能实例化
public:
    virtual double area() const = 0;     // 纯虚：只声明不实现
    virtual ~Shape() = default;
};

class Circle : public Shape {
    double r;
public:
    explicit Circle(double r_) : r(r_) {}
    double area() const override { return 3.14159 * r * r; }
};
```

含纯虚函数的类是**抽象类**（相当于 Java 的 interface），强迫所有派生类提供实现，即"接口契约"。

### 6. 虚析构陷阱（致命）

```cpp
class Base { public: ~Base() { std::cout << "Base dtor\n"; } };  // ❌ 非 virtual
class Derived : public Base {
    int* buf = new int[100];
public:
    ~Derived() { delete[] buf; }     // 释放资源
};

Base* p = new Derived();
delete p;   // 只调 ~Base()，~Derived() 不被调用 → buf 泄漏！未定义行为
```

原因：`~Base()` 非 `virtual`，`delete p` 在编译期**静态绑定**到 `Base` 析构，根本不查 vtable，派生类析构被跳过。**铁律：只要一个类可能被多态地 delete，析构必须 `virtual`。** 改成 `virtual ~Base() = default;` 即修复。

### 7. virtual / override / =default 各司其职

- `virtual`（写在基类）= **机制**：让函数进 vtable、开启动态分发。没有它就没有多态。
- `override`（写在派生类）= **安全检查**："我本意是重写基类虚函数，若签名不对/无对应虚函数请报错"。它**不制造**多态——基类没 `virtual` 时写 `override` 直接编译错误。
- `= default` = "用编译器生成的默认（空）实现"。比手写 `{}` 意图更清晰，对特殊成员函数还能保留平凡性 (trivial)。

```cpp
struct Shape { virtual double area() const { return 0; } };  // virtual = 机制
struct Circle : Shape {
    double area() const override { return 3.14; }          // override = 安全检查，可选 virtual
};
```

> 类比：`virtual` 是把函数"登记进总机（vtable）"；`override` 是给这次登记贴张"我确认号码登对了"的便利贴。**光贴便利贴不去总机登记，电话打不通。**

### 8. vptr 存在条件 与 派生类虚属性

- **只要类里有至少一个虚函数**（虚成员、虚析构、纯虚都算），每个对象就藏一个 `vptr`；无任何虚函数则无 vptr（对象就是普通内存，可 C 兼容、`memcpy`）。
- 抽象类（含纯虚）必然有 vptr；派生类继承基类的虚属性，**派生类自己不必声明任何虚函数**——它可选 override（改写）或新增虚函数，也可以什么都不写（vtable 槽位复用基类实现）。
- 基派生都无虚函数**完全合法**，且往往是默认最优（省 8 字节、可内联、更简单），只是放弃了运行期多态。

```cpp
class A { virtual void f(); };            // ✅ 有 vptr
class B { virtual ~B() = default; };     // ✅ 即使只有虚析构，也有 vptr
class C { int x; };                      // ❌ 无 vptr，对象只有 4 字节
```

### 9. 什么时候需要虚函数（决策框架）

唯一本质场景：**"我会不会用一个基类指针/引用，去操作一个运行期才确定的派生对象，并希望它自动表现出派生类自己的行为？"** 会 → 加 `virtual`（含析构）；不会 → 不加。

典型需要：① 异构集合统一操作（`vector<Shape*>`，逐个 `draw()`）；② 框架/插件/回调（GoogleTest、Qt 事件，框架编译期不认识你的类）；③ 多态 `delete`（析构必须 virtual）；④ 运行期策略切换 / 依赖注入。

不需要：类型编译期就固定、或只有一个具体类 → 普通类；所有类型编译期已知 → 优先用**模板（静态多态）**避免 vtable 开销。

### 10. 组合优于继承

继承的正确理由是 **is-a**（电动车是一种车）。只为复用功能请用**组合**，松耦合、可随时替换、可持有多个：

```cpp
class Logger { /* 记录日志 */ };
class Service { Logger log_;   // 组合：Service 有一个 Logger，而非"是一种"Logger
public: void run() { log_.record("start"); } };
```

## 直觉 / 类比

- **类 = 蓝图**：图纸描述"车有什么属性、能做什么"，按图造出的具体车（对象）才是能开的。一份图纸造无数辆车。
- **继承 = 家族基因**：电动车自动拥有车的全部特征，再叠加自己的电池，是 is-a 关系。
- **多态 = 万能遥控器**：手里只有"车"的遥控器（`Base*`），按"启动"键时电动车电驱、汽油车烧油——同一按钮不同表现，遥控器无需知道车型。
- **vtable = 遥控器背后的对照表**：每种车出厂配一张自己的"按键→功能"表，按哪个键去查这张表找真实功能。**决定权交给对象自己**——这正是 OOP 可扩展架构（框架、插件、游戏引擎）的基石：写通用代码（`total`、`test`）的人不认识具体类型，对象自己"按图索骥"干自己的活。

## 常见误区

- **"基类指针 delete 派生对象能正确析构"—— 不一定，是致命陷阱。** 基类析构必须 `virtual`，否则只调基类析构、派生部分泄漏（见 §6）。
- **"直接 override 不就好了，为什么还要 virtual"—— 误解层级。** `override` 只是安全检查，建立在"基类有虚函数"前提上；基类没 `virtual` 时写 `override` 直接编译报错，离了 `virtual` 它毫无作用（名字隐藏 ≠ 多态）。
- **"继承是为了复用代码"—— 常见误用。** 正确理由是 is-a；只为复用功能请用组合，滥用继承会让层级僵化、耦合爆炸。
- **"虚函数很慢，能不用就不用"—— 片面。** 虚调用只多一次指针解引用（可能 cache miss），瓶颈几乎从不在这；真正代价是阻止内联。该用就用，别为这点开销牺牲设计。
- **"派生类必须自己写虚函数"—— 错。** 派生类继承基类虚属性，可选 override / 新增 / 什么都不写。

## 面试常见问题

- **Q**: 构造函数可以是虚函数吗？为什么？
  **A**: 不能。虚函数靠对象里的 `vptr` 查 `vtable` 实现，而 `vptr` 是在**构造函数执行期间**才被初始化的——构造完成前它没有有效值，虚调用机制根本跑不起来。并且创建对象时（如 `new Derived()`）已经直接写明了类名，编译器在编译期就知道确切类型，不需要多态分发。所以构造函数没有"虚"的必要，语言也不允许。
  *来源：知乎 • @学徒《C++面试必备之虚函数》 • https://zhuanlan.zhihu.com/p/28530472；牛客 • 嵌入式面经（构造函数为什么一般不定义为虚函数）*

- **Q**: 析构函数可以是虚函数吗？
  **A**: 可以，而且**基类析构应当声明为 `virtual`**——否则通过基类指针 `delete` 派生对象时只调基类析构，派生部分资源泄漏（未定义行为）。这是经典面陷阱：有人面试时想当然答"不能"，直接扣分。口诀："构造不能虚，析构常要虚。"
  *来源：牛客 • @taylor_offer《难受今天面试 有个很简单的c++八股答错》*

- **Q**: 用基类指针调用函数，普通成员函数和虚函数分别由什么决定调哪个版本？
  **A**: 普通成员函数由**指针的静态类型**决定（编译期就绑定）；虚函数由**指针实际指向的对象类型**决定（运行期查 vtable）。一句话记忆："普通看指针类型，虚函数看对象本身。"
  *来源：知乎 • @学徒《C++面试必备之虚函数》 • https://zhuanlan.zhihu.com/p/28530472*

- **Q**: 虚函数表（vtable）是每个对象一份还是每个类一份？存在哪？
  **A**: 每个**类**一份，存放在只读数据段（如 `.rodata`），程序整个运行期一直存在，不随对象创建/销毁而分配或释放；同一类的所有对象（包括未覆盖虚函数的派生类对象）**共享同一份** vtable，各自只存一个 `vptr` 指向它。所以带虚函数的类 `sizeof` 只多一个指针大小（`vptr`），而不是整张表。
  *来源：牛客 • @寿司寄《C++面试题》（虚函数表共享问题）；知乎 • @深入浅出cpp《怎么验证虚函数表内存布局？》 • https://zhuanlan.zhihu.com/p/2015913108040856134*

- **Q**: 在构造函数内部调用该类的一个虚函数，会调到派生类的 override 版本吗？
  **A**: 不会。构造某个类时，对象的 `vptr` 被设为"**当前正在构造的类**"的 vtable，所以此时调用的虚函数是当前类自己的版本，而不是更晚才构造完成的派生类的 override。析构时 `vptr` 已回退到当前类，行为同理。这是多态里极容易踩的坑。
  *来源：牛客 • @寿司寄《C++面试题》（在构造函数里调虚函数会发生什么）*

- **Q**: `A* p = nullptr; p->f();` 一定会崩溃吗？
  **A**: 不一定。`f` 若是**普通**成员函数、且函数体内不访问任何成员变量（不解引用 `this`），很多平台下能"正常"执行——因为调用普通成员函数只需函数地址，不读对象内存（但这是**未定义行为**，不可依赖）。若 `f` 是**虚函数**，调用前要先解 `p` 的 `vptr`，`p` 为 `nullptr` 解引用直接崩溃。
  *来源：牛客 • @寿司寄《C++面试题》（空指针能访问成员函数吗）*

- **Q（高阶）**: 怎么在代码里验证 `vptr` 在对象首部、并手动遍历虚函数表？
  **A**: `vptr` 通常位于对象内存起始处，可用 `void* vptr = *(void**)&obj;` 取出，再用 `*(void**)vptr` 取第 0 个虚函数地址、转成函数指针调用。这能亲手验证"对象 → vptr → vtable → 函数"的三步机制。注意：具体布局依赖编译器（GCC/Clang/MSVC 各异），此操作本身属未定义行为，仅用于理解原理，不要写进生产代码。
  *来源：知乎 • @深入浅出cpp《怎么验证虚函数表内存布局？》 • https://zhuanlan.zhihu.com/p/2015913108040856134*

## 关联

- [Templates](templates.md) — 模板是编译期单态化（静态多态），虚函数是运行期查表分发（动态多态）：性能 vs 灵活性的取舍
- [Smart Pointers](smart-pointers.md) — 多态对象常用 `unique_ptr<Base>` 管理所有权，既享 RAII 自动释放又保留通过基类指针调派生行为的多态能力
- [Move Semantics](move-semantics.md) — `unique_ptr` 的可移动性是移动语义最经典的应用，常用来在容器中搬运多态对象
- [RAII](raii.md) — 多态对象的资源释放依赖 RAII + 虚析构配合，确保 `delete` 基类指针时完整析构
