#!/usr/bin/env python3
"""File clustered notes from new keepers; remap leftover keepers; reject leftover junk."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
VAULT = ROOT

JUNK_RE = re.compile(
    r"可可无奈|岚姐|神目|小v挽着|Shape of You|Do you wanna build a snowman Come on|"
    r"港迪会员礼盒|欧洲票房|COVID|病毒在生物体外|欧洲靴子|"
    r"昨晚，我梦到自己|穿越到了冰雪奇缘|感冒了，从现在开始你要躺|"
    r"旅行者要我对群聊|冰学生求带|"
    r"The club isn't the best place|I love you, baby  Oh, oh|"
    r"patreon.com|现在来盘点一下娜娜的衣服|"
    r"ice lolly|heaven to hell and back|"
    r"你画我猜|小蜥蜴好像依然沉浸|"
    r"A：听好了elsa|"
    r"SERIOUSLY, COULD IT BE ANY COLDER",
    re.I,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp") if path.suffix else path.with_suffix(".tmp")
    # decisions.json uses .tmp
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def by_id(keepers: dict) -> dict:
    out = {}
    for items in keepers.values():
        for x in items:
            out[x["id"]] = x
    return out


def fmt_quote(q: dict, cap: int = 1100) -> str:
    text = (q.get("text") or "").replace("\r\n", "\n").replace("**", "")
    if len(text) > cap:
        text = text[:cap].rstrip() + "…"
    who = f"> *{q.get('time') or ''}  {q.get('name') or ''}*"
    body = []
    for ln in text.split("\n"):
        if ln.strip():
            body.append("> " + ln.rstrip())
        else:
            body.append(">")
    return who + "\n" + "\n".join(body)


def quotes_for(item: dict, n: int = 2, cap: int = 1100) -> str:
    qs = item.get("quotes") or []
    if not qs:
        preview = item.get("preview") or ""
        qs = [{"time": item.get("time"), "name": item.get("author"), "text": preview}]
    return "\n\n".join(fmt_quote(q, cap) for q in qs[:n])


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
updated: 2026-08-22
---
"""


def write_note(relpath: str, title: str, area: str, source: str, items: list, body: str, related: list):
    times = [x["time"] for x in items if x.get("time")]
    t0 = min(times) if times else "2020-01-01 00:00:00"
    t1 = max(times) if times else t0
    md = yaml_block(title, area, source, t0, t1, related)
    md += f"\n# {title}\n\n"
    md += f"出处时间：{t0}" + (f" → {t1}" if t1 != t0 else "") + "\n\n"
    md += body.rstrip() + "\n"
    path = VAULT / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    return path, t0, t1


def append_section(relpath: str, heading: str, text: str):
    path = VAULT / relpath
    cur = path.read_text(encoding="utf-8")
    if heading in cur and text[:80] in cur:
        return False
    # bump updated
    cur = re.sub(r"updated: \d{4}-\d{2}-\d{2}", "updated: 2026-08-22", cur, count=1)
    if not cur.endswith("\n"):
        cur += "\n"
    cur += f"\n## {heading}\n\n{text.rstrip()}\n"
    path.write_text(cur, encoding="utf-8")
    return True


def main():
    keepers = load(DATA / "_new_keepers.json")
    idx = by_id(keepers)
    dec_obj = load(DATA / "decisions.json")
    decs = dec_obj["decisions"]
    created = []
    appended = []
    filed_ids = set()

    def take(*ids):
        items = []
        for i in ids:
            if i in idx:
                items.append(idx[i])
                filed_ids.add(i)
        return items

    def mark(ids, verdict, note):
        for i in ids:
            if i in decs:
                decs[i] = {"verdict": verdict, "note": note}

    # ---- notes ----
    # 1 struct
    its = take(
        "tea:theory:7665457168561617774",
        "tea:theory:7608707201839514010",
        "qitan:theory:6815567992477322023",
    )
    body = (
        "主张：结构主义在这里首先是策略，不是给 Frozen 贴学派标签。JU 用 Newcomb 单盒/双盒区分「故事内部推理」和「观众接受」；"
        "Athl 刻画缺失会逼出「弱故事、重人物」的权衡；FH 2020 年已抱怨世界观极大、正片几乎不明示。"
        "四层法与软事实见 [[饮茶室QA/冰学独立理论与分析/JU：质感分析理论整理框架]]；作者论碎片见 [[饮茶室QA/冰学讨论/冰学观众学与IP演化]]。\n\n"
        "### 2026-07 Newcomb 与单盒双盒\n\n"
        + quotes_for(idx["tea:theory:7665457168561617774"], 1, 900)
        + "\n\n### 2026-02 弱故事、重人物\n\n"
        + quotes_for(idx["tea:theory:7608707201839514010"], 1, 900)
        + "\n\n### 2020-04 奇谈 世界观不做明示\n\n"
        + quotes_for(idx["qitan:theory:6815567992477322023"], 1, 700)
        + "\n\n## 短析\n\n"
        "单盒像因果决策派：从 Elsa 已做出的选择倒推世界必须自洽。双盒像证据派：先问电影给没给足够信息。"
        "Athl 空白不是「等 F3」，而是质感层要单独建模的断裂。"
    )
    write_note(
        "冰学讨论/结构主义与质感.md",
        "结构主义与质感",
        "冰学讨论",
        "饮茶室 / ❄️冰学奇谈会议室群聊摘录",
        its,
        body,
        [
            "[[饮茶室QA/冰学独立理论与分析/JU：质感分析理论整理框架]]",
            "[[饮茶室QA/冰学讨论/冰学观众学与IP演化]]",
            "[[饮茶室QA/冰学独立理论与分析/纳西妲：叙事闭合与和声终止]]",
        ],
    )
    created.append("冰学讨论/结构主义与质感.md")

    # 2 disney compare
    its = take(
        "tea:theory:6852347404449656156",
        "qitan:theory:6877948257267258723",
        "qitan:theory:6813683846784674221",
    )
    body = (
        "主张：把 Frozen 放进近十年迪士尼「Who am I / 以何面目示人」序列里看，而不是只和续作自我对照。"
        "㫪 2020 年串爱丽丝→勇敢传说→冰雪→海洋奇缘→花木兰；FH 看完真人花木兰觉得心路像「没误伤 Anna 的 Elsa」；"
        "ZQ 用发型象征解释 Anna 为王。Rapunzel 回科罗娜的对照见既有讨论摘录，Zootopia 另页 [[饮茶室QA/冰学讨论/冰雪与疯狂动物城的反歧视对照]]。\n\n"
        "### 2020-07 Who am I 序列\n\n"
        + quotes_for(idx["tea:theory:6852347404449656156"], 1, 1000)
        + "\n\n### 2020-09 奇谈 花木兰对照\n\n"
        + quotes_for(idx["qitan:theory:6877948257267258723"], 1, 800)
        + "\n\n### 2020-04 奇谈 头发象征\n\n"
        + quotes_for(idx["qitan:theory:6813683846784674221"], 1, 800)
        + "\n\n## 短析\n\n"
        "对照用处是类型功能：公主片的自我命名仪式，Frozen 把它做成了双人桥（Elsa 的 SY / Anna 的女王）。"
        "一一映射角色会把花木兰和 Elsa 焊死，FH 自己也只说「有些像」。"
    )
    write_note(
        "冰学讨论/Frozen与其他迪士尼公主片对照.md",
        "Frozen与其他迪士尼公主片对照",
        "冰学讨论",
        "饮茶室 / ❄️冰学奇谈会议室群聊摘录",
        its,
        body,
        [
            "[[饮茶室QA/冰学讨论/冰学观众学与IP演化]]",
            "[[饮茶室QA/冰学讨论/冰雪与疯狂动物城的反歧视对照]]",
            "[[饮茶室QA/冰学讨论/F2是否放弃了Anna优先]]",
        ],
    )
    created.append("冰学讨论/Frozen与其他迪士尼公主片对照.md")

    # 3 madoka
    its = take(
        "tea:discussion:7645897956208629336",
        "tea:theory:7684670969624070662",
        "tea:theory:7465946011591891475",
    )
    body = (
        "主张：Madoka 不是同人素材库，而是比较框架。圆焰的信息差用来理解 Elsa 对 Anna 的 conceal；"
        "友情/爱情三标准用来卡 EA 的爱不是占有欲；JU 用东方物喻 vs 好莱坞可量化模式，解释 Frozen 和魔圆为什么都能「形式很满、物喻更狠」。"
        "双向轮回思想实验见 [[FH：双向轮回假设]]；信息差见 [[饮茶室QA/冰学讨论/Elsa对Anna保持信息差]]。\n\n"
        "### 2025-11 圆焰信息差\n\n"
        + quotes_for(idx["tea:discussion:7645897956208629336"], 1, 900)
        + "\n\n### 2026-02 排他性 / 未来展望 / 身体诚实\n\n"
        + quotes_for(idx["tea:theory:7684670969624070662"], 1, 900)
        + "\n\n### 2025-01 东方物喻与好莱坞形式\n\n"
        + quotes_for(idx["tea:theory:7465946011591891475"], 1, 800)
        + "\n\n## 短析\n\n"
        "比较文学此处的产出是机制：谁对谁隐瞒、爱是否要求独占、续作情绪是量化模式还是物喻。"
        "不要把 Elsa 写成焰、Anna 写成小圆。"
    )
    write_note(
        "冰学讨论/Frozen与Madoka对照.md",
        "Frozen与Madoka对照",
        "冰学讨论",
        "饮茶室群聊摘录",
        its,
        body,
        [
            "[[FH：双向轮回假设]]",
            "[[饮茶室QA/冰学讨论/Elsa对Anna保持信息差]]",
            "[[饮茶室QA/冰学讨论/Anna死后记忆雪人]]",
        ],
    )
    created.append("冰学讨论/Frozen与Madoka对照.md")

    # 4 ghibli index (thin unique leftover + pointer)
    its = take("tea:discussion:7652198758919377107") if "tea:discussion:7652198758919377107" in idx else []
    body = (
        "宫崎骏 / 吉卜力对照的长文已经写进 [[饮茶室QA/冰学独立理论与分析/纳西妲：冰二结尾Elsa结局折射意识形态倾向分析]]："
        "《你想活出怎样的人生》是 Elsa 选择的精密反转（拒绝留在完美自然秩序），《铃芽之旅》更像 Anna 视角的「回到日常仍连接自然」。"
        "天空之城 / 拉普达作为失败的科技占优透镜，见 [[饮茶室QA/冰学独立理论与分析/JU：Podcast在冰学上的价值]]。"
        "EVA 杯子结构 vs 宫崎骏前现代评价，见 [[饮茶室QA/冰学讨论/Ahtohallan主体性]]。\n\n"
        "本页只做索引，避免把同一段宫崎骏再贴一遍。\n\n"
        "## 短析\n\n"
        "比较点是交汇坐标：个人真实召唤 × 与自然和解。Frozen 2 让 Elsa 走进秩序内部；宫崎骏让真人走回不完美人间。"
    )
    write_note(
        "冰学讨论/Frozen与宫崎骏对照.md",
        "Frozen与宫崎骏对照",
        "冰学讨论",
        "饮茶室群聊摘录（索引）",
        its or [{"time": "2026-06-17 11:07:05"}],
        body,
        [
            "[[饮茶室QA/冰学独立理论与分析/纳西妲：冰二结尾Elsa结局折射意识形态倾向分析]]",
            "[[饮茶室QA/冰学独立理论与分析/JU：Podcast在冰学上的价值]]",
            "[[饮茶室QA/冰学讨论/Ahtohallan主体性]]",
        ],
    )
    created.append("冰学讨论/Frozen与宫崎骏对照.md")

    # 5 myth/theo compare hub
    its = take(
        "tea:theory:7316026895239685969",
        "qitan:theory:6837198723165703474",
        "tea:theory:7652949639843042097",
    )
    body = (
        "主张：神话/童话、萨满隐藏民、基督教素材，都是比较框架，不是把 Frozen 写成宗教寓言。"
        "Little Snow 记 Jennifer Lee 的神话形象定义；FH 2020 年整理设定集里的 Huldrefolk 废案；"
        "土豆拆 Eatnemen Vuelie 原曲里的赞美诗被电影剪掉——素材来源 ≠ 北地人信基督教。"
        "神学作为范式比较见 [[饮茶室QA/冰学讨论/神学方法论是否过度解读]]；Noaidi 见 [[饮茶室QA/冰学独立理论与分析/FH：第五灵与Noaidi中介]]。\n\n"
        "### 2023-12 神话与童话\n\n"
        + quotes_for(idx["tea:theory:7316026895239685969"], 1, 900)
        + "\n\n### 2020-06 奇谈 Huldrefolk\n\n"
        + quotes_for(idx["qitan:theory:6837198723165703474"], 1, 800)
        + "\n\n### 2026-06 Eatnemen Vuelie\n\n"
        + quotes_for(idx["tea:theory:7652949639843042097"], 1, 900)
        + "\n\n## 短析\n\n"
        "JL 的神话人：比日常角色更强、独自扛世界。F1 是童话和解，F2 是神话负担——FOS 作者座谈会也说过 Frozen=fairytale、F2=myth。"
        "Huldrefolk 和赞美诗都提醒：概念艺术 / 原曲可以进比较，不能直接当北地神学正史。"
    )
    write_note(
        "冰学讨论/Frozen与神学神话框架对照.md",
        "Frozen与神学神话框架对照",
        "冰学讨论",
        "饮茶室 / ❄️冰学奇谈会议室群聊摘录",
        its,
        body,
        [
            "[[饮茶室QA/冰学讨论/神学方法论是否过度解读]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：第五灵与Noaidi中介]]",
            "[[饮茶室QA/其他/几内亚-历览前贤国与家]]",
        ],
    )
    created.append("冰学讨论/Frozen与神学神话框架对照.md")

    # 6 other compare hub
    its = take("qitan:theory:6847099885992230421")
    extra = []
    body = (
        "把 Frozen 和其他作品放在同一张比较桌上：Visa/Arinur 的剧作批评、中土/HP 的魔法系统要求、"
        "石头门世界线与玩具总动员「玩具不能被发现」同层级的最高设定（已写入 [[饮茶室QA/冰学独立理论与分析/JU：莎雕分析]]）、"
        "进击的巨人 / Arcane 的叙事容器承压（已写入纳西妲意识形态长文）。本页收尚未独立成篇的对照碎片。\n\n"
        "### 2020-07 奇谈 Visa 与 Arinur\n\n"
        + quotes_for(idx["qitan:theory:6847099885992230421"], 1, 1000)
        + "\n\n## 短析\n\n"
        "FH：Arinur 用「客观文本」论证自己对 F2 Elsa 走向的不满；大众没看见 LIG 负面，所以「不符合大众理解」不是有效判据。"
        "Visa 说刻画贫瘠，FH 同意；说工具人，FH 不同意。专页见 [[饮茶室QA/冰学独立理论与分析/FH：Visa论F2刻画]]。"
    )
    write_note(
        "冰学讨论/Frozen比较文学对照.md",
        "Frozen比较文学对照",
        "冰学讨论",
        "❄️冰学奇谈会议室 / 饮茶室群聊摘录",
        its,
        body,
        [
            "[[饮茶室QA/冰学独立理论与分析/FH：Visa论F2刻画]]",
            "[[饮茶室QA/冰学独立理论与分析/JU：莎雕分析]]",
            "[[饮茶室QA/冰学讨论/Frozen与Madoka对照]]",
            "[[饮茶室QA/冰学讨论/Frozen与宫崎骏对照]]",
        ],
    )
    created.append("冰学讨论/Frozen比较文学对照.md")

    # 7 pixar/sequel
    body = (
        "续作工业对照：Toy Story / Frozen / Zootopia 被 Iger 绑成同一套「unrivaled brands」；"
        "群内也用它讨论续作疲劳、科技 vs 传统玩具的营销切口，以及 F3 是否会落在同一续作坑里。"
        "反歧视结构对照仍以 [[饮茶室QA/冰学讨论/冰雪与疯狂动物城的反歧视对照]] 为准；票房预测原文不收录。\n\n"
        "## 短析\n\n"
        "有用的是结构：第一部解决内部和解，续作被要求扩到跨群体/跨物种。没有分析的开画数字一律 later/reject。"
    )
    write_note(
        "冰学讨论/Frozen与皮克斯续作对照.md",
        "Frozen与皮克斯续作对照",
        "冰学讨论",
        "饮茶室群聊摘录",
        [{"time": "2023-02-09 06:40:58"}, {"time": "2024-10-09 13:25:30"}],
        body,
        [
            "[[饮茶室QA/冰学讨论/冰雪与疯狂动物城的反歧视对照]]",
            "[[饮茶室QA/冰学讨论/冰学观众学与IP演化]]",
        ],
    )
    created.append("冰学讨论/Frozen与皮克斯续作对照.md")

    # 8 ITU 不和谐 + 转调 + Iduna scarf
    its = take(
        "qitan:theory:6805940592731310053",
        "qitan:theory:6808391142681671136",
        "qitan:theory:6813455935202976059",
    )
    body = (
        "主张：ITU 的「不和谐」是结构，不是唱功问题。Michmh 从调性/场景/情感三层反差入手；"
        "木瓜给转调顺序（多利安小调 → 远关系 C 大调）当 Elsa 开始回应召唤的音乐证据；"
        "FH 补 Iduna 围巾：something wrong 时找妈妈，才能接上 SY 的 you are the one。"
        "正片第一次听见 Voice 见 [[饮茶室QA/冰学独立理论与分析/FH：ITU第一次听见the Voice]]。\n\n"
        "### 2020-03 奇谈 ITU 不和谐感\n\n"
        + quotes_for(idx["qitan:theory:6805940592731310053"], 1, 900)
        + "\n\n### 2020-03 奇谈 转调\n\n"
        + quotes_for(idx["qitan:theory:6808391142681671136"], 1, 900)
        + "\n\n### 2020-04 奇谈 围巾线索\n\n"
        + quotes_for(idx["qitan:theory:6813455935202976059"], 1, 800)
        + "\n\n## 短析\n\n"
        "音乐分析在这里是叙事功能：远关系转调 = 回应召唤；围巾 = 母女线提前接线。不要把转调写成乐理竞赛。"
    )
    write_note(
        "冰学独立理论与分析/Michmh：ITU不和谐与转调.md",
        "Michmh：ITU不和谐与转调",
        "冰学独立理论与分析",
        "❄️冰学奇谈会议室群聊 2020-03",
        its,
        body,
        [
            "[[饮茶室QA/冰学独立理论与分析/FH：ITU第一次听见the Voice]]",
            "[[FH：母女线分析]]",
            "[[FH：SY Metaphor]]",
        ],
    )
    created.append("冰学独立理论与分析/Michmh：ITU不和谐与转调.md")

    # 9 dual personality / magic no will
    its = take(
        "qitan:theory:6803704562952993320",
        "tea:theory:6934027242528082415",
        "qitan:theory:6851551642572552253",
    )
    body = (
        "主张：所谓「魔法自己的意识」是 Elsa 人格的一半，不是附身。2020-03 奇谈双人格稿；2021-02 明确魔法无独立意识；"
        "ChaosIce 把 F2 收成两句：人性/魔法互相压抑 + conceal 式扛责。"
        "完整的灵见 [[饮茶室QA/冰学独立理论与分析/FH：完整的灵也是完整的人]]。\n\n"
        "### 2020-03 奇谈 双人格\n\n"
        + quotes_for(idx["qitan:theory:6803704562952993320"], 1, 900)
        + "\n\n### 2021-02 魔法无独立意识\n\n"
        + quotes_for(idx["tea:theory:6934027242528082415"], 1, 900)
        + "\n\n### 2020-07 奇谈 两个核心矛盾\n\n"
        + quotes_for(idx["qitan:theory:6851551642572552253"], 1, 700)
        + "\n\n## 短析\n\n"
        "这是双桥的早期表述：不是两个人抢身体，是同一生命体的两面。F2 看起来「点到为止」，正因为外化的 storm 被收掉了。"
    )
    write_note(
        "冰学独立理论与分析/FH：双人格与魔法无独立意识.md",
        "FH：双人格与魔法无独立意识",
        "冰学独立理论与分析",
        "❄️冰学奇谈会议室 / 饮茶室群聊摘录",
        its,
        body,
        [
            "[[饮茶室QA/冰学独立理论与分析/FH：完整的灵也是完整的人]]",
            "[[FH：双桥理论]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：Visa论F2刻画]]",
        ],
    )
    created.append("冰学独立理论与分析/FH：双人格与魔法无独立意识.md")

    # 10 truth theory
    its = take(
        "qitan:theory:6803701079623183928",
        "qitan:theory:6803207692073560619",
    )
    body = (
        "主张：四灵封林不只是惩罚建坝，也是把「Find the truth」做成必须有人来完成的机制。"
        "Pabbie 极光：The past is not what it seems / A wrong demands to be righted。"
        "早期奇谈稿，和后来的考核/机制杀可对读，不要互相覆盖。\n\n"
        + quotes_for(idx["qitan:theory:6803701079623183928"], 1, 1100)
        + "\n\n## 短析\n\n"
        "封林 = 停住时间，直到有人能 right the wrong。第五灵是解题人，不是风景。"
    )
    write_note(
        "冰学独立理论与分析/FH：truth theory与封林.md",
        "FH：truth theory与封林",
        "冰学独立理论与分析",
        "❄️冰学奇谈会议室群聊 2020-03",
        its,
        body,
        [
            "[[饮茶室QA/冰学讨论/第五灵考核]]",
            "[[饮茶室QA/冰学讨论/大坝对北地的作用]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：Ahtohallan是四灵之母]]",
        ],
    )
    created.append("冰学独立理论与分析/FH：truth theory与封林.md")

    # 11 Olaf snowmen / OFA / 永冬
    its = take(
        "tea:theory:6929523434728004479",
        "qitan:theory:6940371019507122",
        "tea:discussion:7064804829561692",
    )
    body = (
        "三则设定向短论：Olaf 反映 Elsa 当时心理；OFA 从「第一层编剧」被重评为第三层（tradition 在人不在物）；"
        "Elsa 死后暴风雪/雪人会散，永冬大概率不随她死而解——因为永冬是 curse 级事件，不是体温开关。\n\n"
        "### 2021-02 Olaf 与当时心理\n\n"
        + quotes_for(idx["tea:theory:6929523434728004479"], 1, 800)
        + "\n\n### 2021-03 奇谈 错怪 OFA\n\n"
        + quotes_for(idx["qitan:theory:6940371019507122"], 1, 800)
        + "\n\n### 2022-02 永冬\n\n"
        + quotes_for(idx["tea:discussion:7064804829561692"], 1, 800)
        + "\n\n## 短析\n\n"
        "OFA 的翻案很重要：合家欢短片也可以是主题句，不一定是注水。永冬则卡住「Elsa 死了冬天就没了」的脑补。"
    )
    write_note(
        "冰学独立理论与分析/FH：Olaf心理与OFA永冬.md",
        "FH：Olaf心理与OFA永冬",
        "冰学独立理论与分析",
        "饮茶室 / ❄️冰学奇谈会议室群聊摘录",
        its,
        body,
        [
            "[[饮茶室QA/其他/OFA JN时间线细节]]",
            "[[饮茶室QA/冰学讨论/Elsa该不该永生]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：Love is permanent]]",
        ],
    )
    created.append("冰学独立理论与分析/FH：Olaf心理与OFA永冬.md")

    # 12 北寻 Frost Monster / Little Snow FOS / 异乡人 原文
    its = take(
        "tea:theory:7426474236016141731",
        "tea:theory:7466689387266856597",
        "tea:theory:7666015354620130342",
    )
    body = (
        "官方小说读法三则。北寻重读 Elsa and the Frost Monster；Little Snow 把 FOS 祖辈压力接进 F2 弧光；"
        "异乡人 2026-07 强制区分白纸黑字与外网脑补——正片没写「厌王宫」，小说内心独白才有枷锁感。\n\n"
        "### 2024-10 Frost Monster\n\n"
        + quotes_for(idx["tea:theory:7426474236016141731"], 1, 900)
        + "\n\n### 2025-02 FOS 进 F2\n\n"
        + quotes_for(idx["tea:theory:7466689387266856597"], 1, 800)
        + "\n\n### 2026-07 原文 vs 脑补\n\n"
        + quotes_for(idx["tea:theory:7666015354620130342"], 1, 900)
        + "\n\n## 短析\n\n"
        "方法论：小说可以补心理，不能反写正片没给的事实。FOS 的「History seemed to be full of great leaders」是质感，不是 Elsa 亲口承认祖辈压力。"
    )
    write_note(
        "冰学讨论/官方小说读法：FOS与Frost Monster.md",
        "官方小说读法：FOS与Frost Monster",
        "冰学讨论",
        "饮茶室群聊摘录",
        its,
        body,
        [
            "[[饮茶室QA/冰学独立理论与分析/FH：FOS的Nattmara与坏女王恐惧]]",
            "[[Klein：PN在冰学上的价值]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：女王身份不是束缚]]",
        ],
    )
    created.append("冰学讨论/官方小说读法：FOS与Frost Monster.md")

    # 13 methodology / 事件型IP / A线早于E线 / 片尾LIG
    its = take(
        "tea:theory:7664212293060009133",
        "qitan:discussion:6842659131953900092",
        "tea:discussion:7035639438262819821",
        "qitan:theory:6837004326322853216",
    )
    body = (
        "方法论与观众学补页。纳西妲：Frozen 是事件型 IP 不是日常型 IP，空窗只能靠同人续命；"
        "FH：A 线（Anna 为王 / TNRT）比 E 线定得早；片尾版 LIG 把电影里多次转折抹平；"
        "codependency 词太病态，不能直接套姐妹。\n\n"
        "### 2026-07 事件型 IP\n\n"
        + quotes_for(idx["tea:theory:7664212293060009133"], 1, 800)
        + "\n\n### 2020-06 奇谈 A 线更早\n\n"
        + quotes_for(idx["qitan:discussion:6842659131953900092"], 1, 700)
        + "\n\n### 2021-11 片尾 LIG\n\n"
        + quotes_for(idx["tea:discussion:7035639438262819821"], 1, 700)
        + "\n\n### 2020-06 奇谈 codependency 词\n\n"
        + quotes_for(idx["qitan:theory:6837004326322853216"], 1, 600)
        + "\n\n## 短析\n\n"
        "商业空窗解释了为什么冰学必须自己养文本。A 线早于 E 线解释了为什么观众觉得 Anna 更顺、Elsa 更隐。"
        "ZQ 的 spare 专页仍见 [[饮茶室QA/冰学讨论/ZQ：Anna的spare与codependency]]。"
    )
    write_note(
        "冰学讨论/事件型IP与A线先定.md",
        "事件型IP与A线先定",
        "冰学讨论",
        "饮茶室 / ❄️冰学奇谈会议室群聊摘录",
        its,
        body,
        [
            "[[饮茶室QA/冰学讨论/冰学观众学与IP演化]]",
            "[[饮茶室QA/其他/Arendelle Archives]]",
            "[[饮茶室QA/冰学讨论/ZQ：Anna的spare与codependency]]",
        ],
    )
    created.append("冰学讨论/事件型IP与A线先定.md")

    # 14 443127105 莎雕早期 conceal
    its = take("qitan:discussion:6841379394563735251")
    body = (
        "2020-06 奇谈：莎雕前 Elsa 的 conceal don't feel——四灵苏醒后把锅揽到自己「想了解魔法」上。"
        "这是后来「沉船支票 / 不可接受论」的早期心理前提，不是另一套冻住机制。\n\n"
        + quotes_for(idx["qitan:discussion:6841379394563735251"], 1, 1100)
        + "\n\n## 短析\n\n"
        "和 FH 莎雕、土豆故事线并读：机制解释「怎么冻」，这页解释「她为什么觉得是自己的错」。"
    )
    write_note(
        "冰学讨论/早期conceal与莎雕心理.md",
        "早期conceal与莎雕心理",
        "冰学讨论",
        "❄️冰学奇谈会议室群聊 2020-06",
        its,
        body,
        [
            "[[饮茶室QA/冰学讨论/再论莎雕]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：莎雕分析]]",
            "[[饮茶室QA/冰学独立理论与分析/土豆：莎雕分析]]",
        ],
    )
    created.append("冰学讨论/早期conceal与莎雕心理.md")

    # 15 deleted a place of our own / 议会
    its = take(
        "tea:theory:6975732510432996",
        "tea:discussion:6934567553517705596",
    )
    body = (
        "两则生产/设定。FH：deleted scene「a place of our own」里 Elsa 在阿村被冲毁后仍轻松说四灵需要我，OOC 到每次重看冒冷汗——"
        "这是后来「没事干却离开会崩人设」的废案反证。议会：gates close 时 Agnarr 已解散议会，父母遇难时城堡里没有 Peterssen 式人选。\n\n"
        "### 2021-06 a place of our own\n\n"
        + quotes_for(idx["tea:theory:6975732510432996"], 1, 800)
        + "\n\n### 2021-03 议会解散\n\n"
        + quotes_for(idx["tea:discussion:6934567553517705596"], 1, 600)
        + "\n\n## 短析\n\n"
        "废案证明主创一度会写出「成仙后无痛离开」。正片没采用，不等于正片已经写清日常职责。"
    )
    write_note(
        "冰学独立理论与分析/FH：废案a place of our own与议会.md",
        "FH：废案a place of our own与议会",
        "冰学独立理论与分析",
        "饮茶室群聊摘录",
        its,
        body,
        [
            "[[饮茶室QA/冰学独立理论与分析/FH：没事干却离开会崩人设]]",
            "[[饮茶室QA/核心/冰雪时间线发生顺序（冰雪编年史）]]",
            "[[饮茶室QA/冰学讨论/第五灵日常职责真空]]",
        ],
    )
    created.append("冰学独立理论与分析/FH：废案a place of our own与议会.md")

    # 16 雪中火 mythical character / 443 讨论
    its = take(
        "tea:theory:6917601650681305732",
        "tea:discussion:6917603354408254735",
    )
    body = (
        "2021-01：把 Elsa 推进到生与死之后，个人偏爱（她必须是人）会被设定集「Mythical Character」打穿。"
        "这是永生论之前的现场，不是结论。续见 [[饮茶室QA/冰学讨论/Elsa该不该永生]]。\n\n"
        + quotes_for(idx["tea:theory:6917601650681305732"], 1, 900)
        + "\n\n"
        + quotes_for(idx["tea:discussion:6917603354408254735"], 1, 700)
        + "\n\n## 短析\n\n"
        "偏爱可以保留，但不能假装设定集没把她写成 mythical。FH 后来的「完整的灵也是完整的人」就是冲着这个裂口去补。"
    )
    write_note(
        "冰学讨论/Mythical Character与永生偏爱.md",
        "Mythical Character与永生偏爱",
        "冰学讨论",
        "饮茶室群聊 2021-01",
        its,
        body,
        [
            "[[饮茶室QA/冰学讨论/Elsa该不该永生]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：完整的灵也是完整的人]]",
            "[[饮茶室QA/冰学独立理论与分析/FH：第五灵必须保留人性面]]",
        ],
    )
    created.append("冰学讨论/Mythical Character与永生偏爱.md")

    # append 语录 shorts - skip, 语录 is for slogans
    # append 观众学
    if append_section(
        "冰学讨论/冰学观众学与IP演化.md",
        "2026-07 Newcomb 单盒双盒",
        "JU 把 Newcomb 悖论引进群史：单盒派从故事内部推理结局必然，双盒派问信息给没给够。专页见 [[饮茶室QA/冰学讨论/结构主义与质感]]。",
    ):
        appended.append("冰学讨论/冰学观众学与IP演化.md")
    if append_section(
        "冰学独立理论与分析/FH：母女线分析.md",
        "2020-04 奇谈 围巾",
        "SY 能醒悟「自己就是自己在找的人」，前提是 something wrong 时 Elsa 会戴上 Iduna 的围巾。摘录见 [[饮茶室QA/冰学独立理论与分析/Michmh：ITU不和谐与转调]]。",
    ):
        appended.append("冰学独立理论与分析/FH：母女线分析.md")
    if append_section(
        "冰学讨论/再论莎雕.md",
        "2020-06 奇谈 conceal 前提",
        "443127105：ITU 后 Elsa 把四灵苏醒当成自己「想了解魔法」的锅。这是莎雕心理前提，不是冻住公式。见 [[饮茶室QA/冰学讨论/早期conceal与莎雕心理]]。",
    ):
        appended.append("冰学讨论/再论莎雕.md")
    if append_section(
        "核心/FrozenHeart语录.md",
        "2020–2021 口号补",
        "- 魔法没有独立意识，那是人格的一半。见 [[饮茶室QA/冰学独立理论与分析/FH：双人格与魔法无独立意识]]\n"
        "- 封林是为了 Find the truth。见 [[饮茶室QA/冰学独立理论与分析/FH：truth theory与封林]]\n"
        "- 片尾版 LIG 把转折抹平。见 [[饮茶室QA/冰学讨论/事件型IP与A线先定]]\n"
        "- a place of our own 废案 OOC。见 [[饮茶室QA/冰学独立理论与分析/FH：废案a place of our own与议会]]",
    ):
        appended.append("核心/FrozenHeart语录.md")

    # map leftover keepers
    CLUSTER_NOTE = {
        "struct_texture": "饮茶室QA/冰学讨论/结构主义与质感.md",
        "comp_disney": "饮茶室QA/冰学讨论/Frozen与其他迪士尼公主片对照.md",
        "comp_madoka": "饮茶室QA/冰学讨论/Frozen与Madoka对照.md",
        "comp_ghibli": "饮茶室QA/冰学讨论/Frozen与宫崎骏对照.md",
        "comp_myth_theo": "饮茶室QA/冰学讨论/Frozen与神学神话框架对照.md",
        "comp_other": "饮茶室QA/冰学讨论/Frozen比较文学对照.md",
        "comp_pixar": "饮茶室QA/冰学讨论/Frozen与皮克斯续作对照.md",
        "sha_diao": "饮茶室QA/冰学讨论/再论莎雕.md",
        "fifth_spirit": "饮茶室QA/冰学独立理论与分析/FH：双人格与魔法无独立意识.md",
        "athl": "饮茶室QA/冰学独立理论与分析/FH：truth theory与封林.md",
        "two_bridge": "饮茶室QA/冰学独立理论与分析/FH：双人格与魔法无独立意识.md",
        "elsa_char": "饮茶室QA/冰学独立理论与分析/FH：双人格与魔法无独立意识.md",
        "anna_char": "饮茶室QA/冰学讨论/Anna是否在TNRT前有责任感.md",
        "itu_voice": "饮茶室QA/冰学独立理论与分析/Michmh：ITU不和谐与转调.md",
        "pn_fos_ds": "饮茶室QA/冰学讨论/官方小说读法：FOS与Frost Monster.md",
        "production": "饮茶室QA/冰学独立理论与分析/FH：废案a place of our own与议会.md",
        "audience_method": "饮茶室QA/冰学讨论/事件型IP与A线先定.md",
        "visa_arinur": "饮茶室QA/冰学讨论/Frozen比较文学对照.md",
        "ofa": "饮茶室QA/冰学独立理论与分析/FH：Olaf心理与OFA永冬.md",
        "ending_leave": "饮茶室QA/冰学讨论/Mythical Character与永生偏爱.md",
        "f3_ip": "饮茶室QA/冰学讨论/事件型IP与A线先定.md",
        "setting_detail": "饮茶室QA/冰学独立理论与分析/FH：废案a place of our own与议会.md",
        "misc_frozen": "饮茶室QA/冰学讨论/机制与人物碎片.md",
    }

    # misc hub
    misc_items = []
    for x in keepers.get("misc_frozen") or []:
        blob = (x.get("preview") or "") + "".join(q.get("text") or "" for q in x.get("quotes") or [])
        if JUNK_RE.search(blob):
            continue
        if len(blob) >= 200 and re.search(r"Elsa|Anna|Frozen|冰雪|Athl|第五灵|莎雕", blob, re.I):
            misc_items.append(x)
    misc_items = sorted(misc_items, key=lambda z: -(z.get("quotes") or [{}])[0].get("n", 0) if z.get("quotes") else 0)[:12]
    chunks = []
    for x in misc_items[:8]:
        filed_ids.add(x["id"])
        chunks.append(f"### {x['time'][:7]} {x['byline']}\n\n" + quotes_for(x, 1, 700))
    misc_body = (
        "六年长尾里不够独立成篇、但仍是 Frozen 机制/人物/设定的碎片。同主题长文已拆走。"
        "歌词堆砌、同人 RP、周边价目不收。\n\n" + "\n\n".join(chunks) + "\n\n## 短析\n\n当索引用。碰到能独立成主张的句子，再拆出去。"
    )
    write_note(
        "冰学讨论/机制与人物碎片.md",
        "机制与人物碎片",
        "冰学讨论",
        "饮茶室 / ❄️冰学奇谈会议室 / 晚宴群聊摘录",
        misc_items or [{"time": "2020-03-01 00:00:00"}],
        misc_body,
        [
            "[[饮茶室QA/冰学讨论/结构主义与质感]]",
            "[[饮茶室QA/核心/FrozenHeart语录]]",
        ],
    )
    created.append("冰学讨论/机制与人物碎片.md")

    # leftover: junk reject or map
    junk_n = 0
    mapped_n = 0
    for cluster, items in keepers.items():
        note_path = CLUSTER_NOTE.get(cluster, "饮茶室QA/冰学讨论/机制与人物碎片.md")
        for x in items:
            cid = x["id"]
            blob = (x.get("preview") or "") + "".join(q.get("text") or "" for q in x.get("quotes") or [])
            if JUNK_RE.search(blob):
                decs[cid] = {"verdict": "reject", "note": "同人/歌词/周边/闲聊漏网"}
                junk_n += 1
                continue
            if cid in filed_ids:
                decs[cid] = {"verdict": x["verdict"], "note": f"filed → {note_path}"}
                mapped_n += 1
                continue
            decs[cid] = {"verdict": x["verdict"], "note": f"clustered → {note_path}"}
            mapped_n += 1

    tmp = DATA / "decisions.json.tmp"
    tmp.write_text(json.dumps({"decisions": decs}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA / "decisions.json")

    report = {
        "created": created,
        "appended": appended,
        "filed_quoted_ids": len(filed_ids),
        "mapped_or_filed": mapped_n,
        "junk_flipped": junk_n,
    }
    (DATA / "_file_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
