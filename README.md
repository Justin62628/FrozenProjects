---
title: Frozen / 饮茶室 README
tags:
  - type/howto
  - area/frozen
status: active
updated: 2026-08-22
---

# Frozen / 饮茶室 — 规范与踩坑

本目录是独立 RAG 库（目前只有饮茶室QA）。入口：[[MOC-Frozen]]。笔记索引：[[饮茶室QA/MOC-饮茶室QA]]。

群聊原始导出（NTQQ JSONL）字段与回复链：[[NOTE-QQChat-JSONL]]。

下一步是**集中理论分析提取**：从已拆好的原文笔记里抽出可单独引用的论点，写成新笔记并回链，不要覆盖源文档。

## 目录角色

| 路径 | 用途 |
| --- | --- |
| `MOC-Frozen.md` | RAG 根索引 |
| `饮茶室QA/MOC-饮茶室QA.md` | 主题地图（核心 / 独立理论 / 讨论 / 其他） |
| `饮茶室QA/核心/` | 新人稳妥 FAQ、群规、缩写、可单独成册的理论（如双桥） |
| `饮茶室QA/冰学独立理论与分析/` | 单人成文、系统问答 |
| `饮茶室QA/冰学讨论/` | 多声部辩论、群聊记录 |
| `饮茶室QA/其他/` | 资料性短文、占位 |
| `饮茶室QA/assets/` | 从 `data:image` 抽出的图；相对引用，子目录用 `../assets/` |
| `饮茶室QA/_source/` | 原文 dump，`rag: skip`，**禁止 git 追踪、禁止作为检索主源** |
| `NOTE-QQChat-JSONL.md` | QQChatExporter JSONL 字段说明（回复链、发送人 id）；源文件在本机 exports，不进本库 |

分类原则（原文编辑方针）：核心 FAQ 给争议较少的稳妥答；文本 / 创作 / 世界观 / 观众互有指涉，新内容先定侧重点再落文件夹。

## Markdown 规范

1. 正文第一个标题必须是 `#`（MD041）。YAML 可以在它前面。
2. 标题里不要写 `**`。错误：`## **双桥理论**`、`## **关于****冰****二****`。正确：`# 双桥理论`、`## 关于冰二的Ahtohallan`。
3. 一篇笔记一个 H1；小节用 `##` / `###`，不要跳级（`#` 下面直接 `###`）。
4. 过长的聊天句不要当 H1（会变成标题噪声）。改成短标题，原句留在正文。
5. 空标题（只有 `##`）删掉。
6. 每篇加 YAML：`title`、`area`、`source`、`tags`（`type/ref` + `area/frozen`）。`title:` 含 ASCII 冒号时加引号。
7. 链接用 Obsidian wikilink：`[[饮茶室QA/核心/双桥理论]]`。
8. 裸 URL 写成 `<https://example.com>`（MD034）。
9. 只有粗体的一行如果其实是小节名，改成真正的标题（MD036），不要留 `**Klein：第五灵的新理解**`。
10. 改完在本目录跑 markdownlint。配置见 `.markdownlint.json`。

本库关闭 **MD013**（行宽 80）：源材料是群聊/长段，硬折行等于改写。YAML 的 `title` 与正文 `#` 不要被算成两个 H1：配置里 `MD025` / `MD041` 的 `front_matter_title` 设为空串。

## Git / 资源

仓库根 `.gitignore` 已有 `*.png` / `*.jpg` / `**/_source/`。因此：

- 抽出的 `assets/*.png` 默认不进 git。
- `_source/` 不进 git。不要把 dump 再拷回 `MOC-饮茶室QA.md`。
- 根 ignore 含 `.*`，点文件（如 `.markdownlint.json`）可能不被提交；本地编辑器仍会读到。

## 工具

在 `饮茶室QA/` 下：

```bash
python extract_data_images.py path/to/note.md
python split_qa_notes.py --dry-run
python split_qa_notes.py --normalize-headings
python _extract/extract_fragments.py
python _extract/review_server.py
python _extract/copy_range.py FOLDER --start "起始全文" --end "结束全文"
```

群聊片段筛选：先跑 `extract_fragments.py` 写出 `_extract/data/candidates.json`，再开 `review_server.py` 人工标。判定存在 `_extract/data/decisions.json`，重跑提取不会覆盖已有判定（按 candidate id 对齐）。跨群靠合并转发，见 [[NOTE-QQChat-JSONL]]。

按起止记录抽一段对话（默认复制到剪贴板；时间转北京时间；含两端）。发送头与被引用气泡写成 Markdown 引用+斜体；图片、撤回、空文本整段略过。`--start` / `--end` 必须是该条 `content.text` 的完全文本（去空白后全等）。FOLDER 是 QQChatExporter 的 `*_chunked_jsonl` 目录：

```bash
python _extract/copy_range.py "E:\Library\Documents\QQChatExporter\exports\group_冰学三点饮茶室_732870642_20260822_060117249_chunked_jsonl" --start "AT Field. Absolute Terror Field" --end "那块显然各有大神做了，也不管了"
```

可选：`-o slice.md` 同时落盘，`--print` 打到 stdout，`--no-clipboard` 不写剪贴板，`--contains` 改成子串匹配。中文路径下先设 `PYTHONIOENCODING=utf-8`。

格式化与检查（在 ``）：

```bash
npx --yes prettier@3 --write --prose-wrap preserve "**/*.md"
npx --yes markdownlint-cli2 --config .markdownlint.json "**/*.md"
```

Prettier 必须加 `--prose-wrap preserve`，否则会重排中文长段。Prettier **不会**去掉标题里的 `**`，标题清洗用 `--normalize-headings`。

`split_qa_notes.py` 无参数会按行号从 `_source` **复制**切片并覆盖子笔记与两个 MOC。MOC 已改成索引、或子笔记有手工修改之后，不要无参数重跑，只用 `--normalize-headings`。

## 踩过的坑

### 1. `data:image` 会把笔记撑到数 MB

原文曾约 5.8MB，三张 PNG 内嵌 base64。必须先抽到 `assets/`，再改相对路径。抽完后再拆文件，否则行号工具和编辑器都会卡。拆到子目录后，链接是 `../assets/xxx.png`，不是 `assets/xxx.png`。

### 2. 拆分要复制，不要重写

源是群聊/专栏拼贴，错字、零宽空格、断行都是原文。按行号切片复制，只允许加 YAML 和改标题层级。用模型「整理成通顺文章」会毁掉可引用性。

### 3. OneNote / 富文本标题

常见形态：`## **标题**`、标题被拆成多段 `**`、H1 包一层分区名（「冰学讨论：文本」）而真正内容在 H2。markdownlint 的 MD041 看的是「正文第一个标题是不是 `#`」，不是「看起来像标题的粗体」。

### 4. YAML `title` 与 MD025

给每篇加 `title:` 之后，默认 markdownlint 会把 YAML title 也当成 H1，于是和正文 `#` 冲突（MD025）。必须在 `.markdownlint.json` 里把 `front_matter_title` 关掉，同时保留正文 `#`。

### 5. 标题升级会跳级

把唯一的 `##` 升成 `#` 后，原来的 `###` 会悬空。升一级时要把下级一起升（`###` → `##`）。

### 6. 编号列表被段落切断

原文「1. 2. 3. 4.」提纲后面又出现孤立的 `4.`，markdownlint MD029 会报。这种「第 4 点」改成 `（4）` 正文，不要当新的有序列表。

### 7. 检索重复

`_source` 与子笔记正文重复。RAG 只索引子笔记；dump 标 `rag: skip`。提取出的理论笔记也要链回源笔记，不要再贴一整段源文。

### 8. 控制台编码

Windows PowerShell 默认 GBK，中文路径/emoji 标题打印会炸。脚本输出用 `PYTHONIOENCODING=utf-8`。

## QQ JSONL 主源（摘要）

完整字段见 [[NOTE-QQChat-JSONL]]。clip 抽样结论（2026-08-22）：

- **支持回复。** `elements[].replyElement`（`elementType: 7`），本 clip 5942/38418。连边用 `replayMsgSeq` → `msgSeq`，断链用本条 `records[]` + `sourceMsgTextElems`。不要用几乎总是 `"0"` 的 `replayMsgId` 对顶层 `msgId`。
- **人的主键是 `senderUid`（`u_…`）和 `senderUin`（QQ 号）**，基本 1:1。群名片/昵称会变，不当 id。`replyElement.senderUid` 实际是 QQ 号，NT uid 在 `senderUidStr`。
- 消息主键 `msgId`；时间 `msgTime`（Unix 秒）。系统灰条可能空 uid。

源文件在 `e:\Library\Documents\QQChatExporter\exports\` 的 spool jsonl，不进 git。

## 下一步：理论分析提取

目标：从「讨论/长文」里抽出**可单独检索、可单独引用**的论点，供 Agent 回答常见问题。

建议约定：

1. **源笔记只读。** 提取结果写成新文件，不覆盖 `核心/` `冰学讨论/` 里的原文切片。
2. **落点。** 稳定、群内引用多的具名理论 → `核心/` 或 `冰学独立理论与分析/`；从辩论里抽的单点结论 → `冰学独立理论与分析/`，并在文内链回讨论页。
3. **一则一义。** 一篇提取笔记只陈述一个命题（例如「第五灵是职位不是物种」「莎雕是 Athl 考验」），开头用一段话写清主张、提出者、与哪些笔记冲突。
4. **必填。** YAML `source` 指向原切片；`related` 指向 FAQ / 双桥 / 对立观点。正文用引述 + 出处，不整篇复制群聊。
5. **立场分开。** FH 永生论与游鱼反驳不要捏成一篇「综合结论」，除非明确写「争议地图」。
6. **过 lint。** 新笔记同样遵守上文 Markdown 规范后再收进 MOC。

优先提取候选（已在库中、引用密度高）：

- 双桥理论（人与自然之桥 / Elsa 人性与魔法之桥）
- Ahtohallan 的定义与是否「神」
- 第五灵：职位 vs 成仙；考核 vs 引导 vs gift
- 莎雕：考验论 / 不可接受论 / 解冻空白
- PN 对 F2 离开与 True Love 的补全
- F2 刻画缺失（ITU 前探索欲望被吞）

提取完成后：更新 [[饮茶室QA/MOC-饮茶室QA]] 增加「理论提取」节，并给 [[MOC-Frozen]] 的 `updated` 打日期。
