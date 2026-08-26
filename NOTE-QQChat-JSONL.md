---
title: QQ 群导出 JSONL 字段（饮茶室）
tags:
  - type/ref
  - area/frozen
status: active
updated: 2026-08-22
source: QQChatExporter chunked jsonl + NT spool clip
---

# QQ 群导出 JSONL 字段（饮茶室）

RAG 主源是 QQChatExporter 的 **chunked 完整导出**（简化字段，合并转发带正文）。本笔记同时记录 NT 原始 spool clip 的字段，供对照。规范总览见 [[README]]。

## 文件

主源（本机，不进 git）：

| 群 | 路径 | 规模 |
| --- | --- | --- |
| 冰学三点饮茶室 `73xxxxxx2` | `e:\Library\Documents\QQChatExporter\exports\group_冰学三点饮茶室_732870642_20260822_042107409_chunked_jsonl.zip` | 628751 条，2020-02-25 → 2026-08-22，13 个 chunk（提取主源） |
| ❄️冰学奇谈会议室 `10xxxxxx56` | `e:\Library\Documents\QQChatExporter\exports\group_❄️冰学奇谈会议室_1032223756_20260822_043120968_chunked_jsonl.zip` | 93005 条，2020-02-20 → 2026-08-22，2 个 chunk |
| 克莱恩家的晚宴 `83xxxxxx8` | `e:\Library\Documents\QQChatExporter\exports\group_克莱恩家的晚宴_833325688_20260822_060426420_chunked_jsonl.zip` | 153393 条，2025-05-02 → 2026-08-21，4 个 chunk |

提取脚本读 zip 内 `chunks/c*.jsonl`（及 `manifest.json`），不必先解压。文件名里的 ❄️ 是群名的一部分。旧饮茶室目录/zip `…060117249_chunked_jsonl`（315314 条，2024-05-09 → 2026-08-21）已被上面的 `042107409` zip 取代，磁盘上可留着当备份，不要当提取主源。

chunked 一行一条，字段是 `id` / `seq` / `timestamp`（毫秒）/ `sender` / `type` / `content` / `recalled` / `system`。回复在 `content.elements` 里 `type: reply`（必有 `referencedMessageId`）。文件在 `type: file` 的 `filename`。合并转发在 `type: forward`，**嵌套 `data.messages` 有全文**（本库实测最多 100 条，QQ 合并上限）。

对照用的 NT 原始 clip（字段更全，但合并转发只有 XML/`resId`，没有嵌套正文）：

`e:\Library\Documents\QQChatExporter\exports\.qce_spool_streaming_jsonl_1787349677251_d6290d9d6 - clip.jsonl`

clip：38418 条，群仍是饮茶室，时间只覆盖 2026-04-27 → 2026-08-22。入库用 chunked，不要用 clip 当主源。

## 跨群：互相转发聊天记录（不是口嗨引用）

两群正文里互相点名很少（饮茶室提到晚宴约 4 次）。真正的关系是 **把另一群的聊天记录合并转发过来**。

| 方向 | 合并转发总数 | 嵌套消息能对上另一群原文 |
| --- | --- | --- |
| 饮茶室 → 晚宴 | 460 | **29** |
| 晚宴 → 饮茶室 | 808 | **21** |

对不上 `id`（转发副本会换新 id，两群 id 零重叠）。对得上的是 **`(sender.uid, timestamp)`**。对上的标题几乎都是泛称「群聊的聊天记录」。同群自己的聊天记录、别的群、时间对不齐的，会显示为对不上，但正文仍在嵌套 `messages` 里。

提取理论片段时：转发气泡本身就是材料；若嵌套能对上晚宴/饮茶室，把那边当同一段的附件上下文，不要指望 `reply` 跨群。

## 回复 / 引用：支持，且是一等字段

**支持。** 不是从正文猜「回复了某某」，而是 `elements[]` 里的 `elementType: 7` + **`replyElement`**。

本 clip：**5942** 条带回复（约 15.5%）。一条消息最多 **1** 个回复气泡。另有 **@**（`textElement.atType`，本 clip 4676 次），那是点名，不是回复气泡。

### 回复能拿到什么

| 能力 | 字段 | 本 clip |
| --- | --- | --- |
| 被回复消息的群序号 | `replayMsgSeq` → 原消息 `msgSeq` | 5942/5942；clip 内能对上 **5685**（95.7%），**257** 条引用了 clip 开始之前的消息 |
| 被回复者 NT uid | `senderUidStr`（`u_…`） | 几乎全有 |
| 被回复者 QQ 号 | `replyElement.senderUid` | **命名陷阱**：这里实际是 QQ 号字符串，不是顶层那种 `u_…` |
| 被回复时间 | `replyMsgTime` | 全有 |
| 引用预览 | `sourceMsgTextElems[]`（文本/表情/图摘要） | 全有；预览中位约 16 字、最长 323，**不保证原文全文** |
| 原消息快照 | 本条 `records[]` | **5696** 条；用 `sourceMsgIdInRecords` 对 `records[].msgId` |
| 原消息带图 | `sourceMsgIsIncPic` | 495 |
| 原消息已撤回 | `replyMsgRevokeType` | 8 |
| 嵌套「回复的回复」根 | `replayMsgRootSeq` | 仅 1 条非 0，基本可当不支持深层树 |

### `records[]`：被回复消息的一层快照（不是聊天记录树）

`records` **只出现在带回复的消息上**（本 clip 全部是 `msgType: 9`），与 `replyElement` 配套。有回复但没有 `records` 的有 **246** 条：其中 **236** 仍能用 `replayMsgSeq` 在 clip 里找到原文，**10** 条只剩 `sourceMsgTextElems` 预览。

实测边界：

| 能 | 不能 |
| --- | --- |
| 永远 **1 条**：被回复的那一条（`len(records)==1`，`msgSeq` = `replayMsgSeq`） | 不能一次带上多条上下文 |
| 深度 **1**：`records` 里不再套 `records` | 不能从快照还原「B 当时在回复 C」 |
| 快照里有发送人、时间、正文 `elements`（文/表情/图/文件/视频/卡片都见过） | 快照会 **剥掉** 原消息自己的 `replyElement`（本 clip **1470** 条原文其实也是回复，快照里看不到） |
| 图有 `md5HexStr`、`originImageUrl`、本机 `nt_data/Pic` 路径 | 合并转发「聊天记录」气泡 **不进** `records` |
| 正文通常等于原文（5366/5696 文本一致）；个别比气泡预览长（记录最长约 3941 字 vs 预览最长 323） | 撤回后预览可能变成「原消息已被撤回」，快照里仍可能留着旧正文 |

要走回复链：必须用顶层消息的 `replayMsgSeq` **一跳一跳** 回查，不能指望 `records` 自带祖先。QQ 客户端也几乎不填 `replayMsgRootSeq`。

### 合并转发「聊天记录」：本 JSONL 只有摘要

`multiForwardMsgElement` 本 clip **47** 条。字段只有 `xmlContent` / `resId` / `fileName`。XML 里是 UI 摘要（`[聊天记录]`、`查看N条转发消息`），**没有**内嵌那 N 条原文。要全文得另下 `resId`，这份 spool 没带。

### RAG 连边（按这个做）

1. 主键连边：`replyElement.replayMsgSeq` → 原消息 `msgSeq`。
2. 原消息不在当前文件：用本条 `records[]` + `sourceMsgTextElems`。
3. **不要**用 `replayMsgId` 去对顶层 `msgId`：绝大多数是 `"0"`；`sourceMsgIdInRecords` 也 **不是** 顶层 `msgId`，只对嵌套 `records`。

## 身份字段（主键）

### 人

- **`senderUid`**：NT 唯一 id，形如 `u_vUoGgkgkbz3PzpqC3U4NAA`。普通发言都有。系统灰条（`msgType: 5`）会空（本 clip 460 条）。
- **`senderUin`**：QQ 号，同样稳定。本 clip 约 **90** 个有效号，与 uid **基本 1:1**。
- 显示名 **不是** id：`sendNickName` / `sendMemberName`（群名片）/ `sendRemarkName`。同一 uid 在这段时间里有 **24** 人改过名字组合。

`@` 侧：`atType`（常见 2）、`atUid` = QQ 号、`atNtUid` = `u_…`。

### 消息

- **`msgId`**：适合当文档主键（本 clip 全唯一）。
- **`msgSeq`**：群内序号；回复靠它对齐；也适合时间线。
- **`msgTime`**：Unix 秒。
- **`msgRandom`**：辅助去重，不要单独当主键。

### 会话

`chatType: 2` = 群；`peerUid` / `peerUin` = 群号；`peerName` = 群名。

## 内容形态

一条消息可有多个 `elements`（文 + 表情 + 图）。`elementType` 本 clip 出现过：

| type | 含义（按内容判断） | 约计数 |
| --- | --- | --- |
| 1 | 文本 `textElement` | 41417 |
| 2 | 图 `picElement` | 4065 |
| 6 | 表情 `faceElement` | 4365 |
| 7 | 回复 `replyElement` | 5942 |
| 8 | 灰条等 `grayTipElement` | 990 |
| 10 | 卡片 `arkElement` | 175 |
| 16 | 合并转发 `multiForwardMsgElement` | 47 |
| 3 / 4 / 5 / 11 / 21 | 语音 / 视频 / 文件 / markdown 等，少 | — |

`msgType`：2 普通；**9 与回复条数一致**（带引用的消息）；5 灰条。`recallTime != 0` 有 **532** 条撤回。`sourceType: 3` 有 1677 条（导入/同步类标记，入库时当噪声或单独处理）。

## 入库建议

- 人：`senderUid`（空则视为系统号）。
- 消息：`msgId`。
- 回复边：`replayMsgSeq` → `msgSeq`；断链用 `records` + `sourceMsgTextElems`。
- 显示名只作展示，检索/说话人消歧不要当键。
- 本 JSONL 是主源；与 `饮茶室QA/_source` 正文可能重叠，检索时不要两边各吃一遍同一段群聊。
