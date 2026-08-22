#!/usr/bin/env python3
"""Hunt JSONL for recap pointers and earliest originals of known theory phrases."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonl_io import iter_raw, load_group_specs

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CST = timezone(timedelta(hours=8))

NEEDLES = [
    ("母女线是最重要的暗线", "mother_line"),
    ("我找到Ahtohallan冻住Elsa的原因了", "athl_freeze"),
    ("Once upon a time , a dark lord", "once_upon"),
    ("Interesting fanart. Let's see whether we can make up", "huldre_fanart"),
    ("The Northuldra follow magic, which means we can never trust them", "runeard"),
    ("damn.......我这次分析竟然重新回到了那个F1的终极问题", "thaw_2020"),
    ("关于F1如何解冻这里我在20年的理论里写到过一段", "thaw_recap"),
    ("The wind is restless", "itu_wind"),
    ("@Vivian 你要的解释", "vivian"),
    ("Remember when we were little, mother and father", "remember"),
    ("I've linked this big boy", "ice_construct"),
    ("Anna was wakened by the creak", "anna_wakened"),
    ("Elsa flicked her fingers, snowflakes", "elsa_flicked"),
    ("Sunlight pierced through the thick curtains", "sunlight"),
    ("Kristoff was folding his arm", "kristoff_folding"),
    ("Elsa's morning activities", "elsa_morning"),
    ("Elsa let me down! Kristoff is going to be back soon", "elsa_let_me_down"),
    ("I'm going to send you from heaven to hell", "heaven_hell"),
    ("Our story began with the royal sisters of Arendelle", "our_story"),
    ("The sky was awake. Green and pink ribbons", "sky_awake"),
    ("水兵可可的一生", "ke_ke"),
    ("我感觉Elsa的思维似乎分两部分", "two_mind"),
    ("Elsa分两个人格", "two_persona"),
    ("Elsa的魔法是没有自己的独立意识的", "no_magic_mind"),
    ("全篇一个重要线索是Find the truth", "truth_theory"),
    ("我现在有个没完全成型的假说，先写下来", "conceal_hyp"),
    ("首先依旧要强调一下Elsa的conceal", "conceal_202006"),
    ("That's just your fear说明她已看穿祖父", "runeard_2021"),
    ("Fear 和 Love 具体化这点提的太好了", "fear_love_concrete"),
    ("You have no right to claim Elsa's yours", "no_claim"),
    ("This year is one of the most important milestones in Arendelle history", "milestone"),
    ("Winter's gone and Spring is springing", "winter_spring"),
    ("那天是星期五，A和k正悠闲地走在阿伦戴尔的大街上", "charades_rp"),
    ("昨晚，我梦到自己来到了很多年以后的阿伦黛尔", "frozenxx_dream"),
    ("童话的魔女，性质为改编", "fairy_witch"),
    ("我在20年的理论", "in_2020_theory"),
    ("我在21年", "in_2021"),
    ("我以前写过", "i_wrote_before"),
    ("我之前提出的双桥", "two_bridge_recap"),
]


def iso_to_cst(iso: str) -> str:
    t = iso or ""
    if not t:
        return ""
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return t[:19]


def main() -> None:
    specs = load_group_specs()
    hits = {k: [] for _, k in NEEDLES}
    for spec in specs:
        if spec["key"] == "klein":
            continue
        print("scan", spec["key"], file=sys.stderr)
        for raw in iter_raw(spec["root"]):
            text = ((raw.get("content") or {}).get("text") or "")
            if not text:
                continue
            for needle, key in NEEDLES:
                if needle not in text:
                    continue
                s = raw.get("sender") or {}
                hits[key].append(
                    {
                        "group": spec["key"],
                        "id": str(raw.get("id") or ""),
                        "time": iso_to_cst(raw.get("time") or ""),
                        "name": s.get("name") or "",
                        "n": len(text),
                        "head": text[:140].replace("\n", " "),
                    }
                )
    # earliest per key
    summary = {}
    for key, rows in hits.items():
        rows = sorted(rows, key=lambda x: x["time"] or "9")
        summary[key] = {
            "n": len(rows),
            "earliest": rows[0] if rows else None,
            "all": rows[:12],
        }
    out = DATA / "_gapfill_hunt.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = []
    for key, info in summary.items():
        e = info["earliest"]
        if not e:
            lines.append(f"{key}: NONE")
            continue
        lines.append(
            f"{key}: n={info['n']} EARLIEST {e['time']} {e['name']} {e['group']}:{e['id']} {e['n']}c | {e['head'][:80]}"
        )
        if info["n"] > 1:
            for r in info["all"][1:6]:
                lines.append(f"    {r['time']} {r['name']} {r['group']}:{r['id']} {r['n']}c")
    print("\n".join(lines))
    print("wrote", out, file=sys.stderr)


if __name__ == "__main__":
    main()
