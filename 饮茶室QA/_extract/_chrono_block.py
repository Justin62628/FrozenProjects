def md_escape_heading(s: str) -> str:
    return s.replace("**", "").replace("#", "").strip()


def write_out_markdown(payload: dict, out_md: Path) -> None:
    rel = str(out_md.relative_to(QA).as_posix())
    md = render_markdown(payload, rel)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")
    print(f"Markdown {out_md}", file=sys.stderr)


def resolve_out_md(out_md: Path | None, display: str) -> Path:
    if out_md is None:
        return QA / "其他" / suggest_filename(display)
    if not out_md.is_absolute():
        return (QA / out_md).resolve()
    return out_md


def _is_fh(payload: dict) -> bool:
    a = payload.get("author") or {}
    if a.get("prefix") == "FH":
        return True
    name = (a.get("display_name") or "").lower()
    return "frozenheart" in name or name == "fh"


def _ymd(s: str) -> str:
    return (s or "")[:10]


def _cluster_index(clusters: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for c in clusters:
        for key in (
            Path(c.get("vault") or "").name,
            Path(c.get("vault") or "").stem,
            c.get("label") or "",
        ):
            if key:
                out[key] = c
    return out


def _pick(idx: dict[str, dict], stem: str) -> dict | None:
    if stem in idx:
        return idx[stem]
    prefixed = f"FH：{stem}" if not stem.startswith("FH") else stem
    if prefixed in idx:
        return idx[prefixed]
    for k, v in idx.items():
        if stem and stem in k:
            return v
    return None


def _wl(idx: dict[str, dict], stem: str, fallback: str) -> str:
    c = _pick(idx, stem)
    if c and c.get("wikilink"):
        return c["wikilink"]
    return fallback


def _when(idx: dict[str, dict], stem: str, *fields: str, default: str = "") -> str:
    c = _pick(idx, stem)
    if not c:
        return default
    for f in fields:
        v = c.get(f) or ""
        if v:
            return _ymd(v)
    return default or _ymd(c.get("first_time") or "")


def _year_clause(st: dict, year: str) -> str:
    y = (st.get("by_year") or {}).get(year) or {}
    if not y:
        return ""
    return f"本年保留文本 {y.get('n', 0)} 条、{y.get('cjk', 0)} 汉字。"


def _skip_index_cluster(c: dict) -> bool:
    stem = Path(c.get("vault") or "").name
    return stem in INDEX_STEMS


def _related_links(payload: dict) -> list[str]:
    a = payload.get("author") or {}
    related: list[str] = []
    if _is_fh(payload):
        related.extend(
            [
                "[[饮茶室QA/核心/FrozenHeart语录]]",
                "[[FH：双桥理论]]",
            ]
        )
    elif a.get("prefix") == "FH" or "frozenheart" in (
        a.get("display_name") or ""
    ).lower():
        related.append("[[饮茶室QA/核心/FrozenHeart语录]]")

    def first_seen(c: dict) -> str:
        return c.get("vault_time") or c.get("first_essay") or c.get("first_time") or ""

    for c in sorted(payload.get("clusters") or [], key=first_seen):
        if not c.get("wikilink") or _skip_index_cluster(c):
            continue
        if c.get("kind") in {"unbound"}:
            continue
        if c.get("theirs") or c.get("kind") == "fanfic":
            if c["wikilink"] not in related:
                related.append(c["wikilink"])
        if len(related) >= 24:
            break
    if _is_fh(payload):
        for extra in (
            "[[饮茶室QA/冰学讨论/Elsa该不该永生]]",
            "[[饮茶室QA/冰学讨论/Anna死后记忆雪人]]",
            "[[饮茶室QA/同人/MOC-同人]]",
        ):
            if extra not in related:
                related.append(extra)
    related.append("[[饮茶室QA/核心/JU：冰学演化史]]")
    related.append("[[饮茶室QA/核心/冰学发展简史]]")
    return related


def _fh_chronology(payload: dict) -> list[str]:
    """Time-spine narrative. Clustering only labels what appeared when."""
    idx = _cluster_index(payload.get("clusters") or [])
    st = payload.get("stats") or {}

    def L(stem: str, fb: str) -> str:
        return _wl(idx, stem, fb)

    def D(stem: str, *fields: str, default: str = "") -> str:
        return _when(idx, stem, *fields, default=default)

    dual = L(
        "双人格与魔法无独立意识",
        "[[饮茶室QA/冰学独立理论与分析/FH：双人格与魔法无独立意识]]",
    )
    athl_anna = L(
        "Athl冻住是为了让Anna独立",
        "[[饮茶室QA/冰学独立理论与分析/FH：Athl冻住是为了让Anna独立]]",
    )
    truth = L(
        "truth theory与封林",
        "[[饮茶室QA/冰学独立理论与分析/FH：truth theory与封林]]",
    )
    itu = L(
        "ITU第一次听见the Voice",
        "[[饮茶室QA/冰学独立理论与分析/FH：ITU第一次听见the Voice]]",
    )
    noaidi = L(
        "第五灵与Noaidi中介",
        "[[饮茶室QA/冰学独立理论与分析/FH：第五灵与Noaidi中介]]",
    )
    sy = L("SY Metaphor", "[[饮茶室QA/冰学独立理论与分析/FH：SY Metaphor]]")
    runeard = L(
        "Runeard对魔法的不信任",
        "[[饮茶室QA/冰学独立理论与分析/FH：Runeard对魔法的不信任]]",
    )
    ff = L("FF是F2的铺垫", "[[饮茶室QA/冰学独立理论与分析/FH：FF是F2的铺垫]]")
    no_right = L(
        "You have no right to claim Elsa",
        "[[饮茶室QA/冰学独立理论与分析/FH：You have no right to claim Elsa]]",
    )
    mother = L("母女线分析", "[[饮茶室QA/冰学独立理论与分析/FH：母女线分析]]")
    iduna = L("Iduna不是第五灵", "[[饮茶室QA/冰学独立理论与分析/FH：Iduna不是第五灵]]")
    je = L("反对JE", "[[饮茶室QA/冰学独立理论与分析/FH：反对JE]]")
    thaw = L("娜雕解冻分析", "[[饮茶室QA/冰学独立理论与分析/FH：娜雕解冻分析]]")
    visa = L("Visa论F2刻画", "[[饮茶室QA/冰学独立理论与分析/FH：Visa论F2刻画]]")
    human = L(
        "第五灵必须保留人性面",
        "[[饮茶室QA/冰学独立理论与分析/FH：第五灵必须保留人性面]]",
    )
    olaf = L(
        "Olaf心理与OFA永冬",
        "[[饮茶室QA/冰学独立理论与分析/FH：Olaf心理与OFA永冬]]",
    )
    fos = L(
        "FOS的Nattmara与坏女王恐惧",
        "[[饮茶室QA/冰学独立理论与分析/FH：FOS的Nattmara与坏女王恐惧]]",
    )
    scrap = L(
        "废案a place of our own与议会",
        "[[饮茶室QA/冰学独立理论与分析/FH：废案a place of our own与议会]]",
    )
    fear = L("Fear vs Love", "[[饮茶室QA/冰学独立理论与分析/FH：Fear vs Love]]")
    idle = L(
        "没事干却离开会崩人设",
        "[[饮茶室QA/冰学独立理论与分析/FH：没事干却离开会崩人设]]",
    )
    whole = L(
        "完整的灵也是完整的人",
        "[[饮茶室QA/冰学独立理论与分析/FH：完整的灵也是完整的人]]",
    )
    mother_spirits = L(
        "Ahtohallan是四灵之母",
        "[[饮茶室QA/冰学独立理论与分析/FH：Ahtohallan是四灵之母]]",
    )
    loop = L("双向轮回假设", "[[饮茶室QA/其他/FH：双向轮回假设]]")
    immortal = L(
        "Elsa该不该永生",
        "[[饮茶室QA/冰学讨论/Elsa该不该永生]]",
    )
    snowman = L(
        "Anna死后记忆雪人",
        "[[饮茶室QA/冰学讨论/Anna死后记忆雪人]]",
    )
    sha = L("莎雕分析", "[[饮茶室QA/冰学独立理论与分析/FH：莎雕分析]]")
    plant = L("植物人假设", "[[饮茶室QA/冰学独立理论与分析/FH：植物人假设]]")
    queen = L(
        "女王身份不是束缚",
        "[[饮茶室QA/冰学独立理论与分析/FH：女王身份不是束缚]]",
    )
    pn = L(
        "双面动机与PN补全",
        "[[饮茶室QA/冰学独立理论与分析/FH：双面动机与PN补全]]",
    )
    curse = L(
        "魔法是诅咒还是恩赐",
        "[[饮茶室QA/冰学独立理论与分析/FH：魔法是诅咒还是恩赐]]",
    )
    giver = L(
        "Elsa魔法两面性是给予者故意的",
        "[[饮茶室QA/冰学独立理论与分析/FH：Elsa魔法两面性是给予者故意的]]",
    )
    ea_love = L(
        "EA不基于欲望的真爱",
        "[[饮茶室QA/冰学独立理论与分析/FH：EA不基于欲望的真爱]]",
    )
    dungeon = L("F1地牢与Hans", "[[饮茶室QA/冰学独立理论与分析/FH：F1地牢与Hans]]")
    offset = L("F2姐妹错位", "[[饮茶室QA/冰学独立理论与分析/FH：F2姐妹错位]]")
    palace = L(
        "自闭十三年与冰宫",
        "[[饮茶室QA/冰学独立理论与分析/FH：自闭十三年与冰宫]]",
    )
    info_gap = L(
        "自闭期必须保持信息差",
        "[[饮茶室QA/冰学独立理论与分析/FH：自闭期必须保持信息差]]",
    )
    permanent = L(
        "Love is permanent",
        "[[饮茶室QA/冰学独立理论与分析/FH：Love is permanent]]",
    )
    ouat = L(
        "Once upon a time第五灵",
        "[[饮茶室QA/同人/FH：Once upon a time第五灵]]",
    )
    began = L("Our story began", "[[饮茶室QA/同人/FH：Our story began]]")
    huldre = L(
        "Huldrefolk病中back-story",
        "[[饮茶室QA/同人/FH：Huldrefolk病中back-story]]",
    )
    xmas = L("Elsa圣诞贺词", "[[饮茶室QA/同人/FH：Elsa圣诞贺词]]")
    remember = L(
        "Remember when we were little",
        "[[饮茶室QA/同人/FH：Remember when we were little]]",
    )
    y20 = _year_clause(st, "2020")
    y21 = _year_clause(st, "2021")
    y22 = _year_clause(st, "2022")
    y23 = _year_clause(st, "2023")
    y24 = _year_clause(st, "2024")
    y25 = _year_clause(st, "2025")
    y26 = _year_clause(st, "2026")

    dual_d = D("双人格与魔法无独立意识", "vault_time", "first_time", default="2020-03-03")
    athl_d = D("Athl冻住是为了让Anna独立", "vault_time", "first_time", default="2020-03-09")
    truth_d = D("truth theory与封林", "vault_time", "first_essay", default="2020-03-12")
    itu_first = D("ITU第一次听见the Voice", "first_time", default="2020-03-21")
    itu_vault = D("ITU第一次听见the Voice", "vault_time", default="2020-03-21")
    mother_d = D("母女线分析", "vault_time", "first_essay", default="2020-07-22")
    iduna_d = D("Iduna不是第五灵", "vault_time", default="2020-08-17")
    thaw_d = D("娜雕解冻分析", "vault_time", "first_essay", default="2020-10-16")
    visa_d = D("Visa论F2刻画", "vault_time", default="2020-12-11")
    human_d = D("第五灵必须保留人性面", "vault_time", "first_time", default="2021-01-15")
    fos_d = D("FOS的Nattmara与坏女王恐惧", "vault_time", default="2021-04-18")
    fear_d = D("Fear vs Love", "vault_time", "first_essay", default="2023-04-18")
    idle_d = D("没事干却离开会崩人设", "vault_time", "first_time", default="2024-07-06")
    whole_d = D("完整的灵也是完整的人", "vault_time", "first_time", default="2024-08-16")
    ms_vault = D("Ahtohallan是四灵之母", "vault_time", default="2024-09-22")
    sha_d = D("莎雕分析", "vault_time", default="2025-03-18")
    giver_d = D("Elsa魔法两面性是给予者故意的", "vault_time", default="2025-10-12")

    return [
        "## 2020-03 奇谈起步",
        "",
        (y20 + "奇谈立骨架，全年产量最高。") if y20 else "奇谈立骨架，全年产量最高。",
        "",
        f"2020-02-11 进奇谈。Athl / 大灵的讨论从开春就有零散长帖（聚类后来大量吸进 {mother_spirits}，那是 2024 成文，不是 2020 的发明）。真正把后几年反复回指的骨架铺开，是三月。",
        "",
        f"{dual_d} 写出 {dual}：所谓「魔法自己的意识」是 Elsa 人格的一半，不是附身；随后两周展开 LIG，并命名 The Snow Queen / Elsa of Arendelle。同一周已在谈 Iduna 线索（成文要到夏天）。人与自然之桥 + Elsa 人性/魔法之桥也是这季提出的；聚类常被 Athl / 两面种子吸走，全文见 [[FH：双桥理论]]。",
        "",
        f"{athl_d} 两件事并排出现。一是 {athl_anna}：若 Elsa 自己拆坝，人类一侧立不住；冻住是考验 Anna，也是四灵安排。后来「不可接受论」是另一套冻住机制，不要覆盖这篇。二是他反复说 Elsa 内向、什么都自己扛——没有单独成篇，后写入莎雕「单扛」与 {idle}。",
        "",
        f"{truth_d} {truth}：封林是为了 Find the truth，不是单纯惩罚。{itu_first} 起写 ITU 听见 the Voice（奇谈全文 2020-04-03；库内时间 {itu_vault}，见 {itu}）。同月已在摸莎雕心理，独立长文要到 2025。同人 {ouat} 也在三月；种子过宽，当索引即可。",
        "",
        "## 2020-04至06 透镜与F1",
        "",
        f"四月补世界观透镜：{noaidi}（{D('第五灵与Noaidi中介', 'vault_time', 'first_time', default='2020-04-04')}）、{sy}。五月把 F1 / 短片接到 F2：{ff}（conceal 单扛起于短片）、{runeard}（坝像手套）、{no_right}。寿命问题这年夏天已露头，主张后来写在讨论页 {immortal}，不是独立理论笔记。",
        "",
        f"若干句子要等成文：两面性是给予者故意的（成文 {giver_d}）、Fear vs Love（成文 {fear_d}）、女王身份不是束缚（库内 2025-03-23）。同人 {began} 是五月的 F1 开场复述。",
        "",
        "## 2020夏秋 母女线与解冻",
        "",
        f"{mother_d} {mother} 成文：Iduna 线索贯穿 F2。{iduna_d} 奇谈原文是 canonical 的 {iduna}：crucial link，用非魔法方式修补误解，失败后灵才把魔法给女儿。{D('反对JE', 'vault_time', 'first_time', default='2020-08-21')} 表态 {je}（10-13 全文；2024-10-21 重发回指此页）。",
        "",
        f"{thaw_d} 奇谈写出 {thaw}：Anna 的牺牲是 act，Elsa 接受被爱才让 bond 完整、自解永冬。文内说双桥需要重修——Anna 也撑着两座桥，不是 E 站北地 A 站阿村那么绝对。2025-03-18 / 2026-02-23 的「20年理论」缩写回指此页。同日已有 EA 真爱 / selfless sacrifice 的句子，口号收在 2025 的 {ea_love}。自闭期必须保持信息差（圆焰类比）也在十月出现，2026 年才单独成文 {info_gap}。",
        "",
        "## 2020冬 刻画与同人",
        "",
        f"{D('Huldrefolk病中back-story', 'vault_time', default='2020-11-07')} {huldre}。{visa_d} {visa}：同意 F2 刻画贫瘠，不同意 Elsa 沦为工具人。圣诞 {xmas}。不是官设；入口 [[饮茶室QA/同人/MOC-同人]]。",
        "",
        "## 2021 官方小说与人性面",
        "",
        (y21 + "新主张变少，多是把 2020 骨架接到官方小说上。")
        if y21
        else "新主张变少，多是把 2020 骨架接到官方小说上。",
        "",
        f"{human_d} {human}：成仙过 N 代也不丢人性，否则不成 bridge（聚类未单独成簇）。二月 {olaf}；同月在饮茶室向 Vivian 重述 ITU。三月讨论 {scrap}。2021-03-18 口号「真相把她逼进死胡同」是莎雕 2025 长文的先声，回指 {sha}。{fos_d} {fos}：怕 being a bad Queen；把恐惧埋起来才显形。443 的 Fear 驱动跳崖是另一人主张，见 [[饮茶室QA/冰学独立理论与分析/443：Elsa跳崖是Fear驱动]]，不要并进 FH 名下。",
        "",
        "## 2022–2023 低产",
        "",
        " ".join(x for x in (y22, y23) if x) or "发言明显变少。",
        "",
        f"留下的成文主要是 {fear_d} 的 {fear}：要补 E 的 love 和 A 的 fear。2023-02-28 谈 F2 废案 / 硬伤反而养活冰学，是方法论，见 [[饮茶室QA/核心/冰学发展简史]] 与废案页。同年「TNRT 之后 Anna 才有当女王的心态」后来收进 {queen}。",
        "",
        "## 2024 口号化与Athl成文",
        "",
        (y24 + "产量回升，旧主张收成可引用的句子。")
        if y24
        else "产量回升，旧主张收成可引用的句子。",
        "",
        f"{idle_d} {idle}：北地若没事却离开把重担扔给 Anna，人设会崩；群辩入口 [[饮茶室QA/冰学讨论/第五灵日常职责真空]]。{whole_d} {whole}：两面接近平等，深入魔法不是放弃人性——这是 2020 两面论的收束口号，不是另一套形而上学。",
        "",
        f"{ms_vault} 库内写成 {mother_spirits}（大灵是一个意识、幕后大手、记忆深浅反映抗拒）。Athl 关键词从 2020 就把邻题长帖吸进同一簇，当索引用，勿当成这一年才发明。九月 {loop} 是思想实验，不是官设。使命退休 / 大概率不受人类寿命限制写在 {immortal}。",
        "",
        "## 2025 莎雕长文与PN",
        "",
        (y25 + "把几年前的口号写成独立长文。")
        if y25
        else "把几年前的口号写成独立长文。",
        "",
        f"一月同人 {remember}（Athl 未归）。二月 {plant}。三月是成文季：{D('双面动机与PN补全', 'vault_time', default='2025-03-04')} {pn}；{sha_d} 把莎雕写成独立长文 {sha}——真正不能接受的不是「阿村有罪」，而是 cannot face the consequences of breaking the dam；冻住是绝望具象化。局限见 [[饮茶室QA/冰学讨论/FH莎雕分析的局限性讨论]]。同月 {queen}、{curse}。",
        "",
        f"{giver_d} {giver}：两面性是对 Arendelle 的测试。同月收束 {ea_love}（Love is selfless sacrifice；Anna 必须保持人类）。十一月库内写成 {dungeon}（论点 2020-03 已有，成文是回指）。",
        "",
        "## 2026 回指不是新论",
        "",
        (y26 + "解冻 / 自闭 / 信息差帖是回指 2020，不是新发明。")
        if y26
        else "解冻 / 自闭 / 信息差帖是回指 2020，不是新发明。",
        "",
        f"{D('F2姐妹错位', 'vault_time', default='2026-02-17')} {offset} 把 13 年错位和 together 愈合单独成文，{thaw} 里 already 写过。{D('自闭十三年与冰宫', 'vault_time', default='2026-02-24')} {palace} 是娜雕童年 / 冰宫摘段。{D('自闭期必须保持信息差', 'vault_time', default='2026-03-29')} {info_gap} 圆焰类比更早，见 [[饮茶室QA/冰学讨论/Elsa对Anna保持信息差]]。{D('Love is permanent', 'vault_time', default='2026-03-11')} {permanent}：Olaf，物质会变、爱与精神遗产不变。讨论页 {snowman}（冰川只有 Anna 形的门）他有参与。编剧「没必要的设定不去碰」见 [[饮茶室QA/冰学讨论/编剧对没必要的设定不会去碰]]，不是他单独成论。",
        "",
        "## 未绑到现有笔记的簇",
        "",
        "脚本里 unsupervised 簇多数是链接 / 网盘 / 闲聊，或已被上面某段覆盖的邻接长帖。不新开独立理论。最大一簇是「没贴上种子的长帖池」，口号「广义上只要严格遵循有效官方材料…都可算作冰学」只是最早一条，不是独立理论名。Kristoff 在 F2 的功能性、EA 同人倾向、网盘链、广告不单独立项。",
        "",
    ]


def _generic_chronology(payload: dict) -> list[str]:
    """Year-spine for non-FH authors: first-seen, then later restatements."""
    st = payload.get("stats") or {}
    clusters = [
        c
        for c in payload.get("clusters") or []
        if not _skip_index_cluster(c)
        and (
            c.get("theirs")
            or c.get("kind") in {"fanfic", "discussion", "other"}
            or (not c.get("vault") and (c.get("cjk") or 0) >= 800)
        )
    ]

    events: list[tuple[str, str, dict]] = []
    for c in clusters:
        first = c.get("first_time") or ""
        vault = c.get("vault_time") or ""
        if first:
            events.append((first, "提出", c))
        if vault and _ymd(vault) != _ymd(first) and _ymd(vault)[:4] != _ymd(first)[:4]:
            events.append((vault, "成文", c))
        for s in c.get("stages") or []:
            if s.get("kind") == "recap" and s.get("time"):
                events.append((s["time"], "回指", c))
    events.sort(key=lambda x: x[0])

    parts: list[str] = []
    current = ""
    shown_ids: set[tuple[str, str]] = set()
    for t, kind, c in events:
        year = _ymd(t)[:4] or "未知"
        if year != current:
            current = year
            parts.append(f"## {year}")
            parts.append("")
            clause = _year_clause(st, year)
            if clause:
                parts.append(clause)
                parts.append("")
        key = (c.get("id") or c.get("label") or "", kind)
        if key in shown_ids:
            continue
        if kind != "提出" and (c.get("id") or c.get("label"), "提出") not in {
            (x[0], "提出") for x in shown_ids
        }:
            pass
        shown_ids.add(key)
        link = c.get("wikilink") or md_escape_heading(c.get("label") or "")
        claim = (c.get("claim") or "").split("提出者")[0].strip()
        day = _ymd(t)
        if kind == "回指":
            line = f"{day} 回指 {link}，不是新论。"
        elif kind == "成文":
            line = f"{day} 库内成文 {link}。"
            if claim:
                line += claim
        else:
            line = f"{day} 提出 {link}。"
            if claim:
                line += claim
        parts.append(line)
        parts.append("")
    if not parts:
        parts.append("（聚类未绑到可按时间排列的笔记。）")
        parts.append("")
    return parts


def render_markdown(payload: dict, out_rel: str) -> str:
    a = payload["author"]
    st = payload["stats"]
    display = a["display_name"] or a["uin"]
    title = Path(out_rel).stem
    related = _related_links(payload)

    def yaml_list(items: list[str]) -> str:
        lines = ["related:"]
        seen = set()
        for it in items:
            if it in seen:
                continue
            seen.add(it)
            lines.append(f'  - "{it}"')
        return "\n".join(lines)

    groups = st.get("by_group") or {}
    group_lines = []
    group_names = {"tea": "tea（饮茶室）", "qitan": "qitan（奇谈）", "klein": "klein（晚宴）"}
    for k in ("tea", "qitan", "klein"):
        g = groups.get(k)
        if not g:
            continue
        label = group_names.get(k, k)
        group_lines.append(
            f"- {label}：顶层 {g.get('top', 0)}，保留 {g.get('kept', 0)}，"
            f"{g.get('cjk', 0)} 汉字"
        )

    year_lines = []
    year_note = {
        "2020": "奇谈立骨架，产量最高",
        "2021": "",
        "2022": "",
        "2023": "低产",
        "2024": "语录化、Athl 成文",
        "2025": "莎雕长文、PN、植物人",
        "2026": "回指 2020 原文",
    }
    for year, y in sorted((st.get("by_year") or {}).items()):
        extra = year_note.get(year, "") if _is_fh(payload) else ""
        suffix = f"（{extra}）" if extra else ""
        year_lines.append(f"- {year}：{y['n']} 条，{y['cjk']} 汉字{suffix}")

    names = a.get("names") or []
    name_bits = [display]
    for item in names:
        if isinstance(item, (list, tuple)) and item:
            n = str(item[0])
            if n and n != display and n not in name_bits:
                name_bits.append(n)
    name_clause = " / 偶发 ".join(f"`{n}`" if i else n for i, n in enumerate(name_bits[:3]))

    intro = (
        f"{name_clause}（QQ uin `{a['uin']}`"
        + (f"，uid `{a['uid']}`" if a.get("uid") else "")
        + "）一个人的冰学观编年。"
    )
    if _is_fh(payload):
        intro += (
            "口号与索引见 [[饮茶室QA/核心/FrozenHeart语录]]；"
            "群代际背景见 [[饮茶室QA/核心/JU：冰学演化史]]、[[饮茶室QA/核心/冰学发展简史]]。"
        )
    intro += "长文以库内笔记为准，后发缩写回指最早原文，不在这里另写平行论文。"

    parts = [
        "---",
        f"title: {title}",
        "area: 其他",
        f"source: 按 uin {a['uin']} 从饮茶室 / 奇谈 / 晚宴 JSONL 抽取并聚类",
        f"uin: \"{a['uin']}\"",
        f"uid: {a.get('uid') or ''}",
        f"time_start: {st.get('time_start') or ''}",
        f"time_end: {st.get('time_end') or ''}",
        f"updated: {datetime.now(CST).strftime('%Y-%m-%d')}",
        "tags:",
        "  - type/ref",
        "  - area/frozen",
        yaml_list(related),
        "---",
        "",
        f"# {md_escape_heading(title)}",
        "",
        intro,
        "",
        "## 字数与来源",
        "",
        f"三群 JSONL 按 `sender.uin == {a['uin']}` 抽取。"
        f"顶层 {st.get('author_top', 0)} 条、嵌套转发里同 uin {st.get('author_nested', 0)} 条；"
        f"去掉撤回 / 系统 / 空 / 纯图后保留 {st.get('kept', 0)} 条文本："
        f"{st.get('cjk', 0)} 汉字、{st.get('chars', 0)} 字符、约 {st.get('words', 0)} 词（汉字+英文词）。"
        f"进入聚类的长帖/口号 {st.get('clustered', 0)} 条。",
        "",
        "分群（保留文本）：",
        "",
    ]
    parts.extend(group_lines)
    parts.append("")
    if year_lines:
        parts.append("分年（保留文本）：")
        parts.append("")
        parts.extend(year_lines)
        parts.append("")
        parts.append("以下各段按首次出现排列；后文成文或缩写回指最早原文。聚类汉字只作索引，不是库内笔记篇幅。")
        parts.append("")

    if _is_fh(payload):
        parts.extend(_fh_chronology(payload))
    else:
        parts.extend(_generic_chronology(payload))

    parts.append("## 方法")
    parts.append("")
    parts.append(
        "`_extract/author_theory_arc.py`：过滤短噪音，用 scikit-learn 字 n-gram TF-IDF "
        "把长帖贴到库内笔记（标题、语录小标题、golden_set 针），剩余凝聚聚类。"
        "发展史按首次出现时间写成年月脉络，不以理论名为一级结构；后发缩写标成回指。"
        "字数按保留文本。双桥、第五灵留人性面等成文可能被邻题种子吸走，仍以库内笔记为准，不以簇名为新论。"
    )
    parts.append("")
    return "\n".join(parts).rstrip() + "\n"
