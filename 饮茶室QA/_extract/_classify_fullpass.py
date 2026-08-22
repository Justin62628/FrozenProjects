#!/usr/bin/env python3
"""Classify every unmarked candidate; extract keeper quotes by cluster."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
CST = timezone(timedelta(hours=8))

AUTHOR_MAP = {
    "FrozenHeart": "FH",
    "急急急急急急": "JU",
    "发粪涂墙的🥔": "土豆",
    "黑糖小克莱恩": "Klein",
    "叽叽喳喳胖咕咕（北寻）": "北寻",
    "纳西妲": "纳西妲",
    "游鱼": "游鱼",
    "ZQ": "ZQ",
    "Dem": "Dem",
    "几内亚": "几内亚",
    "巴布亚-几内亚": "几内亚",
    "Visa": "Visa",
    "新约": "新约",
    "Snowflake Tale": "Snowflake",
    "443127105": "443127105",
}

FANFIC_RE = re.compile(
    r"纯属虚构|Once upon a time|Kristoff was folding|告阿伦戴尔全党|"
    r"可可无奈|岚姐电话|神目|性转|少女跌坐在浴室|青涩的胸型|"
    r"Scissoring|Tribadism|牵着小v的手|Dear Evan Hansen|"
    r"敬爱的冰雪女王艾莎和阿伦戴尔女王|手挽手步入辉煌的大殿|"
    r"从前，FH因为涉嫌拐卖|Taylor主教|"
    r"I've linked this big boy|Elsa flicked her fingers|"
    r"Remember when we were little, mother|"
    r"Sunlight pierced through the thick curtains|"
    r"Anna was wakened by the creak|"
    r"I’m going to send you from heaven to hell|"
    r"The sisters followed Gale|"
    r"towards the darkness she went|"
    r"Winter's gone and Spring is springing|"
    r"莉莉安的年轻女孩|"
    r"如果小时候的艾莎没有误伤.*平行时空|"
    r"豆腐同志在奥马哈",
    re.I,
)
BOT_RE = re.compile(
    r"旅行者\s*[🍃🌿✨]|Session:\s*milky|Switched to glm|"
    r"Providers:\s*\n- github-copilot|有什么我可以帮你的吗|"
    r"让我仔细思考一下。这条消息来自|"
    r"群里从昨天.+\d{2}:\d{2}.+的消息总结|"
    r"FrozenXX 还在继续说下去",
)
NSFW_RE = re.compile(r"黄图|涩图|r18|nsfw|约稿|胸型|浴室的地板|scissoring|tribadism", re.I)
FROZEN_RE = re.compile(
    r"Elsa|Anna|Ahtohallan|Athl|阿塔霍|第五灵|莎雕|娜雕|双桥|Northuldra|"
    r"Frozen|冰雪|Iduna|Runeard|Hans|Kristoff|Olaf|Arendelle|阿伦戴尔|"
    r"\bF1\b|\bF2\b|\bF3\b|\bPN\b|\bFOS\b|\bITU\b|\bOFA\b|\bDS\b|"
    r"Show Yourself|\bLIG\b|\bTNRT\b|冰宫|冰雕|Nattmara|Noaidi|"
    r"Polar Nights|Dangerous Secrets|Forest of Shadows|"
    r"Agnarr|Pabbie|Gale|Bruni|Nokk|Earth Giant",
    re.I,
)
STRUCT_RE = re.compile(
    r"结构主义|叙事学|叙述学|质感|设定层级|机制杀|闭环|和声终止|叙事功能|母题|"
    r"深层结构|单盒|双盒|功能项|普罗普|格雷马斯|符号矩阵|类型系统|"
    r"叙事闭合|闭合感|成立感|黑箱|观众心理|接受美学|作者论|"
    r"四层法|事实层|质感层|叙事容器|公路片|史诗",
    re.I,
)
COMP_RE = re.compile(
    r"宫崎骏|幽灵公主|吉卜力|小圆|魔圆|madoka|圆焰|焰|"
    r"toy story|玩具总动员|moana|海洋奇缘|rapunzel|tangled|乐佩|科罗娜|"
    r"中土|霍比特|魔戒|哈利波特|\bHP\b|zootopia|疯狂动物城|zoo2|"
    r"星际穿越|interstellar|天空之城|双城记|萨满|noaidi|基督教|神学|"
    r"公主片|比较|对照|对标|联立|同构|互文|迪皮|迪士尼公主|"
    r"千与千寻|龙猫|风之谷|哈尔|魔女宅急便|sekai|世界计划|"
    r"animal farm|动物农场|指环王|纳尼亚|狮子王|花木兰|阿拉丁|小美人鱼|"
    r"寻梦环游记|\bCoco\b|头脑特工|inside out|超能陆战队|无敌破坏王|ralph|"
    r"安徒生|格林童话|北欧神话|卡勒瓦拉|新海诚|你的名字|"
    r"EVA|福音战士|凉宫|进击的巨人|辉夜姬|哪吒|Wish\b|Raya|"
    r"Once Upon a Time|OUAT|Matilda|convergent evolution|"
    r"西部片|余秋雨|红楼梦|哈姆雷特|文化工业|阿多诺|"
    r"Visa|Arinur|Jennifer Lee|神话/童话",
    re.I,
)

CLUSTERS = [
    ("struct_texture", r"质感|单盒|双盒|四层法|事实层|结构主义|作者论|黑箱|观众情绪流|成立感|接受美学"),
    ("comp_ghibli", r"宫崎骏|幽灵公主|吉卜力|千与千寻|龙猫|风之谷|天空之城|哈尔|魔女宅急便"),
    ("comp_madoka", r"小圆|魔圆|madoka|圆焰|圆神|叛逆"),
    ("comp_disney", r"花木兰|moana|海洋奇缘|rapunzel|tangled|乐佩|科罗娜|raya|wish\b|迪士尼公主|Who am I|Matilda"),
    ("comp_pixar", r"toy story|玩具总动员|zootopia|zoo2|疯狂动物城|coco|寻梦环游记|ralph|无敌破坏王"),
    ("comp_myth_theo", r"萨满|noaidi|基督教|神学|神话|安徒生|北欧|huldrefolk|赞美诗|Eatnemen|fairy and spirit"),
    ("comp_other", r"中土|哈利波特|\bHP\b|EVA|进击的巨人|哪吒|星际穿越|石头门|西部片|红楼梦|哈姆雷特|余秋雨|文化工业|阿多诺|sekai|世界计划"),
    ("sha_diao", r"莎雕|机制杀|沉船支票|冻住|自己冻"),
    ("fifth_spirit", r"第五灵|fifth spirit|great spirit|bridge"),
    ("athl", r"Ahtohallan|Athl|阿塔霍"),
    ("two_bridge", r"双桥|两面|人性面|魔法面"),
    ("pn_fos_ds", r"Polar Nights|\bPN\b|Forest of Shadows|\bFOS\b|Dangerous Secrets|\bDS\b|Nattmara"),
    ("itu_voice", r"\bITU\b|the Voice|into the unknown|STNC"),
    ("elsa_char", r"自闭|冰宫|conceal|fear vs love|INFJ|双人格|storm inside|地牢|手套"),
    ("anna_char", r"Anna.{0,8}(责任感|spare|codepend|心理)|TNRT|people person"),
    ("ending_leave", r"离开|传位|女王身份|没事干|日常职责|永生|寿命"),
    ("ofa", r"\bOFA\b|Frozen Adventure|错怪OFA|第三层"),
    ("f3_ip", r"\bF3\b|IP演化|轮回|公主/少女|F3"),
    ("visa_arinur", r"Visa|Arinur"),
    ("production", r"纪录片|底层的大改|Chris Buck|Jennifer Lee|deleted scene|设定集|Art of F2"),
    ("setting_detail", r"议会|闭关|harvest festival|Saga|Aren Fiord|时间线"),
    ("audience_method", r"冰学|过度解读|观众|方法论|圈地自萌"),
]


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


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


def byline(name: str) -> str:
    if name in AUTHOR_MAP:
        return AUTHOR_MAP[name]
    for k, v in AUTHOR_MAP.items():
        if k in (name or ""):
            return v
    return name or "?"


def hay_of(c: dict) -> str:
    parts = [c.get("preview") or "", c.get("author_name") or ""]
    for m in c.get("messages") or []:
        if m.get("role") == "ctx":
            continue
        parts.append(m.get("name") or "")
        parts.append((m.get("text") or "")[:2000])
    return "\n".join(parts)


def longest_quotes(c: dict, n: int = 2, cap: int = 1400) -> list[dict]:
    scored = []
    for m in c.get("messages") or []:
        if m.get("role") in ("ctx",):
            continue
        t = (m.get("text") or "").strip()
        if len(t) < 40:
            continue
        scored.append((len(t), m))
    scored.sort(key=lambda x: -x[0])
    out = []
    for _, m in scored[:n]:
        t = (m.get("text") or "").strip()
        out.append(
            {
                "time": iso_to_cst(m.get("time") or c.get("time_start") or ""),
                "name": m.get("name") or c.get("author_name") or "",
                "text": t[:cap],
                "n": len(t),
            }
        )
    return out


def cluster_of(hay: str, flags: set[str]) -> str:
    if "struct" in flags:
        for key, pat in CLUSTERS[:1]:
            if re.search(pat, hay, re.I):
                return key
        return "struct_texture"
    for key, pat in CLUSTERS:
        if re.search(pat, hay, re.I):
            return key
    if "comp" in flags:
        return "comp_other"
    return "misc_frozen"


def classify(c: dict) -> dict:
    preview = c.get("preview") or ""
    files = c.get("files") or []
    msgs = c.get("messages") or []
    body_chars = 0
    texts = []
    for m in msgs:
        if m.get("role") == "ctx":
            continue
        t = (m.get("text") or "").strip()
        body_chars += len(t)
        texts.append(t)
    hay = hay_of(c)
    flags = set()
    if STRUCT_RE.search(hay):
        flags.add("struct")
    if COMP_RE.search(hay):
        flags.add("comp")

    # later: attachment with almost no text
    if files and body_chars < 80 and not FROZEN_RE.search(preview):
        return {"verdict": "later", "reason": "附件无正文", "cluster": "later_attach", "flags": sorted(flags)}
    if files and body_chars < 50:
        return {"verdict": "later", "reason": "附件无正文", "cluster": "later_attach", "flags": sorted(flags)}

    if NSFW_RE.search(hay) and not FROZEN_RE.search(hay[:400]):
        return {"verdict": "reject", "reason": "NSFW", "cluster": "junk", "flags": sorted(flags)}
    if NSFW_RE.search(hay) and re.search(r"浴室|胸型|scissoring|tribadism", hay, re.I):
        return {"verdict": "reject", "reason": "NSFW/同人色情", "cluster": "junk", "flags": sorted(flags)}

    if BOT_RE.search(hay) and not flags.intersection({"struct", "comp"}):
        # keep if it's a real 纳西妲 essay already flagged; else bot dump
        if re.search(r"旅行者|Session:|Switched to glm|Providers:", hay):
            return {"verdict": "reject", "reason": "LLM/bot 闲聊或会话转储", "cluster": "junk", "flags": sorted(flags)}

    if FANFIC_RE.search(hay):
        # comparative/struct still keep even if framed as story? user said skip NSFW-only and zero Frozen.
        # Actual fiction dumps are junk.
        if not flags.intersection({"struct"}) and (
            re.search(r"纯属虚构|Once upon a time|Kristoff was folding|告阿伦戴尔|可可无奈|岚姐|浴室|牵着小v", hay)
            or (not FROZEN_RE.search(preview) and "fanart" in hay.lower())
        ):
            return {"verdict": "reject", "reason": "同人小说/RP，非分析", "cluster": "junk", "flags": sorted(flags)}
        if re.search(
            r"Once upon a time|Kristoff was folding|纯属虚构|告阿伦戴尔全党|少女跌坐|牵着小v的手|Scissoring|Taylor主教|"
            r"I've linked this big boy|Sunlight pierced|Anna was wakened|Elsa flicked her fingers|"
            r"Remember when we were little, mother|towards the darkness she went|"
            r"Winter's gone and Spring is springing|莉莉安|奥马哈海滩|"
            r"手挽手步入辉煌|国民代表作了",
            hay,
            re.I,
        ):
            return {"verdict": "reject", "reason": "同人小说/歌词堆砌/RP，非分析", "cluster": "junk", "flags": sorted(flags)}

    # drawing / anatomy
    if re.search(r"画大腿|上半身画得窄|鞋垫", hay) and body_chars < 500:
        return {"verdict": "reject", "reason": "画风/解剖闲聊", "cluster": "junk", "flags": sorted(flags)}

    # HALO joke without Frozen mechanism
    if re.search(r"HALO 3|halo 3", hay, re.I) and not re.search(r"Elsa|莎雕|第五灵|Ahtohallan", hay):
        return {"verdict": "reject", "reason": "HALO 玩梗，非冰学", "cluster": "junk", "flags": sorted(flags)}

    frozen = bool(FROZEN_RE.search(hay))
    # boost keep
    if flags.intersection({"struct", "comp"}) and (frozen or flags == {"struct"} or "比较" in hay or "对照" in hay):
        kind = c.get("kind") or "theory"
        v = "keep_discussion" if kind == "discussion" else "keep_theory"
        # multi-voice
        names = {m.get("name") for m in msgs if m.get("role") not in ("ctx", "forwarded") and m.get("name")}
        if len(names) >= 3:
            v = "keep_discussion"
        return {"verdict": v, "reason": "结构主义/比较文学优先收", "cluster": cluster_of(hay, flags), "flags": sorted(flags)}

    if not frozen and body_chars < 400:
        return {"verdict": "reject", "reason": "无 Frozen 内容/过短", "cluster": "junk", "flags": sorted(flags)}
    if not frozen:
        return {"verdict": "reject", "reason": "非 Frozen", "cluster": "junk", "flags": sorted(flags)}

    # one-liner
    if body_chars < 90 and not flags:
        return {"verdict": "reject", "reason": "一句空话/过短", "cluster": "junk", "flags": sorted(flags)}

    # industry news without analysis
    if re.search(r"票房|开画纪录|CEO Bob Iger teased", hay) and body_chars < 700 and not flags:
        return {"verdict": "reject", "reason": "产业新闻无分析", "cluster": "junk", "flags": sorted(flags)}

    kind = c.get("kind") or "theory"
    names = {m.get("name") for m in msgs if m.get("role") not in ("ctx", "forwarded") and m.get("name")}
    v = "keep_discussion" if (kind == "discussion" or len(names) >= 3) else "keep_theory"
    return {"verdict": v, "reason": "冰学机制/人物/设定", "cluster": cluster_of(hay, flags), "flags": sorted(flags)}


def main() -> None:
    cands_obj = load_json(DATA / "candidates.json", {})
    cands = cands_obj.get("candidates", cands_obj)
    dec_obj = load_json(DATA / "decisions.json", {"decisions": {}})
    if "decisions" not in dec_obj:
        dec_obj = {"decisions": dec_obj}
    decs = dec_obj["decisions"]

    unmarked = [c for c in cands if not (decs.get(c["id"]) or {}).get("verdict")]
    results = []
    by_v = Counter()
    by_c = Counter()
    keepers = defaultdict(list)

    # duplicate preview tracking
    seen_preview = {}

    for c in unmarked:
        rec = classify(c)
        prev = re.sub(r"\s+", "", (c.get("preview") or "")[:80])
        if rec["verdict"].startswith("keep") and len(prev) >= 40:
            if prev in seen_preview:
                rec = {
                    "verdict": "reject",
                    "reason": f"重复预览，已见 {seen_preview[prev]}",
                    "cluster": "dup",
                    "flags": rec.get("flags") or [],
                }
            else:
                seen_preview[prev] = c["id"]
        rec["id"] = c["id"]
        rec["author"] = c.get("author_name")
        rec["byline"] = byline(c.get("author_name") or "")
        rec["kind"] = c.get("kind")
        rec["group"] = c.get("group")
        rec["time"] = iso_to_cst(c.get("time_start") or "")
        rec["time_end"] = iso_to_cst(c.get("time_end") or "")
        rec["n_msgs"] = c.get("n_msgs")
        rec["preview"] = (c.get("preview") or "")[:180]
        rec["files"] = c.get("files") or []
        if rec["verdict"].startswith("keep"):
            rec["quotes"] = longest_quotes(c)
            keepers[rec["cluster"]].append(rec)
        results.append(rec)
        by_v[rec["verdict"]] += 1
        by_c[rec["cluster"]] += 1

        # write decision now
        note = rec["reason"]
        if rec["verdict"].startswith("keep"):
            note = f"{rec['reason']} → {rec['cluster']}"
        decs[c["id"]] = {"verdict": rec["verdict"], "note": note}

    atomic_write(DATA / "decisions.json", {"decisions": decs})

    # keepers dump (no full messages)
    slim_keepers = {}
    for k, items in keepers.items():
        items = sorted(items, key=lambda x: (-x.get("quotes", [{}])[0].get("n", 0) if x.get("quotes") else 0, x["time"]))
        slim_keepers[k] = [
            {
                "id": x["id"],
                "byline": x["byline"],
                "author": x["author"],
                "time": x["time"],
                "group": x["group"],
                "verdict": x["verdict"],
                "preview": x["preview"],
                "quotes": x.get("quotes") or [],
                "flags": x.get("flags") or [],
            }
            for x in items
        ]
    atomic_write(DATA / "_keepers_by_cluster.json", slim_keepers)
    atomic_write(
        DATA / "_pass_stats.json",
        {
            "n_unmarked": len(unmarked),
            "verdicts": dict(by_v),
            "clusters": dict(by_c),
            "n_keep_ids": sum(1 for r in results if r["verdict"].startswith("keep")),
        },
    )

    lines = [f"unmarked={len(unmarked)} verdicts={dict(by_v)}"]
    lines.append("clusters:")
    for k, n in by_c.most_common():
        lines.append(f"  {n:4d}  {k}")
    lines.append("\nKEEP samples per cluster:")
    for k, items in slim_keepers.items():
        lines.append(f"\n## {k} n={len(items)}")
        for x in items[:8]:
            q = (x["quotes"][0]["text"][:120].replace("\n", " ") if x["quotes"] else x["preview"][:120])
            lines.append(f"- {x['time']} {x['byline']} {x['id'][-8:]} {q}")
    (DATA / "_pass_preview.txt").write_text("\n".join(lines), encoding="utf-8")
    print("ok", dict(by_v), "clusters", len(slim_keepers), "unmarked", len(unmarked))


if __name__ == "__main__":
    main()
