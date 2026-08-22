#!/usr/bin/env python3
"""Second patch: remaining gloss→full, recap mappings, decisions."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
DUMP = DATA / "_gapfill_dump"
TODAY = "2026-08-22"


def dump_text(name: str) -> str:
    return (DUMP / name).read_text(encoding="utf-8").rstrip()


def bump(path: Path, text: str) -> None:
    text = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {TODAY}", text, count=1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    # Iduna full English
    p = ROOT / "冰学独立理论与分析/FH：Iduna不是第五灵.md"
    cur = p.read_text(encoding="utf-8")
    start = cur.find("> *2020-08-17")
    if start > 0:
        head = cur[:start]
        body = (
            "2020-08-17 奇谈原文是 canonical（两种读法写在英文正文里）。下面中文短析不要当另一篇。\n\n"
            + dump_text("qitan_6861835687095564028.md")
            + "\n\n两种读法的中文对照：Iduna 从小就是第五灵，她缺席导致四灵连她自己一起罚；或者从来没有第五灵，她尽力修补，灵知道她一个人完不成，才给女儿魔法以免努力作废。"
            "第一种会把灵写成只顾私利，也和后来「真理 / 莎雕前心理」对不上——灵在 Elsa 挡住洪水后仍给 Arendelle 机会，不像纯自利。"
            "母女线的证据链见 [[饮茶室QA/冰学独立理论与分析/FH：母女线分析]]。\n"
        )
        bump(p, head + body)

    # 反对JE: 2020-08-21 + 2020-10-13 canonical
    p = ROOT / "冰学独立理论与分析/FH：反对JE.md"
    cur = p.read_text(encoding="utf-8")
    cur = re.sub(r"time_start: .*", "time_start: 2020-08-21 18:31:32", cur, count=1)
    cur = re.sub(r"出处时间：.*", "出处时间：2020-08-21 18:31:32 → 2024-10-21 18:33:42", cur, count=1)
    i = cur.find("主张：")
    j = cur.find("JE的核心在于")
    head = cur[:i]
    rest_after_essay = ""  # keep nothing of unquoted 2024
    body = (
        "主张：Jack Frost 引导自闭期 Elsa 看似为她着想，实则拆掉 E 线自救、LIG 爆发和姐妹互相依赖。"
        "2020-08-21 表态；2020-10-13 全文是 canonical。2024-10-21 是同一段重发，回指本页。\n\n"
        "## 2020-08-21\n\n"
        + dump_text("tea_6863383047160386053.md")
        + "\n\n## 2020-10-13 全文\n\n"
        + dump_text("tea_discussion_6883124093216941121.md")
        + "\n"
    )
    bump(p, head + body)

    # 废案: replace truncated quote
    p = ROOT / "冰学独立理论与分析/FH：废案a place of our own与议会.md"
    cur = p.read_text(encoding="utf-8")
    # replace the truncated 2021-06 section
    m = re.search(r"### 2021-06 a place of our own\n\n", cur)
    m2 = re.search(r"### 2021-03 议会解散", cur)
    if m and m2:
        section = (
            "### 2021-06 a place of our own\n\n"
            "2021-06-20 原文。下面截断已去掉。\n\n"
            + "\n\n".join(
                [
                    b
                    for b in dump_text("tea_theory_6975732510432996.md").split("\n\n")
                    if "FrozenHeart" in b[:90] and len(b) > 80
                ][:8]
            )
            + "\n\n"
        )
        cur = cur[: m.start()] + section + cur[m2.start()]
        bump(p, cur)

    # 娜雕: childhood insert is 2020-08-07
    p = ROOT / "冰学独立理论与分析/FH：娜雕解冻分析.md"
    cur = p.read_text(encoding="utf-8")
    if "2020-08-07" not in cur:
        cur = cur.replace(
            "然后和上面那段有关的，我再发一下以前写的一段",
            "然后和上面那段有关的，我再发一下以前写的一段（这段 2020-08-07 原文见下节，不要把 10-16 当成童年分析的诞生日期）",
        )
        cur = cur.replace(
            "## 2025-03-18 缩写（回指）",
            "## 2020-08-07 童年 / true love（被 10-16 引用的原文）\n\n"
            + dump_text("tea_6858235705375919022.md")
            + "\n\n## 2025-03-18 缩写（回指）",
        )
        bump(p, cur)

    # EA真爱 pointer already added; strengthen
    p = ROOT / "冰学独立理论与分析/FH：EA不基于欲望的真爱.md"
    cur = p.read_text(encoding="utf-8")
    if "2020-08-07" not in cur:
        cur = cur.replace(
            "「先从EA小时候说起」到 best buddies 那一段，2020-10-16 奇谈原文见",
            "「先从EA小时候说起」到 best buddies 那一段，2020-08-07 原文见 [[饮茶室QA/冰学独立理论与分析/FH：娜雕解冻分析]]（10-16 是重发），2020-10-16 解冻长文见",
        )
        bump(p, cur)

    # 双人格 2021 full
    p = ROOT / "冰学独立理论与分析/FH：双人格与魔法无独立意识.md"
    cur = p.read_text(encoding="utf-8")
    m = re.search(r"## 2021-02 魔法无独立意识\n\n", cur)
    m2 = re.search(r"## 2020-07 奇谈 两个核心矛盾", cur)
    if m and m2:
        cur = cur[: m.end()] + dump_text("tea_6934037639537970056.md") + "\n\n" + cur[m2.start()]
        bump(p, cur)

    # 机制碎片 ZQ full
    p = ROOT / "冰学讨论/机制与人物碎片.md"
    cur = p.read_text(encoding="utf-8")
    cur = re.sub(
        r"### 2020-04 ZQ\n\n> \*2020-04-02 16:03:26.+?(?=\n### )",
        "### 2020-04 ZQ\n\n" + dump_text("qitan_6811021872596920785.md") + "\n\n",
        cur,
        count=1,
        flags=re.S,
    )
    bump(p, cur)

    # decisions extra flips
    dec = json.loads((DATA / "decisions.json").read_text(encoding="utf-8"))
    extra = {
        "tea:discussion:6883124093216941121": ("keep_theory", "反对JE 2020-10-13 原文"),
        "tea:theory:7502392269696835339": ("keep_theory", "反对JE 2024 重发，回指 2020-10-13"),
        "tea:theory:6975732510432996": ("keep_theory", "a place of our own 2021-06 原文"),
        "tea:theory:7409476223054358458": ("keep_theory", "You have no right 2024 重发，回指 2020-05-19"),
        "klein:discussion:7541742635693026833": ("keep_discussion", "女王是否开心 2025-08"),
        "tea:theory:7690081352341945247": ("keep_theory", "Love is permanent 2026-03"),
        "qitan:theory:6861835687095564028": ("keep_theory", "Iduna不是第五灵 2020-08-17"),
    }
    flipped = 0
    for cid, (v, n) in extra.items():
        prev = (dec["decisions"].get(cid) or {}).get("verdict")
        dec["decisions"][cid] = {"verdict": v, "note": n}
        if prev == "reject":
            flipped += 1
    tmp = DATA / "decisions.json.tmp"
    tmp.write_text(json.dumps(dec, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA / "decisions.json")
    print("extra flipped", flipped)


if __name__ == "__main__":
    main()
