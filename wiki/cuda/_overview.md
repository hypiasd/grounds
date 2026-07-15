# cuda 总览

## 这个主题是什么 / 学习目标

GPU 编程基础与工具栈，涵盖执行模型（线程层级、warp/SIMT）、内存体系，以及四层 GPU 编程抽象：CUDA（线程级）→ CUTLASS（模板拼积木）→ TileLang（tile DSL + TVM）→ Triton（块级编译器全包）。

## 包含笔记

- [GPU 执行模型](gpu-execution-model.md) — 线程层级（Grid/Block/Thread + SM/CUDA Core）、Warp 与 SIMT（warp divergence、latency hiding）、GPU 内存层级（寄存器/共享内存/显存），三面相合一
- [Triton](triton.md) — 块级 GPU 编程语言/编译器，用 Python 风格语法写 kernel，编译器自动管理线程、共享内存和同步
- [CUTLASS](cutlass.md) — NVIDIA 开源的 CUDA C++ 模板库，把 GEMM 拆成可组合的 tile 零件（TiledCopy/TiledMMA/Epilogue），追求极致性能
- [TileLang](tilelang.md) — 基于 TVM 的 tile-level DSL，tile 是一等公民，显式管理内存层级（shared/fragment），填在 CUTLASS 和 Triton 之间的生态位

## 知识脉络

推荐阅读顺序：GPU 执行模型（线程层级 → Warp/SIMT → 内存层级）→ CUTLASS → TileLang → Triton。
四层抽象栈的核心张力是控制 vs 效率：
- CUDA 线程级手动管理，性能天花板最高但开发最慢
- CUTLASS 用模板拼积木，性能几乎无损，学习曲线陡
- TileLang 显式 tile + TVM 编译，在控制和效率间找平衡
- Triton 编译器全包，块级编程，开发最快但精细控制最少

## 未解问题

- Occupancy 调优的具体方法
- 不同 GPU 架构（Volta/Ampere/Hopper）的 SM 差异
