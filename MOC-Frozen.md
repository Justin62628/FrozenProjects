---
title: Frozen / 饮茶室 RAG
tags:
  - type/ref
  - area/frozen
status: active
updated: 2026-08-22
---

# Frozen / 饮茶室 RAG

独立检索库入口。目前只有饮茶室QA 一批材料，按主题拆在子文件夹里，方便 Agent 引用常见问题与历史讨论。

规范与踩坑：[[README]]。群聊 JSONL 字段：[[NOTE-QQChat-JSONL]]。

## 库

- [[饮茶室QA/MOC-饮茶室QA]] — 核心 FAQ、独立理论、讨论、其他
- [[NOTE-QQChat-JSONL]] — QQChatExporter 导出结构（回复 / 发送人 id）

检索时优先子笔记，不要用 `_source/饮茶室QA-原文`（完整dump，标记 `rag: skip`）。

## 版本

- 2026-08-22：建立 RAG 入口；饮茶室QA 按主题拆分；Prettier 标准化 Markdown；清洗标题结构
- 2026-08-22：补充 README（规范、踩坑、理论提取约定）
- 2026-08-22：记录 QQ JSONL 字段（回复链、senderUid / senderUin）→ [[NOTE-QQChat-JSONL]]
- 2026-08-22：主源改为两群 chunked 导出；跨群是合并转发（uid+时间对齐）；筛选脚本 `_extract/`
