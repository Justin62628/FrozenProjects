#!/usr/bin/env python3
"""Copy slices of 饮茶室QA-原文.md into themed subnotes. Does not rewrite bodies.

Usage:
    python split_qa_notes.py
    python split_qa_notes.py --dry-run

Source of truth after first run: _source/饮茶室QA-原文.md
(created automatically from MOC-饮茶室QA.md if that file is still the dump).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

QA_DIR = Path(__file__).resolve().parent
FROZEN_DIR = QA_DIR.parent
SOURCE_DUMP = QA_DIR / "_source" / "饮茶室QA-原文.md"
HUB_PATH = QA_DIR / "MOC-饮茶室QA.md"
ROOT_MOC = FROZEN_DIR / "MOC-Frozen.md"

# 1-based inclusive line ranges from 饮茶室QA-原文.md (no frontmatter).
# Taxonomy:
#   核心 — 新人稳妥 FAQ、群规、缩写、可单独引用的成册（双桥、简史）
#   冰学独立理论与分析 — 单人成文 / 系统化问答
#   冰学讨论 — 多声部辩论与群聊记录
#   其他 — 资料性短文、代际、占位


@dataclass(frozen=True)
class Slice:
    relpath: str
    start: int
    end: int
    area: str
    gloss: str
    related: tuple[str, ...] = ()


SLICES: tuple[Slice, ...] = (
    # —— 核心 ——
    Slice("核心/饮茶室是干嘛的.md", 23, 44, "核心", "群定位、冰学定义、欢迎与不欢迎的讨论", ("核心/常见缩写.md", "核心/核心FAQ.md")),
    Slice("核心/常见缩写.md", 45, 74, "核心", "人物 / 电影短片 / 官方小说缩写", ("核心/饮茶室是干嘛的.md",)),
    Slice("核心/核心FAQ.md", 75, 195, "核心", "主旨、Ahtohallan、冰二结局、莎雕、娜雕（争议较少的稳妥答）", (
        "核心/双桥理论.md",
        "冰学独立理论与分析/母女线分析.md",
        "冰学讨论/再论莎雕.md",
        "冰学讨论/第五灵考核.md",
    )),
    Slice("核心/双桥理论.md", 415, 436, "核心", "人与自然之桥 + Elsa 人性/魔法之桥", (
        "核心/核心FAQ.md",
        "冰学独立理论与分析/PN在冰学上的价值.md",
        "冰学独立理论与分析/Klein-世界观问题.md",
        "冰学讨论/Elsa该不该永生.md",
    )),
    Slice("核心/冰学发展简史.md", 1048, 0, "核心", "2014 至今编年：贴吧、AK、QQ 群、根叔、UF", ("其他/冰学代际.md",)),
    # —— 独立理论与分析 ——
    Slice("冰学独立理论与分析/SY-Metaphor.md", 311, 364, "冰学独立理论与分析", "FH：Show Yourself 场景的情感/象征逻辑", (
        "核心/核心FAQ.md",
        "冰学独立理论与分析/母女线分析.md",
    )),
    Slice("冰学独立理论与分析/母女线分析.md", 365, 392, "冰学独立理论与分析", "FH：Iduna 线索如何贯穿 F2", ("核心/核心FAQ.md", "冰学独立理论与分析/SY-Metaphor.md")),
    Slice("冰学独立理论与分析/PN在冰学上的价值.md", 393, 414, "冰学独立理论与分析", "Klein：Polar Nights 如何补 F2 离开与 True Love", (
        "核心/双桥理论.md",
        "冰学独立理论与分析/Klein版F2常见问题与解答.md",
    )),
    Slice("冰学独立理论与分析/Klein版F2常见问题与解答.md", 437, 470, "冰学独立理论与分析", "阿塔霍兰、第五灵、离开、自主选择权", (
        "核心/核心FAQ.md",
        "核心/双桥理论.md",
        "冰学独立理论与分析/PN在冰学上的价值.md",
    )),
    Slice("冰学独立理论与分析/Klein-世界观问题.md", 471, 498, "冰学独立理论与分析", "其他国家缺席；第五灵作为「老师」而非保姆", (
        "核心/双桥理论.md",
        "冰学讨论/Elsa该不该永生.md",
        "冰学讨论/冰二的刻画缺失.md",
    )),
    # —— 讨论 ——
    Slice("冰学讨论/再论莎雕.md", 201, 256, "冰学讨论", "莎雕小轮回 / 大轮回；不可接受论与解冻空白", (
        "核心/核心FAQ.md",
        "冰学讨论/第五灵考核.md",
    )),
    Slice("冰学讨论/PN的北地.md", 257, 274, "冰学讨论", "游鱼：求学、尸鬼、四灵上限", ("冰学独立理论与分析/PN在冰学上的价值.md",)),
    Slice("冰学讨论/EAK三人组.md", 275, 310, "冰学讨论", "PN 中豆腐与 Elsa；KA / EA true love 次序", ("核心/核心FAQ.md",)),
    Slice("冰学讨论/编剧对没必要的设定不会去碰.md", 503, 524, "冰学讨论", "世界观专人 vs 水平问题；对照魔圆", ("冰学讨论/冰二的刻画缺失.md",)),
    Slice("冰学讨论/Elsa该不该永生.md", 525, 669, "冰学讨论", "FH 永生论 vs 游鱼反驳及终辩", (
        "核心/双桥理论.md",
        "冰学独立理论与分析/Klein-世界观问题.md",
        "冰学讨论/F2结尾第五灵的必要性.md",
    )),
    Slice("冰学讨论/F2结尾第五灵的必要性.md", 670, 759, "冰学讨论", "第五灵是否必须；gift / 考核 / 永生余波", (
        "冰学讨论/Elsa该不该永生.md",
        "冰学讨论/第五灵考核.md",
        "冰学讨论/冰二的刻画缺失.md",
    )),
    Slice("冰学讨论/冰二的刻画缺失.md", 760, 839, "冰学讨论", "土豆：ITU 前探索欲望铺垫被吞掉", (
        "核心/核心FAQ.md",
        "冰学讨论/F2结尾第五灵的必要性.md",
    )),
    Slice("冰学讨论/冰一野史创作.md", 840, 855, "冰学讨论", "JU：野史必须重写 FTFTIF reprise", ("核心/核心FAQ.md",)),
    Slice("冰学讨论/第五灵考核.md", 866, 923, "冰学讨论", "把冰二当考核是否成立；引导 vs 考核", (
        "核心/核心FAQ.md",
        "冰学讨论/再论莎雕.md",
        "冰学讨论/Ahtohallan主体性.md",
    )),
    Slice("冰学讨论/Ahtohallan主体性.md", 924, 987, "冰学讨论", "Ahtohallan 是否被观众造神；后现代附记", (
        "核心/核心FAQ.md",
        "冰学讨论/第五灵考核.md",
        "其他/几内亚-历览前贤国与家.md",
    )),
    # —— 其他 ——
    Slice("其他/几内亚-历览前贤国与家.md", 992, 1021, "其他", "把 True Love 当超道德实体；新旧约对照", (
        "核心/双桥理论.md",
        "冰学讨论/Ahtohallan主体性.md",
    )),
    Slice("其他/冰学代际.md", 1022, 1033, "其他", "JU：2021–2025 冰学班子代际", ("核心/冰学发展简史.md",)),
    Slice("其他/活Elsa.md", 1034, 1047, "其他", "浅斟低唱：以亲历者直觉解读 Elsa", ("核心/核心FAQ.md",)),
    Slice("其他/冰学世界观分析.md", 856, 859, "其他", "原文占位 TODO，尚未成文", ()),
)

AREA_ORDER = ("核心", "冰学独立理论与分析", "冰学讨论", "其他")

DUMP_MARKERS = ("# **核心FAQ**", "# **冰学发展简史**")


def read_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return text.splitlines(True)


def dump_body_lines(path: Path) -> list[str]:
    """Skip YAML frontmatter if present so line numbers match the original dump."""
    lines = read_lines(path)
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                rest = lines[i + 1 :]
                if rest and rest[0] == "\n":
                    rest = rest[1:]
                return rest
    return lines


def ensure_source_dump() -> list[str]:
    SOURCE_DUMP.parent.mkdir(parents=True, exist_ok=True)
    if SOURCE_DUMP.exists():
        return dump_body_lines(SOURCE_DUMP)

    if not HUB_PATH.exists():
        raise SystemExit(f"Missing source: neither {SOURCE_DUMP} nor {HUB_PATH}")

    raw = HUB_PATH.read_text(encoding="utf-8")
    if not all(m in raw for m in DUMP_MARKERS):
        raise SystemExit(
            f"{HUB_PATH.name} is not the original dump and {SOURCE_DUMP.name} is missing."
        )

    body = raw
    rewritten = rewrite_asset_links(body, SOURCE_DUMP)
    header = (
        "---\n"
        "status: source-dump\n"
        "rag: skip\n"
        "---\n\n"
    )
    SOURCE_DUMP.write_text(header + rewritten, encoding="utf-8", newline="\n")
    print(f"Saved original dump -> {SOURCE_DUMP.relative_to(FROZEN_DIR)}")
    return dump_body_lines(SOURCE_DUMP)


def rewrite_asset_links(text: str, dest: Path) -> str:
    rel_assets = Path(os_relpath(QA_DIR / "assets", dest.parent)).as_posix()
    text = re.sub(r"\]\(assets/", f"]({rel_assets}/", text)
    text = re.sub(r"\]\(\.\./assets/", f"]({rel_assets}/", text)
    return text


def os_relpath(target: Path, start: Path) -> str:
    import os

    return os.path.relpath(target, start)


def wiki(relpath: str) -> str:
    note = relpath[:-3] if relpath.endswith(".md") else relpath
    return f"[[饮茶室QA/{note}]]"


def slice_text(lines: list[str], start: int, end: int) -> str:
    last = len(lines) if end <= 0 else end
    if start < 1 or start > len(lines) or last < start:
        raise ValueError(f"Bad range {start}-{end} for {len(lines)} lines")
    chunk = "".join(lines[start - 1 : last])
    return chunk if chunk.endswith("\n") else chunk + "\n"


def frontmatter(sl: Slice) -> str:
    end = "EOF" if sl.end <= 0 else str(sl.end)
    if sl.related:
        related_block = "related:\n" + "\n".join(f'  - "{wiki(r)}"' for r in sl.related)
    else:
        related_block = "related: []"
    return (
        "---\n"
        f"title: {Path(sl.relpath).stem}\n"
        f"area: {sl.area}\n"
        'source: "[[饮茶室QA/_source/饮茶室QA-原文]]"\n'
        f'source_lines: "{sl.start}-{end}"\n'
        "tags:\n"
        "  - type/ref\n"
        "  - area/frozen\n"
        f"{related_block}\n"
        "---\n\n"
    )


HEADING_RE = re.compile(r"^(#{1,6})([ \t]*)(.*)$")
LONG_HEADING = 45


def split_frontmatter(text: str) -> tuple[str, str]:
    lines = text.splitlines(True)
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[: i + 1]), "".join(lines[i + 1 :])
    return "", text


def clean_heading_text(title: str) -> str:
    title = title.replace("**", "")
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"^Q:\s*", "Q：", title)
    return title.rstrip("：:").strip()


def normalize_headings(text: str, stem: str, *, is_moc: bool = False) -> str:
    """Clean heading markers only; do not rewrite body paragraphs."""
    fm, body = split_frontmatter(text)
    body = body.lstrip("\n")
    out: list[str] = []
    headings: list[tuple[int, int, str]] = []

    for line in body.splitlines(True):
        raw = line.rstrip("\n")
        m = HEADING_RE.match(raw)
        if not m:
            out.append(line if line.endswith("\n") else line + "\n")
            continue
        title = clean_heading_text(m.group(3))
        if not title:
            continue
        level = len(m.group(1))
        headings.append((len(out), level, title))
        out.append(f"{'#' * level} {title}\n")

    if not is_moc:
        h1s = [(i, t) for i, lv, t in headings if lv == 1]
        h2s = [(i, t) for i, lv, t in headings if lv == 2]
        if not h1s and len(h2s) == 1:
            i, t = h2s[0]
            out[i] = f"# {stem}\n\n{t}\n" if len(t) > LONG_HEADING else f"# {t}\n"
        elif not h1s:
            out.insert(0, f"# {stem}\n\n")
        elif h1s and len(h1s[0][1]) > LONG_HEADING:
            i, t = h1s[0]
            out[i] = f"# {stem}\n\n{t}\n"
        _fix_skipped_heading_level(out)

    body = "".join(out)
    if fm and not fm.endswith("\n"):
        fm += "\n"
    result = f"{fm}\n{body}" if fm else body
    return result if result.endswith("\n") else result + "\n"


def write_slice(lines: list[str], sl: Slice, dry_run: bool) -> Path:
    dest = QA_DIR / sl.relpath
    body = rewrite_asset_links(slice_text(lines, sl.start, sl.end), dest)
    text = normalize_headings(frontmatter(sl) + body, Path(sl.relpath).stem)
    if dry_run:
        print(f"DRY  {sl.relpath}  ({sl.start}-{sl.end or 'EOF'}, {len(body)} chars)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    print(f"WRITE {sl.relpath}  ({sl.start}-{sl.end or 'EOF'})")
    return dest


def normalize_existing_notes(*, dry_run: bool = False) -> int:
    count = 0
    for path in sorted(FROZEN_DIR.rglob("*.md")):
        if "_source" in path.parts:
            continue
        original = path.read_text(encoding="utf-8")
        updated = normalize_headings(
            original,
            path.stem,
            is_moc=path.name.startswith("MOC-"),
        )
        if updated == original:
            continue
        count += 1
        rel = path.relative_to(FROZEN_DIR)
        if dry_run:
            print(f"DRY  {rel}")
            continue
        path.write_text(updated, encoding="utf-8", newline="\n")
        print(f"NORM {rel}")
    return count


def _fix_skipped_heading_level(out: list[str]) -> None:
    """If a note has H1 and H3 but no H2, promote H3+ one level."""
    parsed: list[tuple[int, int, str]] = []
    for i, line in enumerate(out):
        m = HEADING_RE.match(line.rstrip("\n"))
        if m:
            parsed.append((i, len(m.group(1)), clean_heading_text(m.group(3))))
    levels = {lv for _, lv, _ in parsed}
    if 1 not in levels or 2 in levels or not any(lv >= 3 for lv in levels):
        return
    for i, lv, title in parsed:
        if lv >= 3:
            out[i] = f"{'#' * (lv - 1)} {title}\n"


def uncovered(lines: list[str], slices: tuple[Slice, ...]) -> list[tuple[int, int, str]]:
    n = len(lines)
    covered = [False] * (n + 1)
    for sl in slices:
        last = n if sl.end <= 0 else sl.end
        for i in range(sl.start, last + 1):
            if 1 <= i <= n:
                covered[i] = True
    gaps: list[tuple[int, int, str]] = []
    i = 1
    while i <= n:
        if covered[i]:
            i += 1
            continue
        j = i
        while j <= n and not covered[j]:
            j += 1
        preview = "".join(lines[i - 1 : min(j, i + 2)]).strip().replace("\n", " / ")
        gaps.append((i, j - 1, preview[:80]))
        i = j
    return gaps


def hub_markdown() -> str:
    by_area: dict[str, list[Slice]] = {a: [] for a in AREA_ORDER}
    for sl in SLICES:
        by_area[sl.area].append(sl)

    parts = [
        "---",
        "tags:",
        "  - type/ref",
        "  - area/frozen",
        "status: active",
        "updated: 2026-08-22",
        "---",
        "",
        "# 饮茶室QA",
        "",
        "本文档有两大核心部分",
        "",
        "​                ● 核心FAQ，给新人看的，提供对常见问题保险、稳妥、本群争议较少的答案",
        "",
        "​                ● 围绕FAQ的补充说明文档，包含对同一问题的其他视角解读、一些深入的讨论",
        "",
        "​                ○ 分成文本、创作、世界观、观众、其它五个部分。",
        "",
        "​                ○ 文本部分包含针对电影、小说的多视角分析和解释，例如莎雕问题；",
        "",
        "​                ○ 创作部分包含对冰二F2创作过程的分析，例如“为什么冰二没这么写，Elsa该不该永生”，以及群侑对F3的展望；",
        "",
        "​                ○ 世界观部分包含对冰雪系列总体世界观、设定细节的分析和讨论",
        "",
        "​                ○ 观众部分包含对搞冰学的人脑袋里在想什么的研究和讨论，即冰学观众理论",
        "",
        "​                ● 编辑原则：上述六个部分互有指涉，添加内容前需要先确定内容侧重点",
        "",
        "正文已按主题**复制**到子笔记（未改写）。检索请走子笔记；完整原文见 [[饮茶室QA/_source/饮茶室QA-原文]]（`rag: skip`）。",
        "",
        "## 核心（独立成册）",
        "",
        "新人入口与可单独引用的成册。",
        "",
    ]
    for sl in by_area["核心"]:
        parts.append(f"- {wiki(sl.relpath)} — {sl.gloss}")
    parts += ["", "## 冰学独立理论与分析", ""]
    for sl in by_area["冰学独立理论与分析"]:
        parts.append(f"- {wiki(sl.relpath)} — {sl.gloss}")
    parts += ["", "## 冰学讨论", ""]
    for sl in by_area["冰学讨论"]:
        parts.append(f"- {wiki(sl.relpath)} — {sl.gloss}")
    parts += ["", "## 其他", ""]
    for sl in by_area["其他"]:
        parts.append(f"- {wiki(sl.relpath)} — {sl.gloss}")
    parts += [
        "",
        "## 版本",
        "",
        "- 2026-08-22：从原文按主题复制拆分为子笔记",
        "- 2026-08-22：Prettier 标准化 Markdown（`--prose-wrap preserve`，不重排正文）",
        "- 2026-08-22：清洗标题结构（去掉标题内 **、空标题；独立笔记补一级标题）",
        "",
        "## 工具",
        "",
        "- `extract_data_images.py` — 把 `data:image` 抽到 `assets/`",
        "- `split_qa_notes.py` — 按行号从原文复制到本索引所列子笔记",
        "",
        "---",
        "",
        "[[MOC-Frozen]]",
        "",
    ]
    return "\n".join(parts)


def root_moc_markdown() -> str:
    return "\n".join(
        [
            "---",
            "tags:",
            "  - type/ref",
            "  - area/frozen",
            "status: active",
            "updated: 2026-08-22",
            "---",
            "",
            "# Frozen / 饮茶室 RAG",
            "",
            "独立检索库入口。目前只有饮茶室QA 一批材料，按主题拆在子文件夹里，方便 Agent 引用常见问题与历史讨论。",
            "",
            "## 库",
            "",
            "- [[饮茶室QA/MOC-饮茶室QA]] — 核心 FAQ、独立理论、讨论、其他",
            "",
            "检索时优先子笔记，不要用 `_source/饮茶室QA-原文`（完整dump，标记 `rag: skip`）。",
            "",
            "## 版本",
            "",
            "- 2026-08-22：建立 RAG 入口；饮茶室QA 按主题拆分；Prettier 标准化 Markdown",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--normalize-headings",
        action="store_true",
        help="Clean ** / empty headings on existing notes; do not recopy from _source",
    )
    args = parser.parse_args()

    if args.normalize_headings:
        n = normalize_existing_notes(dry_run=args.dry_run)
        print(f"{'Would update' if args.dry_run else 'Updated'} {n} file(s)")
        return 0

    lines = ensure_source_dump()
    print(f"Source lines: {len(lines)}")

    seen_ranges: list[tuple[int, int, str]] = []
    for sl in SLICES:
        last = len(lines) if sl.end <= 0 else sl.end
        for a, b, name in seen_ranges:
            if not (last < a or sl.start > b):
                print(f"WARNING overlap: {sl.relpath} vs {name}", file=sys.stderr)
        seen_ranges.append((sl.start, last, sl.relpath))
        write_slice(lines, sl, args.dry_run)

    gaps = uncovered(lines, SLICES)
    print("--- uncovered (expected: intro + section H1 wrappers) ---")
    for a, b, preview in gaps:
        print(f"  {a}-{b}: {preview}")

    if args.dry_run:
        print(f"DRY hub -> {HUB_PATH.name}")
        print(f"DRY root -> {ROOT_MOC.name}")
        return 0

    HUB_PATH.write_text(hub_markdown(), encoding="utf-8", newline="\n")
    ROOT_MOC.write_text(root_moc_markdown(), encoding="utf-8", newline="\n")
    print(f"WRITE {HUB_PATH.relative_to(FROZEN_DIR)}")
    print(f"WRITE {ROOT_MOC.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
