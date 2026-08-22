#!/usr/bin/env python3
"""Compact unmarked-candidate index for the 2026-08-22 full pass."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
CAND = DATA / "candidates.json"
DEC = DATA / "decisions.json"
OUT = DATA / "_unmarked_index.json"
OUT_TXT = DATA / "_unmarked_preview.txt"
VAULT_CORPUS = DATA / "_vault_corpus.txt"

STRUCT_RE = re.compile(
    r"结构主义|叙事学|叙述学|质感|设定层级|机制杀|闭环|和声终止|叙事功能|母题|"
    r"深层结构|单盒|双盒|功能项|普罗普|格雷马斯|符号矩阵|类型系统|类型片|"
    r"叙事闭合|闭合感|成立感|黑箱|观众心理|接受美学|结构主义作者",
    re.I,
)
COMP_RE = re.compile(
    r"宫崎骏|幽灵公主|小圆|魔圆|madoka|toy story|玩具总动员|moana|海洋奇缘|"
    r"rapunzel|tangled|乐佩|中土|霍比特|魔戒|哈利波特|\bhp\b|zootopia|疯狂动物城|"
    r"星际穿越|interstellar|天空之城|双城|萨满|noaidi|基督教|神学|公主片|"
    r"visa|比较|对照|对标|联立|同构|互文|迪皮|迪士尼公主|千与千寻|龙猫|"
    r"风之谷|哈尔|魔女宅急便|sekai|世界计划|动物农场|animal farm|"
    r"冰与火|权力的游戏|冰火|指环王|纳尼亚|狮子王|花木兰|阿拉丁|小美人鱼|"
    r"寻梦环游记|coco|头脑特工|inside out|超能陆战队|无敌破坏王|"
    r"冰雪女王|安徒生|格林童话|神话|萨迦|北欧神话|芬兰|卡勒瓦拉|"
    r"千与千寻|幽灵|米娅水崎|押井守|新海诚|你的名字|天气之子|"
    r"EVA|eva|福音战士|凉宫|物语系列|命运石之门|进击的巨人|"
    r"冰封王座|魔兽|塞尔达|塞尔达传说|王国之泪|"
    r"比较文学|互文性|原型批评|荣格|坎贝尔|英雄之旅",
    re.I,
)
JUNK_RE = re.compile(
    r"黄图|涩图|r18|nsfw|色图|约稿价格|红包|管理员|禁言|踢人|"
    r"今晚吃|约饭|外卖|打游戏|开黑|lol排名|原神抽卡",
    re.I,
)
AUTHOR_KEEP = re.compile(
    r"FrozenHeart|^FH$|土豆|JU|Klein|克莱恩|游鱼|纳西妲|ZQ|北寻|新约|几内亚|Visa|"
    r"Minich|隔壁老王|Dem|Snowflake|发粪涂墙",
    re.I,
)


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def vault_text() -> str:
    parts = []
    for folder in (
        ROOT / "核心",
        ROOT / "冰学讨论",
        ROOT / "冰学独立理论与分析",
        ROOT / "其他",
    ):
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            parts.append(f"\n\n###FILE {p.relative_to(ROOT).as_posix()}\n")
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def main() -> None:
    cands_obj = load_json(CAND, {})
    cands = cands_obj.get("candidates", cands_obj) if isinstance(cands_obj, dict) else cands_obj
    if isinstance(cands, dict):
        cands = list(cands.values())
    dec_obj = load_json(DEC, {})
    decs = dec_obj.get("decisions", dec_obj) if isinstance(dec_obj, dict) else {}

    by_v = Counter()
    for d in decs.values():
        by_v[(d or {}).get("verdict") or "empty"] += 1

    unmarked = []
    marked_ids = {k for k, v in decs.items() if (v or {}).get("verdict")}
    last_agent_rejects = []
    user_style_rejects = []
    for c in cands:
        cid = c["id"]
        d = decs.get(cid) or {}
        v = d.get("verdict") or ""
        if not v:
            unmarked.append(c)
            continue
        note = (d.get("note") or "")
        if v == "reject" and re.search(r"同人|脑洞|二创", note):
            last_agent_rejects.append(
                {
                    "id": cid,
                    "note": note[:200],
                    "author": c.get("author_name"),
                    "preview": (c.get("preview") or "")[:160],
                    "time": c.get("time_start"),
                    "kind": c.get("kind"),
                    "group": c.get("group"),
                }
            )
        if v == "reject" and (not note or note in ("", "用户拒绝", "reject")):
            user_style_rejects.append(cid)

    corpus = vault_text()
    VAULT_CORPUS.write_text(corpus, encoding="utf-8")

    rows = []
    struct_hits = []
    comp_hits = []
    for c in unmarked:
        preview = c.get("preview") or ""
        msgs = c.get("messages") or []
        # don't dump full messages; take author+times+first 80 of each non-ctx
        snippets = []
        authors = []
        total_chars = 0
        for m in msgs:
            if m.get("role") == "ctx":
                continue
            t = (m.get("text") or "").strip()
            total_chars += len(t)
            if m.get("name"):
                authors.append(m["name"])
            if t and len(t) >= 40:
                snippets.append(t[:80])
            if len(snippets) >= 4:
                break
        hay = preview + "\n" + "\n".join(snippets)
        # overlap: distinctive 24-char window from preview
        overlap = ""
        needle = re.sub(r"\s+", "", preview)[:80]
        if len(needle) >= 24:
            for i in range(0, max(1, len(needle) - 23), 12):
                n = needle[i : i + 24]
                if n and n in corpus.replace("\n", "").replace(" ", ""):
                    overlap = "vault_overlap"
                    break
        flags = []
        if STRUCT_RE.search(hay) or STRUCT_RE.search(preview):
            flags.append("struct")
            struct_hits.append(c["id"])
        if COMP_RE.search(hay) or COMP_RE.search(preview):
            flags.append("comp")
            comp_hits.append(c["id"])
        if JUNK_RE.search(hay):
            flags.append("junkish")
        if AUTHOR_KEEP.search(c.get("author_name") or ""):
            flags.append("named")
        files = c.get("files") or []
        if files and total_chars < 40:
            flags.append("attach_only")
        year = (c.get("time_start") or "")[:4]
        row = {
            "id": c["id"],
            "kind": c.get("kind"),
            "group": c.get("group"),
            "author": c.get("author_name"),
            "time": (c.get("time_start") or "")[:19],
            "n_msgs": c.get("n_msgs"),
            "n_fwd": c.get("n_forwarded"),
            "chars": total_chars,
            "files": files,
            "reasons": c.get("reasons"),
            "flags": flags,
            "overlap": overlap,
            "preview": preview[:180],
            "snips": snippets[:3],
        }
        rows.append(row)

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    by_group = Counter(r["group"] for r in rows)
    by_kind = Counter(r["kind"] for r in rows)
    by_year = Counter((r["time"] or "")[:4] for r in rows)
    by_author = Counter(r["author"] for r in rows)
    flag_c = Counter(f for r in rows for f in r["flags"])

    lines = []
    lines.append(f"n_candidates={len(cands)}")
    lines.append(f"n_decision_keys={len(decs)}")
    lines.append(f"verdicts={dict(by_v)}")
    lines.append(f"n_unmarked={len(rows)}")
    lines.append(f"by_group={dict(by_group)}")
    lines.append(f"by_kind={dict(by_kind)}")
    lines.append(f"by_year={dict(by_year)}")
    lines.append(f"flags={dict(flag_c)}")
    lines.append(f"struct={len(struct_hits)} comp={len(comp_hits)}")
    lines.append(f"same_theme_tongren_rejects={len(last_agent_rejects)}")
    lines.append(f"empty_note_rejects={len(user_style_rejects)}")
    lines.append("\nTOP AUTHORS unmarked:")
    for a, n in by_author.most_common(30):
        lines.append(f"  {n:4d}  {a}")
    lines.append("\n=== STRUCT ===")
    for r in rows:
        if "struct" in r["flags"]:
            lines.append(f"{r['id']}\t{r['time']}\t{r['author']}\t{r['chars']}\t{r['preview'][:100]}")
    lines.append("\n=== COMP ===")
    for r in rows:
        if "comp" in r["flags"]:
            lines.append(f"{r['id']}\t{r['time']}\t{r['author']}\t{r['chars']}\t{r['preview'][:100]}")
    lines.append("\n=== NAMED long (>=200 chars) no overlap ===")
    for r in rows:
        if "named" in r["flags"] and r["chars"] >= 200 and not r["overlap"]:
            lines.append(f"{r['id']}\t{r['kind']}\t{r['time']}\t{r['author']}\t{r['chars']}\t{r['preview'][:90]}")
    lines.append("\n=== TONGREN REJECTS TO GLANCE ===")
    for x in last_agent_rejects[:80]:
        lines.append(f"{x['id']}\t{x['time']}\t{x['author']}\t{x['note']}\t{x['preview'][:80]}")
    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT_TXT.read_text(encoding="utf-8")[:8000])
    print("\n... wrote", OUT, "n=", len(rows))


if __name__ == "__main__":
    main()
