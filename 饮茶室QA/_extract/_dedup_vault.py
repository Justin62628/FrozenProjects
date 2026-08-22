#!/usr/bin/env python3
"""Mark keepers already in vault; dump truly-new quotes grouped for filing."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"


def vault_blob() -> str:
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
            parts.append(p.read_text(encoding="utf-8"))
    return re.sub(r"\s+", "", "\n".join(parts))


def needles(text: str) -> list[str]:
    t = re.sub(r"\s+", "", text or "")
    out = []
    if len(t) < 28:
        return out
    step = 18
    width = 32
    for i in range(0, min(len(t) - width + 1, 400), step):
        out.append(t[i : i + width])
    return out[:12]


def main():
    good = json.loads((DATA / "_good_keepers.json").read_text(encoding="utf-8"))
    dec_obj = json.loads((DATA / "decisions.json").read_text(encoding="utf-8"))
    decs = dec_obj["decisions"]
    corpus = vault_blob()
    new = defaultdict(list)
    seen_n = 0
    new_n = 0
    for cluster, items in good.items():
        for x in items:
            blob = (x.get("preview") or "")
            for q in x.get("quotes") or []:
                blob += q.get("text") or ""
            hit = False
            for n in needles(blob):
                if n and n in corpus:
                    hit = True
                    break
            if hit:
                seen_n += 1
                decs[x["id"]] = {
                    "verdict": decs[x["id"]]["verdict"],
                    "note": f"已见现有笔记（文本重叠） cluster={cluster}",
                }
            else:
                new_n += 1
                new[cluster].append(x)
    tmp = DATA / "decisions.tmp"
    tmp.write_text(json.dumps({"decisions": decs}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA / "decisions.json")
    (DATA / "_new_keepers.json").write_text(
        json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    lines = [f"seen_in_vault={seen_n} still_new={new_n}"]
    for k, items in sorted(new.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"\n## {k} n={len(items)}")
        for x in items[:12]:
            q = ""
            if x.get("quotes"):
                q = x["quotes"][0]["text"][:140].replace("\n", " ")
            else:
                q = (x.get("preview") or "")[:140]
            lines.append(f"- {x['time']} {x['byline']} {q}")
    (DATA / "_new_preview.txt").write_text("\n".join(lines), encoding="utf-8")
    print("seen", seen_n, "new", new_n, {k: len(v) for k, v in new.items()})


if __name__ == "__main__":
    main()
