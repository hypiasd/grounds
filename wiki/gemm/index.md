---
title: gemm
topic: gemm
tags: [gemm, tiling, matrix-multiplication, gpu]
summary: 通用矩阵乘（GEMM）相关笔记索引——分块原理、切法、写回语义。
created: 2026-07-22
updated: 2026-07-22
---

# gemm

通用矩阵乘（GEMM）主题笔记。

## 笔记

- [分块 GEMM 的原理与切法](tiled-gemm.md) — 两个可加性→可分块算对；A/B 各切两维、A_tile/B_tile 沿同一 K 段对齐；写回用 `=` 的语义根；输出块网格 / 单块数据流 / K 维累加三图。

## 关联

- [gpu：HBM 流量与数据复用](../gpu/hbm-traffic.md)
