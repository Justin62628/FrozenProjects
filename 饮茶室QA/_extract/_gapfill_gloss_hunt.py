#!/usr/bin/env python3
"""Hunt earliest JSONL for remaining gloss-only theory notes; dump matches."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonl_io import iter_raw, load_group_specs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
CST = timezone(timedelta(hours=8))

NEEDLES = [
    ("以及Elsa从没明说或者明确暗示过Arendelle女王的身份是束缚", "queen_not_bind"),
    ("既是一个完整的自然之灵也是一个完整的人", "full_spirit_full_human"),
    ("Elsa在冻裂手铐逃离前应该是不知道Hans要来处决她的", "dungeon_hans"),
    ("Love is, putting someone's need before yourself's", "love_permanent_olaf"),
    ("如果小时候有个Jack Frost在旁边引导Elsa", "anti_je"),
    ("双面是动机合集", "two_motive"),
    ("形影不离仍有13年错位", "sister_offset"),
    ("北地若没事却离开", "idle_leave"),
    ("圆焰类比", "info_gap"),
    ("自闭期必须保持信息差", "info_gap2"),
    ("魔法是诅咒还是恩赐", "curse_gift"),
    ("肉体已死、意识靠魔法", "vegetative"),
    ("Noaidi", "noaidi"),
    ("成仙过 N 代也不会丢掉人性面", "keep_human"),
    ("Iduna不是第五灵", "iduna_not_fifth"),
    ("crucial link", "crucial_link"),
    ("Olaf心理", "olaf_psy"),
    ("a place of our own", "place_own"),
    ("Nattmara", "nattmara"),
    ("being a bad Queen", "bad_queen"),
    ("Visa论F2刻画", "visa_f2"),
    ("植物人假设", "vegetative2"),
    ("Elsa在冻裂手铐", "dungeon2"),
    ("女王身份不是束缚", "queen2"),
    ("完整的灵也是完整的人", "full2"),
    ("Fear will be your enemy", "fear_enemy"),
    ("just take care of my sister", "take_care_sister"),
    ("I took an oath to always do what is best for Arendelle, luckily I know just what that is", "oath"),
    ("You belong up here", "belong_up_here"),
    ("Jack Frost", "jack_frost"),
    ("Astrid", "astrid"),
    ("Love is permanent", "love_perm"),
    ("nothing is permanent", "nothing_perm"),
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
            name = ((raw.get("sender") or {}).get("name") or "")
            for needle, key in NEEDLES:
                if needle not in text:
                    continue
                hits[key].append(
                    {
                        "group": spec["key"],
                        "id": str(raw.get("id") or ""),
                        "time": iso_to_cst(raw.get("time") or ""),
                        "name": name,
                        "n": len(text),
                        "head": text[:160].replace("\n", " "),
                    }
                )
    summary = {}
    for key, rows in hits.items():
        rows = sorted(rows, key=lambda x: x["time"] or "9")
        summary[key] = {"n": len(rows), "earliest": rows[0] if rows else None, "all": rows[:8]}
    (DATA / "_gapfill_gloss_hunt.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for key, info in summary.items():
        e = info["earliest"]
        if not e:
            print(f"{key}: NONE")
            continue
        print(f"{key}: n={info['n']} EARLIEST {e['time']} {e['name']} {e['group']}:{e['id']} {e['n']}c | {e['head'][:90]}")


if __name__ == "__main__":
    main()
