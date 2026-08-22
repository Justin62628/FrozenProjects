#!/usr/bin/env python3
from pathlib import Path
import json

p = Path(__file__).resolve().parent / "data" / "_new_keepers.json"
d = json.loads(p.read_text(encoding="utf-8"))
need = [
    "Newcomb",
    "Who am I",
    "Hair symbolism",
    "ITU所呈现",
    "转调顺序",
    "魔法是没有自己的独立意识",
    "truth theory",
    "Jennifer Lee",
    "Huldrefolk",
    "永冬大概率",
    "Frost Monster",
    "事件型IP",
    "Eatnemen",
    "Arinur的分析",
    "codependency是一种很病态",
    "Olaf的思想其实是反映",
    "A线比E线",
    "片尾版LIG",
    "官方原文",
    "单盒派",
    "弱故事",
    "世界观做的这么大",
    "花木兰",
    "圆焰的Analogy",
    "区分爱情和友情",
    "东方叙事",
    "Fairy and spirit",
    "议会解散",
    "Mythical Characte",
    "a place of our own",
    "祖辈压力",
    "FOS also builds",
    "两个人格",
    "两个核心矛盾",
    "Iduna作为全篇线索",
    "Find the truth",
    "OFA三层",
    "错怪OFA",
    "设定集说过She do not",
]
out = []
for k, items in d.items():
    for x in items:
        blob = x.get("preview") or ""
        for q in x.get("quotes") or []:
            blob += q.get("text") or ""
        for n in need:
            if n in blob:
                out.append(f"{n}\t{x['id']}\t{x['time']}\t{x['byline']}\t{k}")
                break
Path(__file__).resolve().parent.joinpath("data/_id_hits.txt").write_text(
    "\n".join(out), encoding="utf-8"
)
print(len(out), "hits")
