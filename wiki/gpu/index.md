---
title: gpu
topic: gpu
tags: [gpu, hbm, memory-bandwidth, reuse, cache]
summary: GPU 架构与kernel 优化相关笔记索引——HBM 流量、数据复用、内存层级。
created: 2026-07-22
updated: 2026-07-22
---

# gpu

GPU 架构与 kernel 优化主题笔记。

## 笔记

- [HBM 流量与数据复用](hbm-traffic.md) — 复用=取1次用多次；HBM 流量=从显存搬的字节数（时间≈流量/带宽）；两级抽屉模型；流量 2·M·N·K→理想 M·K+K·N。

## 关联

- [gemm：分块 GEMM 的原理与切法](../gemm/tiled-gemm.md)
