#!/usr/bin/env python3
"""Re-reject leaked junk among keepers; dump good quotes for note filing."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

JUNK_KEEP = re.compile(
    r"可可无奈|岚姐电话|神目|性转|少女跌坐|青涩的胸型|小蜥蜴哇的一声|"
    r"小v挽着小蜥蜴|Vibrators are one of the most popular|"
    r"Hainosaurus|orogeny of the Rocky Mountains|"
    r"magnet:\?xt=|archiveofourown\.org/works/search|"
    r"关于我的艳史|The snow glows white on the mountain|"
    r"Every inch of me is trembling|"
    r"Elsa's morning activities|Elsa let me down! Kristoff|"
    r"icy blades sank into her back|"
    r"Product Details With the Olaf doll|"
    r"最长白昼的祝福|夏至的阳光漫过|"
    r"EA百合的成果被层层打开|"
    r"水兵可可的一生|There once was a troll|"
    r"Put me down, Nokk|"
    r"理解了～周末兄|"
    r"丧尸世界，我是吼姆拉|"
    r"Winter Festival, kids can help|"
    r"Hello 你好 It's Elsa|"
    r"See The Sky\s+Mattias|"
    r"A Warm Welcome: Olaf hears|"
    r"Elsa awoke with a jolt|"
    r"Stuck upside down to the corridor|"
    r"欧洲的\*\*古典原子论\*\*|"
    r"东亚地区，大部分动物为了确保幼崽|"
    r"Idina Menzel has recently revealed what she regretted",
    re.I,
)
STILL_FANFIC = re.compile(
    r"纯属虚构|Once upon a time|Kristoff was folding|"
    r"I've linked this big boy|Sunlight pierced through|"
    r"Anna was wakened by the creak|Elsa flicked her fingers|"
    r"Remember when we were little, mother|"
    r"towards the darkness she went|手挽手步入|"
    r"告阿伦戴尔全党|牵着小v的手",
    re.I,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main():
    keepers = load(DATA / "_keepers_by_cluster.json")
    dec_obj = load(DATA / "decisions.json")
    decs = dec_obj["decisions"]
    flipped = 0
    good = defaultdict(list)
    for cluster, items in keepers.items():
        for x in items:
            blob = (x.get("preview") or "") + "\n" + "\n".join(
                q.get("text") or "" for q in x.get("quotes") or []
            )
            if JUNK_KEEP.search(blob) or STILL_FANFIC.search(blob):
                reason = "同人/百科/歌词/闲聊漏网，非分析"
                if re.search(r"Vibrator|sex toy", blob, re.I):
                    reason = "NSFW，非冰学"
                decs[x["id"]] = {"verdict": "reject", "note": reason}
                flipped += 1
                continue
            good[cluster].append(x)
    atomic_write(DATA / "decisions.json", {"decisions": decs})
    atomic_write(DATA / "_good_keepers.json", good)
    counts = {k: len(v) for k, v in good.items()}
    vcount = Counter(d.get("verdict") for d in decs.values())
    (DATA / "_good_preview.txt").write_text(
        "flipped="
        + str(flipped)
        + "\ngood_clusters="
        + json.dumps(counts, ensure_ascii=False, indent=2)
        + "\nall_verdicts_now="
        + json.dumps(dict(vcount), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    # dump quotes file per priority cluster
    pri = [
        "struct_texture",
        "comp_ghibli",
        "comp_madoka",
        "comp_disney",
        "comp_pixar",
        "comp_myth_theo",
        "comp_other",
        "sha_diao",
        "fifth_spirit",
        "athl",
        "two_bridge",
        "elsa_char",
        "anna_char",
        "itu_voice",
        "pn_fos_ds",
        "production",
        "audience_method",
        "visa_arinur",
        "ofa",
        "ending_leave",
        "f3_ip",
        "setting_detail",
        "misc_frozen",
    ]
    lines = []
    for k in pri:
        items = good.get(k) or []
        lines.append(f"\n\n======== {k} n={len(items)} ========")
        for x in items[:18]:
            lines.append(f"\n--- {x['id']} | {x['time']} | {x['byline']} | {x['group']} ---")
            lines.append(x.get("preview") or "")
            for q in x.get("quotes") or []:
                lines.append(f"QUOTE {q['time']} {q['name']} ({q['n']}c)")
                lines.append(q["text"][:1200])
    (DATA / "_good_quotes.txt").write_text("\n".join(lines), encoding="utf-8")
    print("flipped", flipped, "good", sum(counts.values()), dict(counts))


if __name__ == "__main__":
    main()
