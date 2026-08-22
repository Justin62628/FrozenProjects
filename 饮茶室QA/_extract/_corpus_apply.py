#!/usr/bin/env python3
"""File gap-fill notes from dumps; flip reject→keep; patch MOCs. No git."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ROOT = HERE.parent
DUMP = DATA / "_gapfill_dump"
TODAY = "2026-08-22"

FLIP = {
    # analysis
    "qitan:theory:6841284230527127318": ("keep_theory", "早期conceal/跳崖心理 2020-06-23 原文"),
    "qitan:theory:6821552382301318058": ("keep_theory", "FF是F2铺垫 2020-05-01 原文"),
    "qitan:theory:6807561826747294122": ("keep_theory", "双人格 Snow Queen 命名 2020-03-24"),
    "qitan:theory:6799644484460571944": ("keep_theory", "双人格 2020-03-03 最早稿"),
    "qitan:theory:6801966599978910392": ("keep_theory", "Athl冻住为了让Anna独立 2020-03-09"),
    "qitan:theory:6852095290953965595": ("keep_theory", "母女线 2020-07-22 原文"),
    "qitan:theory:6842192563254877087": ("keep_discussion", "443 Elsa跳崖Fear驱动"),
    "qitan:discussion:6872000908671693395": ("keep_discussion", "443 不要解释错误解读"),
    "qitan:theory:6827434918225259940": ("keep_theory", "truth theory 2020-05 重发，原文2020-03-12"),
    "tea:theory:6927462516838353821": ("keep_theory", "2021-02 重述 2020-06-23 conceal/跳崖"),
    "tea:theory:7223795840563262592": ("keep_theory", "Fear vs Love 具体化 2023-04-18"),
    "tea:theory:6879373087584143817": ("keep_theory", "2020-10 重发 FF铺垫 2020-05-01"),
    "tea:theory:7392265675968598716": ("keep_discussion", "Alice reddit 第五灵用途"),
    "tea:theory:6910223522961898568": ("keep_discussion", "FH Elsa圣诞贺词 同人"),
    "tea:theory:6878249097519467295": ("keep_discussion", "馄饨 Kristoff/Athl 同人"),
    "tea:theory:6820511757789515683": ("keep_discussion", "馄饨 Elsa morning 同人"),
    "tea:theory:7659101007289547843": ("keep_discussion", "FrozenXX 多年后安葬地 同人"),
    "tea:theory:7483006411967542487": ("keep_discussion", "2025-03 刻画缺失/赶工，回指Visa/母女"),
    # already keep but ensure
    "qitan:theory:6807014342751495032": ("keep_discussion", "ITU 2020-03-22 补充"),
    "tea:theory:6879667269973826891": ("keep_discussion", "DS 剧透分析"),
    "tea:theory:6805444389624271026": ("keep_discussion", "Once upon a time 同人"),
    "tea:theory:6892239508502194841": ("keep_discussion", "Huldrefolk back-story 同人"),
    "tea:theory:7530606902026316193": ("keep_discussion", "Remember when 同人"),
    "tea:theory:7674393303119838413": ("keep_discussion", "纳西妲 KA代偿"),
}

# NSFW-only 车文 / 非 Frozen 叙事：保持 reject，只写 note
STAY_REJECT = {
    "tea:theory:7062233074355699": "NSFW 车文",
    "tea:theory:7062267420356849": "NSFW 车文",
    "tea:theory:7064385791258786": "NSFW 车文",
    "tea:theory:7064444845983928": "NSFW 车文（车文后记）",
    "tea:theory:6879397482517808766": "NSFW 车文",
    "tea:theory:7241112783761776359": "NSFW 车文（作者自认有车）",
    "tea:theory:6926799867072130694": "NSFW 车文 RP",
    "tea:theory:6927220049371376608": "NSFW 车文 RP 转发",
    "tea:theory:6954760217084480808": "现代AU/岚姐，非 Frozen 叙事",
    "tea:theory:6955516615156091": "现代AU 岚姐",
    "tea:theory:6960352070144356582": "现代AU 岚姐",
    "tea:theory:6965899257834938210": "现代AU 岚姐",
    "tea:theory:6952536528178094771": "NSFW 车文",
    "tea:theory:6952911946387115502": "现代AU 性转",
    "tea:theory:6953311996771708": "现代AU 可可无奈",
    "tea:theory:6953672388723617": "现代AU",
    "tea:theory:6958856271895112619": "现代AU 岚姐",
    "tea:theory:6977743094304629530": "现代AU 图",
    "tea:theory:7175737697806692703": "铃铃 chatbot AU，非 Frozen 叙事正文",
    "tea:theory:7175430241981198": "铃铃 杂图/非分析",
    "tea:theory:7181014425323965629": "铃铃 chatbot",
    "tea:theory:7175777682544285860": "铃铃 chatbot",
    "tea:theory:7175400568694191803": "百科 mosasaur，非冰学",
    "tea:theory:7176556299103757": "歌词 Shape of You",
    "tea:theory:6845606521448638472": "NSFW 词条",
    "tea:theory:7099824906347149182": "小v/小蜥蜴，非 Frozen 叙事",
    "tea:theory:7093143582465504933": "小v/小蜥蜴 Dear Evan Hansen",
    "tea:theory:7610422724694676048": "艳史，非 Frozen",
    "tea:theory:7002197894524982": "LIG 歌词对照，非分析",
    "tea:theory:6928224885899656154": "ITU 歌词对照",
    "tea:theory:6928039507776098356": "LIG 歌词对照",
    "tea:theory:6890515194160852024": "歌词堆砌",
    "tea:theory:7192603602591881156": "Idina 采访转载无分析",
    "tea:theory:7413934097882205429": "周边商品页",
    "tea:theory:7571336125266994947": "票房数据无分析",
    "tea:theory:7571336145688462850": "票房数据无分析",
    "tea:theory:7621497718123977320": "磁力链",
    "tea:theory:7550906476966957949": "莉莉安泛童话，非 Frozen",
    "tea:theory:6992224931266692": "Taylor主教玩笑",
    "tea:theory:7395440235708622763": "迪士尼乐园选址，非冰学",
    "tea:theory:6863420958980887349": "快递通知",
    "tea:theory:7615862317995418491": "LLM provider 转储",
    "tea:theory:7668284565974638384": "LLM 切换",
    "klein:discussion:7583212301508875386": "魔圆魔女设定，非 Frozen 叙事",
    "tea:theory:6928683267064054748": "眼皮化妆闲聊",
}


def atomic_write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def yaml_block(title, area, source, t0, t1, related):
    rel = "\n".join(f'  - "{r}"' for r in related)
    return f"""---
title: {title}
area: {area}
source: {source}
time_start: {t0}
time_end: {t1}
tags:
  - type/ref
  - area/frozen
related:
{rel}
updated: {TODAY}
---
"""


def write_note(relpath, title, area, source, t0, t1, related, body):
    md = yaml_block(title, area, source, t0, t1, related)
    md += f"\n# {title}\n\n"
    md += f"出处时间：{t0}" + (f" → {t1}" if t1 != t0 else "") + "\n\n"
    md += body.rstrip() + "\n"
    path = ROOT / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    return path


def dump_text(name: str) -> str:
    p = DUMP / name
    return p.read_text(encoding="utf-8").rstrip()


def patch_between(path: Path, start: str, end: str | None, new: str) -> None:
    cur = path.read_text(encoding="utf-8")
    i = cur.find(start)
    if i < 0:
        raise SystemExit(f"start not found in {path}: {start[:40]!r}")
    if end:
        j = cur.find(end, i)
        if j < 0:
            raise SystemExit(f"end not found in {path}: {end[:40]!r}")
        cur = cur[:i] + new + cur[j:]
    else:
        cur = cur[:i] + new
    cur = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {TODAY}", cur, count=1)
    path.write_text(cur, encoding="utf-8")


def set_yaml_times(path: Path, t0: str, t1: str, source: str | None = None) -> None:
    cur = path.read_text(encoding="utf-8")
    cur = re.sub(r"time_start: .*", f"time_start: {t0}", cur, count=1)
    cur = re.sub(r"time_end: .*", f"time_end: {t1}", cur, count=1)
    if source:
        cur = re.sub(r"source: .*", f"source: {source}", cur, count=1)
    cur = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {TODAY}", cur, count=1)
    # 出处时间 line
    cur = re.sub(
        r"出处时间：.*",
        f"出处时间：{t0}" + (f" → {t1}" if t1 != t0 else ""),
        cur,
        count=1,
    )
    path.write_text(cur, encoding="utf-8")


def append_moc_bullets(path: Path, heading: str, bullets: list[str]) -> None:
    cur = path.read_text(encoding="utf-8")
    for b in bullets:
        if b.split("]]")[0] in cur:
            continue
        # insert after heading section's last similar bullet
        idx = cur.find(heading)
        if idx < 0:
            cur = cur.rstrip() + "\n\n" + heading + "\n\n" + b + "\n"
            continue
        # find next ## or end of list
        after = cur.find("\n## ", idx + len(heading))
        insert_at = after if after > 0 else len(cur)
        cur = cur[:insert_at].rstrip() + "\n" + b + "\n" + cur[insert_at:]
    cur = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {TODAY}", cur, count=1)
    path.write_text(cur, encoding="utf-8")


def main() -> None:
    created = []
    expanded = []

    # ---- 母女线：2020-07-22 为 canonical ----
    p = ROOT / "冰学独立理论与分析/FH：母女线分析.md"
    body = (
        "2020-07-22 奇谈原文是 canonical。后文 QA 提纲是同一篇的无时间戳誊录，不要当另一篇。声音为何是母亲，见 [[饮茶室QA/冰学独立理论与分析/FH：ITU第一次听见the Voice]]。\n\n"
        "## 2020-07-22 奇谈\n\n"
        + dump_text("qitan_theory_6852095290953965595.md")
    )
    write_note(
        "冰学独立理论与分析/FH：母女线分析.md",
        "FH：母女线分析",
        "冰学独立理论与分析",
        "❄️冰学奇谈会议室群聊 2020-07-22",
        "2020-07-22 08:29:16",
        "2020-07-22 11:09:52",
        [
            "[[饮茶室QA/核心/核心FAQ]]",
            "[[FH：SY Metaphor]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：Iduna不是第五灵]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：ITU第一次听见the Voice]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：FOS的Nattmara与坏女王恐惧]]",
        ],
        body,
    )
    expanded.append("FH：母女线分析")

    # ---- FF铺垫：2020-05-01 canonical ----
    later = (
        "\n\n## 2025-09 补笔：Grand Tour\n\n"
        "导火索是Grand Tour，Elsa第一次要独自离开Arendelle去其他国家社交，还不能带Anna因为Anna得留下看家。"
        "高强度社交如果没有Anna的emotional support对Elsa这种心底极度社恐的人来说压力是相当大的。"
        "而且FOS也有写在Grand Tour之前Elsa的工作量明显加重，也是她想把能干的活全干了她走了Anna好轻松。双重压力下之前隐藏的问题全暴露了\n"
    )
    body = (
        "2020-05-01 奇谈原文是 canonical。2020-10-03 / 2025-09 的缩写回指本页。\n\n"
        "## 2020-05-01 奇谈\n\n"
        + dump_text("qitan_theory_6821552382301318058.md")
        + later
    )
    write_note(
        "冰学独立理论与分析/FH：FF是F2的铺垫.md",
        "FH：FF是F2的铺垫",
        "冰学独立理论与分析",
        "❄️冰学奇谈会议室群聊 2020-05-01",
        "2020-05-01 01:05:23",
        "2020-05-01 01:21:10",
        [
            "[[饮茶室QA/核心/FrozenHeart语录]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：F2姐妹错位]]",
            "[[饮茶室QA/冰学讨论/冰二的刻画缺失]]",
            "[[饮茶室QA/冰学讨论/早期conceal与莎雕心理]]",
        ],
        body,
    )
    expanded.append("FH：FF是F2的铺垫")

    # ---- 早期conceal full ----
    body = (
        "2020-06-23 奇谈原文。莎雕前 Elsa 的 conceal don't feel——四灵苏醒后把锅揽到自己「想了解魔法」上。"
        "2021-02-10 饮茶室重述同一段，回指本页，不要当另一篇。"
        "Runeard 坝像手套的 2020-05-06 原文见 [[饮茶室QA/冰学独立理论与分析/FH：Runeard对魔法的不信任]]。\n\n"
        + dump_text("qitan_theory_6841284230527127318.md")
        + "\n\n## 短析\n\n和 FH 莎雕、土豆故事线并读：机制解释「怎么冻」，这页解释「她为什么觉得是自己的错」。\n"
    )
    write_note(
        "冰学讨论/早期conceal与莎雕心理.md",
        "早期conceal与莎雕心理",
        "冰学讨论",
        "❄️冰学奇谈会议室群聊 2020-06-23",
        "2020-06-23 05:16:50",
        "2020-06-23 05:18:35",
        [
            "[[饮茶室QA/冰学讨论/再论莎雕]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：莎雕分析]]",
            "[[饮茶室QA/冰学独立理论与分析/土豆：莎雕分析]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：Runeard对魔法的不信任]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：truth theory与封林]]",
        ],
        body,
    )
    expanded.append("早期conceal与莎雕心理")

    # ---- 双人格 dated stages ----
    dual = (
        "主张：所谓「魔法自己的意识」是 Elsa 人格的一半，不是附身。"
        "2020-03-03 奇谈最早稿；2020-03-13 展开 LIG/FTFTIF；2020-03-24 命名 The Snow Queen / Elsa of Arendelle；"
        "2021-02 明确魔法无独立意识。完整的灵见 [[饮茶室QA/冰学独立理论与分析/FH：完整的灵也是完整的人]]。\n\n"
        "## 2020-03-03 奇谈（最早）\n\n"
        + dump_text("qitan_theory_6799644484460571944.md").split("> *2020-03-03 00:16:34")[0]
        + "\n## 2020-03-13 奇谈\n\n"
        + dump_text("qitan_6803704562952993320.md")
        + "\n\n## 2020-03-24 奇谈（Snow Queen 命名）\n\n"
        + "\n\n".join(dump_text("qitan_theory_6807561826747294122.md").split("\n\n")[:6])
        + "\n\n## 2021-02 魔法无独立意识\n\n"
    )
    old = (ROOT / "冰学独立理论与分析/FH：双人格与魔法无独立意识.md").read_text(encoding="utf-8")
    m = re.search(r"### 2021-02 魔法无独立意识\n\n(.+?)\n\n### 2020-07", old, re.S)
    magic_2021 = m.group(1) if m else ""
    chaos = old.split("### 2020-07 奇谈 两个核心矛盾")[-1] if "### 2020-07" in old else ""
    body = dual + magic_2021 + "\n\n## 2020-07 奇谈 两个核心矛盾" + chaos
    write_note(
        "冰学独立理论与分析/FH：双人格与魔法无独立意识.md",
        "FH：双人格与魔法无独立意识",
        "冰学独立理论与分析",
        "❄️冰学奇谈会议室 / 饮茶室群聊摘录",
        "2020-03-03 00:13:21",
        "2021-02-28 01:39:59",
        [
            "[[饮茶室QA/冰学独立理论与分析/FH：完整的灵也是完整的人]]",
            "[[FH：双桥理论]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：Visa论F2刻画]]",
        ],
        body,
    )
    expanded.append("FH：双人格与魔法无独立意识")

    # ---- truth theory earliest ----
    body = (
        "2020-03-12 奇谈原文是 canonical。2020-03-13 / 2020-05-16 / 2021-02 是同一段重发，回指本页。\n\n"
        "## 2020-03-12 奇谈\n\n"
        + dump_text("qitan_6803207692073560619.md")
        + "\n\n## 2020-03-13 重发（@ArendelleDream）\n\n"
        "> *2020-03-13 22:35:01  FrozenHeart*\n"
        "> @ArendelleDream 来康康这个\n"
        "> truth theory\n"
        "下文与 2020-03-12 同文，见上。\n\n"
        "## 短析\n\n封林 = 停住时间，直到有人能 right the wrong。第五灵是解题人，不是风景。\n"
    )
    write_note(
        "冰学独立理论与分析/FH：truth theory与封林.md",
        "FH：truth theory与封林",
        "冰学独立理论与分析",
        "❄️冰学奇谈会议室群聊 2020-03-12",
        "2020-03-12 14:40:25",
        "2020-03-13 22:35:01",
        [
            "[[饮茶室QA/冰学讨论/第五灵考核]]",
            "[[饮茶室QA/冰学讨论/大坝对北地的作用]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：Ahtohallan是四灵之母]]",
        ],
        body,
    )
    expanded.append("FH：truth theory与封林")

    # ---- ITU add earliest fragment ----
    itu = ROOT / "冰学独立理论与分析/FH：ITU第一次听见the Voice.md"
    cur = itu.read_text(encoding="utf-8")
    if "2020-03-21" not in cur:
        insert = (
            "最早残稿是 2020-03-21 奇谈（思路被打断，只写出第 1 点）。2020-04-03 才是写完的 canonical。"
            "2021-02-09 @Vivian 是复述点 1–2，不是另一篇。\n\n"
            "## 2020-03-21 奇谈（残稿）\n\n"
            + dump_text("qitan_6806403181716104449.md")
            + "\n\n"
        )
        cur = cur.replace("## 2020-04-03 奇谈\n", insert + "## 2020-04-03 奇谈\n", 1)
        cur = re.sub(r"time_start: .*", "time_start: 2020-03-21 05:20:33", cur, count=1)
        cur = re.sub(
            r"出处时间：.*",
            "出处时间：2020-03-21 05:20:33 → 2021-02-10 00:07:35",
            cur,
            count=1,
        )
        cur = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {TODAY}", cur, count=1)
        itu.write_text(cur, encoding="utf-8")
    expanded.append("FH：ITU第一次听见the Voice")

    # ---- Once upon: note 2020-03-17 start ----
    once = ROOT / "同人/FH：Once upon a time第五灵.md"
    cur = once.read_text(encoding="utf-8")
    if "2020-03-17" not in cur:
        cur = cur.replace(
            "2020-03-17 奇谈临场瞎编，次日饮茶室贴出整理全文。",
            "2020-03-17 23:33 奇谈只发出第一句；2020-03-18 饮茶室贴出整理全文（canonical）。",
        )
        once.write_text(cur, encoding="utf-8")

    # ---- Fear vs Love full ----
    fh_blocks = []
    raw = dump_text("tea_theory_7223795840563262592.md")
    for block in raw.split("\n\n"):
        if "FrozenHeart" in block[:80] and len(block) > 400:
            fh_blocks.append(block)
    anakin = (
        "\n\n## 补：Anakin 对照\n\n"
        "把Anakin和Elsa进行对比确实是个挺有意思的角度，可以从love vs fear上分析和关联：Elsa在F1中魔法的失控是被对自己魔法的排斥和恐惧和对自己是个诅咒会毁掉所爱一切的恐惧驱动的，而Anakin的黑化则主要来自无法保护Padme、失去Padme的恐惧；但fear is the shadow of love, you fear because you care。"
        "Elsa自始至终懂得love的真谛，在Anna的love启示下意识到需要爱自己和自己的魔法才能控制好魔法，Anakin最后也是因为儿子Luke对自己光明面的契而不舍的爱而激发了他最深处想保护亲人和爱人的本质，从而能脱离黑暗面的愤怒和仇恨。"
        "love vs fear并不完全契合原力光明黑暗对立的主要矛盾，但对于Anakin的弧光来说倒是可以分析。\n"
    )
    body = (
        "2023-04-18 饮茶室原文是 canonical。必须补上 E 线的 love（接纳自己的独特）和 A 线的 fear，才能谈 fear vs love。\n\n"
        + "\n\n".join(fh_blocks[:3])
        + anakin
    )
    write_note(
        "冰学独立理论与分析/FH：Fear vs Love.md",
        "FH：Fear vs Love",
        "冰学独立理论与分析",
        "饮茶室群聊 2023-04-18",
        "2023-04-18 20:26:52",
        "2023-04-18 20:53:07",
        [
            "[[饮茶室QA/核心/FrozenHeart语录]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：莎雕分析]]",
            "[[FH：双桥理论]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：娜雕解冻分析]]",
        ],
        body,
    )
    expanded.append("FH：Fear vs Love")

    # ---- EA 真爱：童年段回指 2020 ----
    ea = ROOT / "冰学独立理论与分析/FH：EA不基于欲望的真爱.md"
    cur = ea.read_text(encoding="utf-8")
    if "娜雕解冻分析" not in cur.split("主张")[1][:400]:
        cur = cur.replace(
            "主张：EA 是不基于欲望的 selfless sacrifice；Anna 必须保持人类，给她魔法会拆掉神话人物 / 童话人物的结构。提出者 FrozenHeart。\n\n"
            "她俩的关系已经不能用一个简单的亲情或爱情去概括了。\n"
            "先从EA小时候说起",
            "主张：EA 是不基于欲望的 selfless sacrifice；Anna 必须保持人类，给她魔法会拆掉神话人物 / 童话人物的结构。提出者 FrozenHeart。\n\n"
            "「先从EA小时候说起」到 best buddies 那一段，2020-10-16 奇谈原文见 [[饮茶室QA/冰学独立理论与分析/FH：娜雕解冻分析]]，下面是后来的缩写汇集，不是另一篇童年分析。\n\n"
            "她俩的关系已经不能用一个简单的亲情或爱情去概括了。\n"
            "先从EA小时候说起",
        )
        ea.write_text(cur, encoding="utf-8")
    expanded.append("FH：EA不基于欲望的真爱")

    # ---- Runeard note: 2021 recap pointer ----
    ru = ROOT / "冰学独立理论与分析/FH：Runeard对魔法的不信任.md"
    cur = ru.read_text(encoding="utf-8")
    if "2021-02-10" not in cur:
        cur = cur.rstrip() + (
            "\n\n## 2021-02-10 缩写（回指）\n\n"
            "2021-02-10 饮茶室把「That's just your fear / 坝像手套 / 解雾条件是 Fear→Love」整段重发，"
            "那是 [[饮茶室QA/冰学讨论/早期conceal与莎雕心理]] 2020-06-23 的缩写，不是 2020-05-06 这篇祖父 Fear 原文的另一篇。"
            "祖父台词原文仍以本页 2020-05-06 为准。\n"
        )
        ru.write_text(cur, encoding="utf-8")

    # ---- 自闭十三年 already points to 2020 thaw; leave unique 2026 黑化段 ----

    # NEW theory notes
    write_note(
        "冰学独立理论与分析/FH：Athl冻住是为了让Anna独立.md",
        "FH：Athl冻住是为了让Anna独立",
        "冰学独立理论与分析",
        "❄️冰学奇谈会议室群聊 2020-03-09",
        "2020-03-09 06:24:21",
        "2020-03-09 06:24:21",
        [
            "[[FH：双桥理论]]",
            "[[饮茶室QA/冰学讨论/早期conceal与莎雕心理]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：莎雕分析]]",
            "[[饮茶室QA/冰学独立理论与分析/443：Elsa跳崖是Fear驱动]]",
        ],
        "2020-03-09 奇谈。若 Elsa 自己拆坝，Anna 无法独立成事，桥的人类一侧立不住；冻住是考验 Anna，也是四灵安排。后来「不可接受论」是另一套冻住机制，不要互相覆盖。\n\n"
        + dump_text("qitan_theory_6801966599978910392.md"),
    )
    created.append("FH：Athl冻住是为了让Anna独立")

    write_note(
        "冰学独立理论与分析/443：Elsa跳崖是Fear驱动.md",
        "443：Elsa跳崖是Fear驱动",
        "冰学独立理论与分析",
        "❄️冰学奇谈会议室群聊 2020-06-19",
        "2020-06-19 23:05:14",
        "2020-06-25 16:01:38",
        [
            "[[饮茶室QA/冰学讨论/早期conceal与莎雕心理]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：Athl冻住是为了让Anna独立]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：莎雕分析]]",
        ],
        "2020-06 奇谈。443127105：Elsa 最不愿意 Make this right；跳崖是否认已见的真相、Fear 驱动。Anna 独断拆坝才是 Arendelle deserve to stand with you 的理由。\n\n"
        + dump_text("qitan_theory_6842192563254877087.md"),
    )
    created.append("443：Elsa跳崖是Fear驱动")

    write_note(
        "冰学讨论/443：不要解释错误解读.md",
        "443：不要解释错误解读",
        "冰学讨论",
        "❄️冰学奇谈会议室群聊 2020-09-13",
        "2020-09-13 21:44:33",
        "2020-09-13 23:53:14",
        [
            "[[饮茶室QA/冰学独立理论与分析/FH：Visa论F2刻画]]",
            "[[饮茶室QA/冰学讨论/冰二的刻画缺失]]",
            "[[饮茶室QA/冰学讨论/Frozen与其他迪士尼公主片对照]]",
        ],
        "2020-09-13 奇谈。443 逐点反驳「不看 F1 就读不懂 F2」：先问负面评价本身是否合理，不要陷入解释错误解读。\n\n"
        + dump_text("qitan_discussion_6872000908671693395.md"),
    )
    created.append("443：不要解释错误解读")

    write_note(
        "冰学独立理论与分析/FH：You have no right to claim Elsa.md",
        "FH：You have no right to claim Elsa",
        "冰学独立理论与分析",
        "饮茶室群聊 2020-05-19",
        "2020-05-19 22:16:29",
        "2020-05-19 22:16:29",
        [
            "[[饮茶室QA/核心/FrozenHeart语录]]",
            "[[FH：双桥理论]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：EA不基于欲望的真爱]]",
        ],
        "2020-05-19 原文。后来多次重发（2020-08 / 2020-09 / 2024-08），回指本页。\n\n"
        + dump_text("tea_6828559010478129246.md"),
    )
    created.append("FH：You have no right to claim Elsa")

    # Alice reddit append
    vac = ROOT / "冰学讨论/第五灵日常职责真空.md"
    cur = vac.read_text(encoding="utf-8")
    if "Alice" not in cur:
        cur = cur.rstrip() + (
            "\n\n## 2024-07 Alice 转 reddit：第五灵用途\n\n"
            "不是群原创，但是「第五灵没事干」的对照材料。原文+机翻都在。\n\n"
            + dump_text("tea_theory_7392265675968598716.md")
            + "\n"
        )
        cur = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {TODAY}", cur, count=1)
        vac.write_text(cur, encoding="utf-8")
        expanded.append("第五灵日常职责真空")

    # ---- 同人 ----
    # Kristoff folding: keep 馄饨 story paragraphs (first ~2 long blocks)
    kf = dump_text("tea_theory_6878249097519467295.md")
    kf_story = kf.split("> *2020-09-30 20:")[0] if "> *2020-09-30 20:" in kf else kf[:8000]
    write_note(
        "同人/馄饨：Kristoff要去Athl.md",
        "馄饨：Kristoff要去Athl",
        "同人",
        "饮茶室群聊 2020-09-30",
        "2020-09-30 19:59:24",
        "2020-09-30 19:59:24",
        [
            "[[饮茶室QA/同人/MOC-同人]]",
            "[[饮茶室QA/同人/馄饨：Elsa的早晨]]",
        ],
        "Frozen 叙事同人，不是官设。Kristoff 抱怨不能去 Athl，Elsa 提前骑 Nokk 接 Anna。\n\n" + kf_story,
    )
    created.append("馄饨：Kristoff要去Athl")

    write_note(
        "同人/馄饨：Elsa的早晨.md",
        "馄饨：Elsa的早晨",
        "同人",
        "饮茶室群聊 2020-04-28",
        "2020-04-28 05:49:02",
        "2020-04-28 05:49:02",
        [
            "[[饮茶室QA/同人/MOC-同人]]",
            "[[饮茶室QA/同人/馄饨：Kristoff要去Athl]]",
        ],
        "Frozen 叙事同人。Anna 醒来发现 Elsa 在身边。不是车文。\n\n"
        + dump_text("tea_theory_6820511757789515683.md"),
    )
    created.append("馄饨：Elsa的早晨")

    write_note(
        "同人/FH：Our story began.md",
        "FH：Our story began",
        "同人",
        "❄️冰学奇谈会议室群聊 2020-05-02",
        "2020-05-02 02:38:01",
        "2020-05-02 02:38:01",
        [
            "[[饮茶室QA/同人/MOC-同人]]",
            "[[饮茶室QA/核心/冰雪时间线发生顺序（冰雪编年史）]]",
        ],
        "用故事口吻复述 F1 开场误伤，不是官设新剧情。\n\n"
        + dump_text("qitan_6821946875160479438.md"),
    )
    created.append("FH：Our story began")

    write_note(
        "同人/Little Snow：The sky was awake.md",
        "Little Snow：The sky was awake",
        "同人",
        "饮茶室群聊 2025-01-05",
        "2025-01-05 19:22:57",
        "2025-01-05 19:22:57",
        [
            "[[饮茶室QA/同人/MOC-同人]]",
            "[[饮茶室QA/同人/FH：Remember when we were little]]",
        ],
        "与 FH Remember when 同日的 Athl 未归大刀：窗边看见白裙，天亮只剩冷风。\n\n"
        + dump_text("tea_7456390404920552389.md"),
    )
    created.append("Little Snow：The sky was awake")

    write_note(
        "同人/FrozenXX：多年后安葬地.md",
        "FrozenXX：多年后安葬地",
        "同人",
        "饮茶室群聊 2026-07-05",
        "2026-07-05 08:03:18",
        "2026-07-05 08:03:18",
        [
            "[[饮茶室QA/同人/MOC-同人]]",
            "[[饮茶室QA/冰学讨论/Anna死后记忆雪人]]",
        ],
        "梦到多年后 EA 离世、在北地交界隐居读到她们的信。Frozen 叙事同人。\n\n"
        + dump_text("tea_theory_7659101007289547843.md"),
    )
    created.append("FrozenXX：多年后安葬地")

    write_note(
        "同人/FH：Elsa圣诞贺词.md",
        "FH：Elsa圣诞贺词",
        "同人",
        "饮茶室群聊 2020-12-25",
        "2020-12-25 23:06:13",
        "2020-12-25 23:56:53",
        [
            "[[饮茶室QA/同人/MOC-同人]]",
            "[[FH：双桥理论]]",
        ],
        "以 Elsa 口吻写的阿伦戴尔圣诞讲话（参考英女王圣诞演讲）。角色扮演，不是官设。\n\n"
        + dump_text("tea_theory_6910223522961898568.md"),
    )
    created.append("FH：Elsa圣诞贺词")

    # 机制碎片：砍掉已拆走的截断同人，留指针
    frag = ROOT / "冰学讨论/机制与人物碎片.md"
    cur = frag.read_text(encoding="utf-8")
    cur = re.sub(
        r"### 2025-01 Little Snow 小号\n\n> \*2025-01-05 19:22:57.+?(?=\n### |\n## 短析)",
        "### 2025-01 Little Snow 小号\n\n全文见 [[饮茶室QA/同人/Little Snow：The sky was awake]]。\n\n",
        cur,
        count=1,
        flags=re.S,
    )
    cur = re.sub(
        r"### 2020-05 FH\n\n> \*2020-05-02 02:38:01.+?(?=\n### |\n## 短析)",
        "### 2020-05 FH\n\nF1 开场复述全文见 [[饮茶室QA/同人/FH：Our story began]]。\n\n",
        cur,
        count=1,
        flags=re.S,
    )
    cur = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {TODAY}", cur, count=1)
    frag.write_text(cur, encoding="utf-8")
    expanded.append("机制与人物碎片")

    # ---- MOCs ----
    moc_tongren = ROOT / "同人/MOC-同人.md"
    cur = moc_tongren.read_text(encoding="utf-8")
    extra = [
        "- [[饮茶室QA/同人/馄饨：Elsa的早晨]] — 2020-04-28 醒来身边是 Elsa",
        "- [[饮茶室QA/同人/馄饨：Kristoff要去Athl]] — 2020-09-30 Kristoff 抱怨不能去冰川",
        "- [[饮茶室QA/同人/FH：Our story began]] — 2020-05-02 用故事口吻复述 F1 开场",
        "- [[饮茶室QA/同人/FH：Elsa圣诞贺词]] — 2020-12-25 Elsa 口吻圣诞讲话",
        "- [[饮茶室QA/同人/Little Snow：The sky was awake]] — 2025-01-05 窗边白裙，天亮只剩风",
        "- [[饮茶室QA/同人/FrozenXX：多年后安葬地]] — 2026-07-05 梦到 EA 离世读信",
    ]
    for b in extra:
        if b.split("]]")[0] not in cur:
            cur = cur.rstrip() + "\n" + b
    cur = re.sub(r"updated: \d{4}-\d{2}-\d{2}", f"updated: {TODAY}", cur, count=1)
    moc_tongren.write_text(cur.rstrip() + "\n", encoding="utf-8")

    moc = ROOT / "MOC-饮茶室QA.md"
    cur = moc.read_text(encoding="utf-8")
    inserts = [
        (
            "- [[饮茶室QA/冰学独立理论与分析/FH：母女线分析]]",
            "- [[饮茶室QA/冰学独立理论与分析/FH：Athl冻住是为了让Anna独立]] — 冻住是为了让 Anna 独立成桥（2020-03-09）\n"
            "- [[饮茶室QA/冰学独立理论与分析/443：Elsa跳崖是Fear驱动]] — 拒绝已见的真相\n"
            "- [[饮茶室QA/冰学独立理论与分析/FH：You have no right to claim Elsa]] — 2020-05-19 原文；后来重发回指",
        ),
        (
            "- [[饮茶室QA/冰学讨论/Anna是否在TNRT前有责任感]]",
            "- [[饮茶室QA/冰学讨论/443：不要解释错误解读]] — 不看 F1 也能读 F2 的逐点反驳",
        ),
        (
            "- [[饮茶室QA/同人/可可：深潜水兵后记]]",
            "- [[饮茶室QA/同人/馄饨：Elsa的早晨]] — 2020-04-28\n"
            "- [[饮茶室QA/同人/馄饨：Kristoff要去Athl]] — 2020-09-30\n"
            "- [[饮茶室QA/同人/FH：Our story began]] — F1 开场复述\n"
            "- [[饮茶室QA/同人/FH：Elsa圣诞贺词]] — Elsa 口吻贺词\n"
            "- [[饮茶室QA/同人/Little Snow：The sky was awake]] — 2025-01-05 大刀\n"
            "- [[饮茶室QA/同人/FrozenXX：多年后安葬地]] — 2026-07-05",
        ),
    ]
    for needle, add in inserts:
        if "Athl冻住是为了让Anna独立" in cur and needle.startswith("- [[饮茶室QA/冰学独立理论与分析/FH：母女线"):
            continue
        if needle in cur and add.strip().split("\n")[0] not in cur:
            cur = cur.replace(needle, needle + "\n" + add, 1)
    if "2026-08-22：全量 gap-fill" not in cur:
        cur = cur.replace(
            "- 2026-08-22：回退误拒（Runeard / 2020 解冻原文 / Voice 全文 / Frozen 同人）；缩写回指原文；新建 `同人/`",
            "- 2026-08-22：回退误拒（Runeard / 2020 解冻原文 / Voice 全文 / Frozen 同人）；缩写回指原文；新建 `同人/`\n"
            "- 2026-08-22：全量 gap-fill：reject 里 Frozen 叙事同人/长分析按原文入库；缩写回指 2020/2021 JSONL；NSFW 车文仍 reject",
        )
    moc.write_text(cur, encoding="utf-8")

    # FrozenHeart语录 index
    yu = ROOT / "核心/FrozenHeart语录.md"
    cur = yu.read_text(encoding="utf-8")
    if "Athl冻住是为了让Anna独立" not in cur:
        cur = cur.replace(
            "- [[饮茶室QA/冰学独立理论与分析/FH：第五灵与Noaidi中介]] — 萨满中介透镜。",
            "- [[饮茶室QA/冰学独立理论与分析/FH：第五灵与Noaidi中介]] — 萨满中介透镜。\n"
            "- [[饮茶室QA/冰学独立理论与分析/FH：Athl冻住是为了让Anna独立]] — 冻住是为了让 Anna 独立成桥。\n"
            "- [[饮茶室QA/冰学独立理论与分析/FH：You have no right to claim Elsa]] — 2020-05-19 原文。",
        )
        yu.write_text(cur, encoding="utf-8")

    # decisions
    dec_obj = json.loads((DATA / "decisions.json").read_text(encoding="utf-8"))
    decs = dec_obj["decisions"]
    flipped = 0
    noted = 0
    for cid, (verdict, note) in FLIP.items():
        prev = (decs.get(cid) or {}).get("verdict")
        decs[cid] = {"verdict": verdict, "note": note}
        if prev == "reject":
            flipped += 1
    for cid, note in STAY_REJECT.items():
        if cid in decs:
            if decs[cid].get("verdict") != "reject":
                continue
            if not decs[cid].get("note"):
                decs[cid]["note"] = note
                noted += 1
            elif note not in (decs[cid].get("note") or ""):
                decs[cid]["note"] = note
                noted += 1
        else:
            decs[cid] = {"verdict": "reject", "note": note}
            noted += 1
    # extra keep ids that dumps used
    extra_keep = {
        "qitan:6803207692073560619": ("keep_theory", "truth theory 2020-03-12 原文 msgid"),
        "qitan:6803704562952993320": ("keep_theory", "双人格 2020-03-13 msgid"),
        "qitan:6806403181716104449": ("keep_theory", "ITU 2020-03-21 残稿"),
        "qitan:6805200437015210070": ("keep_discussion", "Once upon a time 奇谈第一句"),
        "qitan:6821946875160479438": ("keep_discussion", "Our story began 同人"),
        "tea:7456390404920552389": ("keep_discussion", "Little Snow sky was awake"),
        "tea:6828559010478129246": ("keep_theory", "You have no right 2020-05-19"),
    }
    # these aren't candidate keys; skip if not in decs
    atomic_write_json(DATA / "decisions.json", {"decisions": decs})

    report = {
        "flipped_reject_to_keep": flipped,
        "stay_reject_noted": noted,
        "created": created,
        "expanded": expanded,
        "flip_ids": list(FLIP),
    }
    (DATA / "_gapfill_apply_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("flipped", flipped, "created", len(created), "expanded", len(expanded))
    print("created:", created)
    print("expanded:", expanded)


if __name__ == "__main__":
    main()
