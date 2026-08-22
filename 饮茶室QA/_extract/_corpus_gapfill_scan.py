#!/usr/bin/env python3
"""Scan rejects/later + notes for gap-fill: fanfic, recaps, gloss-only keepers."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ROOT = HERE.parent
CST = timezone(timedelta(hours=8))

FANFIC_CUE = re.compile(
    r"Once upon a time|back-?story|fanart|fanfic|同人|纯属虚构|"
    r"Remember when we were little|Put me down, Nokk|"
    r"The sky was awake|Our story began with the royal sisters|"
    r"Kristoff was folding|I've linked this big boy|"
    r"Sunlight pierced through|Anna was wakened|"
    r"Elsa flicked her fingers|towards the darkness she went|"
    r"Winter's gone and Spring is springing|"
    r"水兵可可|深潜者|后记|"
    r"手挽手步入|告阿伦戴尔全党|"
    r"Queen Anna of Arendelle sat|"
    r"Interesting fanart|"
    r"Let's see whether we can make up",
    re.I,
)
NSFW_CUE = re.compile(
    r"黄图|涩图|r18|nsfw|约稿|胸型|浴室的地板|scissoring|tribadism|"
    r"Vibrator|sex toy|青涩的胸型|少女跌坐",
    re.I,
)
RECAP_CUE = re.compile(
    r"我在\s*\d{2,4}\s*年.{0,12}(写过|提过|分析过|理论)|"
    r"我(以前|之前|早就|当年).{0,16}(写过|提过|分析过|发过)|"
    r"20年的理论|21年的理论|2020年.{0,8}(写过|发过)|"
    r"我上次(写|发)过|重发一下以前|"
    r"结合我之前的|我之前提出的|我之前分析|"
    r"这段之前的理论|以前写的一段",
)
NUMBERED_CUE = re.compile(
    r"(?:^|\n)\s*(?:\d+[\.、\)］)]|[一二三四五六七八九十]+[、.])\s*\S{20,}",
)
BRAINHOLE_CUE = re.compile(r"脑洞|瞎编|瞎想|胡思乱想|纯属瞎")
ANALYSIS_CUE = re.compile(
    r"分析|理论|机制|人设|心理|双桥|莎雕|娜雕|第五灵|Ahtohallan|"
    r"conceal|Fear vs Love|解冻|act of true love",
    re.I,
)
FROZEN_CUE = re.compile(
    r"Elsa|Anna|Ahtohallan|Athl|阿塔霍|第五灵|莎雕|娜雕|双桥|Northuldra|"
    r"Frozen|冰雪|Iduna|Runeard|Hans|Kristoff|Olaf|Arendelle|"
    r"\bF1\b|\bF2\b|\bF3\b|\bPN\b|\bFOS\b|\bITU\b|\bOFA\b",
    re.I,
)
GLOSS_MARK = re.compile(r"[…⋯](?:\s*$)")


def iso_to_cst(iso: str) -> str:
    if not iso:
        return ""
    s = iso.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return iso.replace("T", " ")[:19]


def hay_of(c: dict, cap: int = 12000) -> str:
    parts = [c.get("preview") or "", c.get("author_name") or ""]
    n = 0
    for m in c.get("messages") or []:
        if m.get("role") == "ctx":
            continue
        t = (m.get("text") or "").strip()
        parts.append(t)
        n += len(t)
        if n >= cap:
            break
    return "\n".join(parts)


def longest_chat(c: dict) -> tuple[int, str, str]:
    best_n, best_t, best_name = 0, "", ""
    for m in c.get("messages") or []:
        if m.get("role") in ("ctx",):
            continue
        t = (m.get("text") or "").strip()
        if len(t) > best_n:
            best_n = len(t)
            best_t = t
            best_name = m.get("name") or c.get("author_name") or ""
    return best_n, best_t, best_name


def body_chars(c: dict) -> int:
    n = 0
    for m in c.get("messages") or []:
        if m.get("role") == "ctx":
            continue
        n += len((m.get("text") or "").strip())
    return n


def classify_reject(c: dict, dec: dict) -> dict:
    hay = hay_of(c)
    n, longest, who = longest_chat(c)
    bc = body_chars(c)
    note = (dec.get("note") or "")
    flags = []
    if NSFW_CUE.search(hay) and (not FROZEN_CUE.search(hay[:800]) or re.search(r"浴室|胸型|scissoring|tribadism", hay, re.I)):
        flags.append("nsfw")
    if FANFIC_CUE.search(hay):
        flags.append("fanfic")
    if RECAP_CUE.search(hay):
        flags.append("recap")
    if NUMBERED_CUE.search(longest) and n >= 400:
        flags.append("numbered")
    if BRAINHOLE_CUE.search(hay) and ANALYSIS_CUE.search(hay) and n >= 300:
        flags.append("brainhole_analysis")
    if n >= 800 and FROZEN_CUE.search(hay) and "essay" in (c.get("reasons") or []):
        flags.append("long_essay")
    if n >= 1200 and FROZEN_CUE.search(hay):
        flags.append("long_frozen")
    if "同人" in note or "fanfic" in note.lower() or "脑洞" in note:
        flags.append("note_says_fanfic")
    frozen = bool(FROZEN_CUE.search(hay))
    return {
        "id": c["id"],
        "author": c.get("author_name"),
        "group": c.get("group"),
        "time": iso_to_cst(c.get("time_start") or ""),
        "verdict": dec.get("verdict"),
        "note": note[:120],
        "n_msgs": c.get("n_msgs"),
        "body_chars": bc,
        "longest": n,
        "preview": (c.get("preview") or "")[:160].replace("\n", " "),
        "longest_head": longest[:180].replace("\n", " "),
        "flags": flags,
        "frozen": frozen,
        "reasons": c.get("reasons") or [],
    }


def scan_notes() -> list[dict]:
    rows = []
    for folder in ["核心", "冰学独立理论与分析", "冰学讨论", "其他", "同人"]:
        d = ROOT / folder
        if not d.is_dir():
            continue
        for p in d.rglob("*.md"):
            if p.name.startswith("MOC"):
                continue
            text = p.read_text(encoding="utf-8")
            n = len(text)
            ell = text.count("…") + text.count("⋯")
            gloss_heads = len(re.findall(r"^主张：", text, re.M))
            quote_blocks = len(re.findall(r"^> \*\d{4}-\d{2}-\d{2}", text, re.M))
            truncated_quotes = 0
            for m in re.finditer(r"(^> .+(?:\n>.*)*)", text, re.M):
                block = m.group(1)
                if block.rstrip().endswith("…") or block.rstrip().endswith("…"):
                    truncated_quotes += 1
                if "…" in block[-8:]:
                    truncated_quotes += 1
            rows.append(
                {
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "n": n,
                    "ell": ell,
                    "quote_blocks": quote_blocks,
                    "truncated_quotes": truncated_quotes,
                    "has_主张": gloss_heads > 0,
                }
            )
    return rows


def main() -> None:
    cands_obj = json.loads((DATA / "candidates.json").read_text(encoding="utf-8"))
    cands = {c["id"]: c for c in cands_obj["candidates"]}
    decs = json.loads((DATA / "decisions.json").read_text(encoding="utf-8"))["decisions"]

    by_v = Counter(d.get("verdict") for d in decs.values())
    rescues = []
    recaps = []
    later_text = []
    for cid, dec in decs.items():
        v = dec.get("verdict")
        c = cands.get(cid)
        if not c:
            continue
        if v == "reject":
            rec = classify_reject(c, dec)
            if rec["flags"] or (rec["frozen"] and rec["longest"] >= 600):
                rescues.append(rec)
        elif v == "later":
            n, longest, _ = longest_chat(c)
            if n >= 200 and FROZEN_CUE.search(hay_of(c, 4000)):
                later_text.append(
                    {
                        "id": cid,
                        "author": c.get("author_name"),
                        "time": iso_to_cst(c.get("time_start") or ""),
                        "longest": n,
                        "preview": (c.get("preview") or "")[:160].replace("\n", " "),
                        "note": (dec.get("note") or "")[:80],
                        "files": c.get("files") or [],
                    }
                )
        if c and RECAP_CUE.search(hay_of(c, 8000)):
            recaps.append(
                {
                    "id": cid,
                    "verdict": v,
                    "author": c.get("author_name"),
                    "time": iso_to_cst(c.get("time_start") or ""),
                    "preview": (c.get("preview") or "")[:160].replace("\n", " "),
                    "longest": longest_chat(c)[0],
                }
            )

    notes = scan_notes()
    notes_trunc = [x for x in notes if x["truncated_quotes"] or (x["n"] < 2500 and x["has_主张"])]

    out = {
        "verdicts": dict(by_v),
        "n_reject_flagged": len(rescues),
        "rescues": sorted(rescues, key=lambda x: (-x["longest"], x["time"])),
        "n_later_text": len(later_text),
        "later_text": sorted(later_text, key=lambda x: -x["longest"]),
        "n_recaps": len(recaps),
        "recaps": sorted(recaps, key=lambda x: x["time"] or "9"),
        "notes_trunc": notes_trunc,
        "notes_all": notes,
    }
    (DATA / "_gapfill_scan.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        f"verdicts={dict(by_v)}",
        f"reject flagged={len(rescues)} later_text={len(later_text)} recaps={len(recaps)} notes_trunc={len(notes_trunc)}",
        "",
        "## REJECT RESCUES (flags or long frozen)",
    ]
    flag_c = Counter()
    for r in rescues:
        for f in r["flags"] or ["long_frozen_unflagged"]:
            flag_c[f] += 1
    lines.append(str(dict(flag_c)))
    for r in rescues[:80]:
        lines.append(
            f"- {r['longest']:5d}c {r['time']} {r['author']} {r['id']} flags={r['flags']} | {r['preview'][:90]}"
        )
    lines.append("\n## LATER WITH TEXT")
    for r in later_text[:40]:
        lines.append(f"- {r['longest']:5d}c {r['time']} {r['author']} {r['id']} | {r['preview'][:90]}")
    lines.append("\n## RECAPS")
    for r in recaps:
        lines.append(f"- [{r['verdict']}] {r['time']} {r['author']} {r['id']} {r['longest']}c | {r['preview'][:90]}")
    lines.append("\n## NOTES TRUNC/GLOSS")
    for r in notes_trunc:
        lines.append(f"- {r['n']:6d}c ell={r['ell']} q={r['quote_blocks']} trunc={r['truncated_quotes']} 主张={r['has_主张']} {r['path']}")
    (DATA / "_gapfill_scan.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:40]))
    print("wrote", DATA / "_gapfill_scan.txt")


if __name__ == "__main__":
    main()
