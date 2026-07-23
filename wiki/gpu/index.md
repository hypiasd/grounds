---
title: gpu
topic: gpu
tags: [gpu, hbm, memory-bandwidth, reuse, cache]
summary: GPU 架构与kernel 优化相关笔记索引——HBM 流量、数据复用、内存层级。
created: 2026-07-22
updated: 2026-07-23
---

# gpu

GPU 架构与 kernel 优化主题笔记。

## 笔记

- [HBM 流量与数据复用](hbm-traffic.md) — 复用=取1次用多次；HBM 流量=从显存搬的字节数（时间≈流量/带宽）；两级抽屉模型；流量 2·M·N·K→理想 M·K+K·N。
- [Roofline 模型与算术强度](roofline.md) — AI=FLOPs/Bytes 决定 GEMM 是带宽游戏还是算力游戏；Roofline 性能上限=min(算力上限, 带宽上限×AI)，拐点是两者相等处；GB/s/TFLOPS 指标定义与如何读 roofline 图
- [延迟隐藏与占用率](latency-hiding.md) — HBM 带宽高但延迟几百 cycle；靠并发 warp 切换把访存等待 overlap 掉（延迟隐藏），occupancy=SM 驻留 warp 占比决定能藏多少延迟；M2 测 GB/s 远低于屋顶时分「延迟没藏住」vs「复用差流量大」两类根因

## 关联

- [gemm：分块 GEMM 的原理与切法](../gemm/tiled-gemm.md)
