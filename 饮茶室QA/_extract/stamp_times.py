#!/usr/bin/env python3
"""Locate original QQ send times for note quotes and stamp them.

Usage:
    python stamp_times.py PATH [PATH ...]
    python stamp_times.py 饮茶室QA/核心 --dry-run
    python stamp_times.py 饮茶室QA/冰学讨论 -o report.json

PATH is a .md file or a folder (recursive *.md). 默认在原文里就地盖时间；
--dry-run 只出报告。跳过已有 `> *YYYY-MM-DD HH:mm:ss` 的块。
歧义命中不猜，列入 unmatched。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonl_io import add_group_args, iter_jsonl_lines, load_group_specs

HERE = Path(__file__).resolve().parent

CST = timezone(timedelta(hours=8))
IMG_RE = re.compile(r"\[图片(?::[^\]]*)?\]")
STAMPED_RE = re.compile(
    r"^>+\s*\*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+.+\*"
)
ISO_HEAD_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)"
    r"\s*·\s*(.+?)\s*·\s*chat\s*$"
)
SPEAKER_RE = re.compile(
    r"^(?:>+\s*)?(?:\*)?([^：:\n*]{1,40})[：:](.+)$"
)
# FAQ / 提纲里的 Q： A： 不是发言人
SKIP_SPEAKERS = {"Q", "A", "q", "a"}
SKIP_PREFIX = (
    "http://",
    "https://",
    "[[",
    "![",
    "#",
    "-",
    "* ",
    "主张：",
    "讨论：",
    "全文见",
    "出处时间",
)
MIN_NEEDLE = 20
PREFILTER_LEN = 48


def msg_text(raw: dict) -> str:
    return ((raw.get("content") or {}).get("text") or "").strip()


def sender_name(raw: dict) -> str:
    s = raw.get("sender") or {}
    return s.get("name") or s.get("groupCard") or s.get("nickname") or ""


def fmt_time(raw: dict) -> str:
    t = raw.get("time") or ""
    if t:
        try:
            dt = datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(CST)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    ts = int(raw.get("timestamp") or 0)
    if ts:
        if ts > 10_000_000_000:
            ts //= 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(CST)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return ""


def iso_z_to_cst(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(CST)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def strip_images(text: str) -> str:
    text = IMG_RE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_body(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("[回复消息]"):
        text = text[len("[回复消息]") :].lstrip()
    return strip_images(text)


def iter_md_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        p = p.expanduser().resolve()
        if p.is_file() and p.suffix.lower() == ".md":
            out.append(p)
        elif p.is_dir():
            out.extend(sorted(q for q in p.rglob("*.md") if q.is_file()))
    skip = {"_source", "_extract", "assets"}
    cleaned = []
    for p in out:
        parts = {x.lower() for x in p.parts}
        if parts & skip:
            continue
        if p.name.startswith("MOC-"):
            continue
        cleaned.append(p)
    return cleaned


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    return text[: end + 4], text[end + 4 :]


def already_stamped_line(line: str) -> bool:
    return bool(STAMPED_RE.match(line.strip()))


def is_skip_text(s: str) -> bool:
    t = s.strip()
    if len(t) < MIN_NEEDLE:
        return True
    if t.startswith("[图片"):
        return True
    if t.startswith(SKIP_PREFIX):
        return True
    if re.fullmatch(r"[-=—]{3,}", t):
        return True
    return False


def extract_needles(body: str) -> list[dict]:
    """Collect candidate quote strings with their line index in body_lines."""
    lines = body.split("\n")
    needles: list[dict] = []
    seen: set[str] = set()

    def add(text: str, line_idx: int, kind: str, speaker: str = "") -> None:
        text = normalize_body(text)
        if is_skip_text(text) or text in seen:
            return
        seen.add(text)
        needles.append(
            {
                "text": text,
                "line": line_idx,
                "kind": kind,
                "speaker": speaker,
            }
        )

    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        s = raw.strip()
        if already_stamped_line(s):
            i += 1
            continue
        m_iso = ISO_HEAD_RE.match(s)
        if m_iso:
            i += 1
            continue

        if s.startswith(">"):
            inner = re.sub(r"^>+\s*", "", s)
            inner = inner.strip()
            if inner.startswith("*") and inner.endswith("*") and len(inner) < 80:
                i += 1
                continue
            if inner.startswith("*↪") or inner.startswith("↪"):
                i += 1
                continue
            if inner.startswith("*[转发]") or inner.startswith("[转发]"):
                i += 1
                continue
            sm = SPEAKER_RE.match(inner)
            if sm and sm.group(1).strip() not in SKIP_SPEAKERS and len(sm.group(2).strip()) >= MIN_NEEDLE:
                add(sm.group(2).strip(), i, "quote_speaker", sm.group(1).strip())
            elif not is_skip_text(inner):
                add(inner, i, "blockquote")
            i += 1
            continue

        sm = SPEAKER_RE.match(s)
        if sm:
            who, rest = sm.group(1).strip(), sm.group(2).strip()
            if who in SKIP_SPEAKERS:
                i += 1
                continue
            if rest:
                add(rest, i, "speaker", who)
                i += 1
                continue

        if not s:
            i += 1
            continue

        # paragraph: gather until blank, if it looks like chat/quote
        if not s.startswith("#") and not s.startswith("- ") and not s.startswith("* "):
            chunk = [s]
            j = i + 1
            while j < n and lines[j].strip() and not lines[j].strip().startswith("#"):
                nxt = lines[j].strip()
                if nxt.startswith(">") or already_stamped_line(nxt):
                    break
                if SPEAKER_RE.match(nxt):
                    break
                chunk.append(nxt)
                j += 1
            para = "\n".join(chunk)
            if len(para) >= MIN_NEEDLE:
                add(para, i, "paragraph")
            i = j
            continue
        i += 1
    return needles


def prefilter_key(text: str) -> str:
    t = text.replace("\n", "")
    if len(t) <= PREFILTER_LEN:
        return t
    return t[:PREFILTER_LEN]


class JsonlIndex:
    def __init__(self, sources: list[Path]) -> None:
        self.sources: list[Path] = []
        for src in sources:
            src = src.expanduser()
            if src.exists():
                self.sources.append(src)
            else:
                print(f"警告：JSONL 源不存在 {src}", file=sys.stderr)

    def search(self, needles: list[str]) -> dict[str, list[dict]]:
        """Return needle -> list of {time, sender, exact, text}."""
        if not needles:
            return {}
        keys = [(n, prefilter_key(n)) for n in needles]
        raw_needles = {k for _, k in keys if k}
        hits: dict[str, list[dict]] = defaultdict(list)
        if not raw_needles:
            return hits

        for src in self.sources:
            for line in iter_jsonl_lines(src):
                if not any(k in line for k in raw_needles):
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if raw.get("recalled"):
                    continue
                body = normalize_body(msg_text(raw))
                if not body:
                    continue
                when = fmt_time(raw)
                who = sender_name(raw)
                if not when:
                    continue
                rec = {
                    "time": when,
                    "sender": who,
                    "text": body,
                }
                for needle, key in keys:
                    if key not in line and key not in body:
                        continue
                    exact = body == needle
                    contains = (not exact) and (needle in body or body in needle)
                    if exact or contains:
                        hits[needle].append({**rec, "exact": exact})
        for needle, rows in hits.items():
            uniq = []
            seen = set()
            for r in rows:
                k = (r["time"], r["sender"], r["text"])
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(r)
            hits[needle] = uniq
        return hits


def stamp_header(when: str, who: str) -> str:
    who = who or "未知"
    return f"> *{when}  {who}*"


def apply_iso_headers(body: str) -> tuple[str, int]:
    lines = body.split("\n")
    n = 0
    out = []
    for line in lines:
        m = ISO_HEAD_RE.match(line.strip())
        if m:
            when = iso_z_to_cst(m.group(1))
            who = m.group(2).strip()
            out.append(stamp_header(when, who))
            n += 1
        else:
            out.append(line)
    return "\n".join(out), n


def upsert_yaml_times(fm: str, start: str, end: str) -> str:
    if not fm:
        return fm
    inner = fm[3:]
    if inner.startswith("\n"):
        inner = inner[1:]
    if inner.endswith("---"):
        inner = inner[:-3]
    if inner.endswith("\n"):
        inner = inner[:-1]
    lines = inner.split("\n")
    have = {ln.split(":", 1)[0] for ln in lines if ":" in ln}
    extra: list[str] = []
    if "updated" not in have:
        extra.append("updated: 2026-08-22")
    if "time_start" not in have:
        extra.append(f"time_start: {start}")
    if "time_end" not in have:
        extra.append(f"time_end: {end}")
    if not extra:
        return fm
    insert_at = len(lines)
    for i, ln in enumerate(lines):
        if ln.startswith("tags:"):
            insert_at = i
            break
    new_inner = "\n".join(lines[:insert_at] + extra + lines[insert_at:])
    return f"---\n{new_inner}\n---"


def apply_stamps(
    body: str,
    needles: list[dict],
    hitmap: dict[str, list[dict]],
) -> tuple[str, list[dict], list[dict], list[str]]:
    """Return new_body, stamped, unmatched, yaml_times."""
    lines = body.split("\n")
    stamped: list[dict] = []
    unmatched: list[dict] = []
    times: list[str] = []
    insert_at: dict[int, str] = {}  # line idx -> header to insert above
    replace_line: dict[int, str] = {}

    for nd in needles:
        hits = hitmap.get(nd["text"]) or []
        exact = [h for h in hits if h.get("exact")]
        use = exact if exact else hits
        if not use:
            unmatched.append({**nd, "reason": "no_match"})
            continue
        # unique by time+sender
        uniq_keys = {(h["time"], h["sender"]) for h in use}
        if len(uniq_keys) != 1:
            unmatched.append(
                {
                    **nd,
                    "reason": "ambiguous",
                    "n": len(uniq_keys),
                    "times": sorted(t for t, _ in uniq_keys)[:6],
                }
            )
            continue
        h = use[0]
        times.append(h["time"])
        header = stamp_header(h["time"], h["sender"])
        idx = nd["line"]
        prev = lines[idx - 1].strip() if idx > 0 else ""
        if already_stamped_line(prev) or already_stamped_line(lines[idx]):
            stamped.append({**nd, "time": h["time"], "sender": h["sender"], "action": "already"})
            continue
        if nd["kind"] == "paragraph":
            # 散文理论：只收时间进 YAML / 出处时间，不在段前插发送头
            stamped.append({**nd, "time": h["time"], "sender": h["sender"], "action": "yaml"})
            continue
        if nd["kind"] in ("speaker", "quote_speaker"):
            raw = lines[idx]
            rest = nd["text"]
            if raw.strip().startswith(">"):
                depth = len(raw) - len(raw.lstrip(">"))
                replace_line[idx] = f"{'>' * depth} {header}\n{'>' * depth} {rest}"
            else:
                replace_line[idx] = f"{header}\n{rest}"
            stamped.append({**nd, "time": h["time"], "sender": h["sender"], "action": "speaker"})
        else:
            insert_at[idx] = header
            stamped.append({**nd, "time": h["time"], "sender": h["sender"], "action": "insert"})

    new_lines: list[str] = []
    for i, line in enumerate(lines):
        if i in replace_line:
            new_lines.append(replace_line[i])
            continue
        if i in insert_at:
            # don't double-insert
            if not (new_lines and already_stamped_line(new_lines[-1])):
                new_lines.append(insert_at[i])
        new_lines.append(line)
    return "\n".join(new_lines), stamped, unmatched, times


def process_file(
    path: Path,
    index: JsonlIndex,
    dry_run: bool,
) -> dict:
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    body, iso_n = apply_iso_headers(body)
    needles = extract_needles(body)
    hitmap = index.search([n["text"] for n in needles])
    new_body, stamped, unmatched, times = apply_stamps(body, needles, hitmap)
    if iso_n and not dry_run:
        # iso conversion already in new_body via apply_iso on original body;
        # apply_stamps started from converted body
        pass
    if times:
        start, end = min(times), max(times)
        if fm:
            fm = upsert_yaml_times(fm, start, end)
        else:
            # leave body-only; agent may add YAML later
            pass
        # 出处时间 for prose notes without chat headers dominating
        chat_stamped = sum(1 for s in stamped if s.get("action") in ("speaker", "insert"))
        if chat_stamped == 0 and "出处时间" not in new_body:
            # insert after first H1
            lines = new_body.split("\n")
            for i, ln in enumerate(lines):
                if ln.startswith("# "):
                    stamp_line = f"出处时间：{start}" if start == end else f"出处时间：{start} → {end}"
                    lines.insert(i + 1, "")
                    lines.insert(i + 2, stamp_line)
                    new_body = "\n".join(lines)
                    break

    new_text = (fm + new_body) if fm else new_body
    if new_text and not new_text.endswith("\n"):
        new_text += "\n"
    changed = new_text != text
    if changed and not dry_run:
        path.write_text(new_text, encoding="utf-8")

    return {
        "path": str(path),
        "iso_converted": iso_n,
        "needles": len(needles),
        "stamped": len([s for s in stamped if s.get("action") != "already"]),
        "already": len([s for s in stamped if s.get("action") == "already"]),
        "unmatched": [
            {
                "text": u["text"][:160],
                "reason": u.get("reason"),
                "n": u.get("n"),
                "times": u.get("times"),
                "kind": u.get("kind"),
            }
            for u in unmatched
        ],
        "stamped_detail": [
            {
                "time": s.get("time"),
                "sender": s.get("sender"),
                "action": s.get("action"),
                "preview": s["text"][:80],
            }
            for s in stamped
            if s.get("action") != "already"
        ],
        "changed": changed,
        "times": sorted(set(times)),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="给笔记引用盖上 QQ 原发送时间")
    p.add_argument("paths", nargs="+", type=Path, help=".md 或文件夹")
    p.add_argument("--dry-run", action="store_true", help="不写回，只出报告")
    p.add_argument("-o", "--out", type=Path, help="把报告写成 JSON")
    add_group_args(p)
    p.add_argument(
        "--tea",
        type=Path,
        default=None,
        help="额外饮茶室导出（目录或 zip；兼容旧开关）",
    )
    p.add_argument(
        "--klein",
        type=Path,
        default=None,
        help="额外晚宴导出（目录或 zip；兼容旧开关）",
    )
    args = p.parse_args(argv)

    files = iter_md_paths(args.paths)
    if not files:
        raise SystemExit("没有可处理的 .md")

    specs = load_group_specs(args.config, extra_paths=args.group)
    roots = [spec["root"] for spec in specs]
    if args.tea:
        roots.append(args.tea)
    if args.klein:
        roots.append(args.klein)
    index = JsonlIndex(roots)
    prepared: list[tuple[Path, str, str, list[dict]]] = []
    all_needles: list[str] = []
    for fp in files:
        text = fp.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        body, iso_n = apply_iso_headers(body)
        needles = extract_needles(body)
        prepared.append((fp, text, fm, body, iso_n, needles))
        all_needles.extend(n["text"] for n in needles)
    print(f"扫描 JSONL：{len(files)} 篇，{len(all_needles)} 条候选…", file=sys.stderr)
    hitmap = index.search(all_needles)

    reports = []
    total_stamped = 0
    total_unmatched = 0
    total_iso = 0
    for fp, orig, fm, body, iso_n, needles in prepared:
        new_body, stamped, unmatched, times = apply_stamps(body, needles, hitmap)
        if times:
            start, end = min(times), max(times)
            if fm:
                fm = upsert_yaml_times(fm, start, end)
            chat_stamped = sum(
                1 for s in stamped if s.get("action") in ("speaker", "insert")
            )
            if chat_stamped == 0 and "出处时间" not in new_body:
                lines = new_body.split("\n")
                for i, ln in enumerate(lines):
                    if ln.startswith("# "):
                        stamp_line = (
                            f"出处时间：{start}"
                            if start == end
                            else f"出处时间：{start} → {end}"
                        )
                        lines.insert(i + 1, "")
                        lines.insert(i + 2, stamp_line)
                        new_body = "\n".join(lines)
                        break
        new_text = (fm + new_body) if fm else new_body
        if new_text and not new_text.endswith("\n"):
            new_text += "\n"
        changed = new_text != orig
        if changed and not args.dry_run:
            fp.write_text(new_text, encoding="utf-8")
        rep = {
            "path": str(fp),
            "iso_converted": iso_n,
            "needles": len(needles),
            "stamped": len([s for s in stamped if s.get("action") != "already"]),
            "already": len([s for s in stamped if s.get("action") == "already"]),
            "unmatched": [
                {
                    "text": u["text"][:160],
                    "reason": u.get("reason"),
                    "n": u.get("n"),
                    "times": u.get("times"),
                    "kind": u.get("kind"),
                }
                for u in unmatched
            ],
            "stamped_detail": [
                {
                    "time": s.get("time"),
                    "sender": s.get("sender"),
                    "action": s.get("action"),
                    "preview": s["text"][:80],
                }
                for s in stamped
                if s.get("action") != "already"
            ],
            "changed": changed,
            "times": sorted(set(times)),
        }
        reports.append(rep)
        total_stamped += rep["stamped"]
        total_unmatched += len(rep["unmatched"])
        total_iso += iso_n
        print(
            f"{fp.name}\tneedles={rep['needles']}\tstamped={rep['stamped']}"
            f"\talready={rep['already']}\tunmatched={len(rep['unmatched'])}"
            f"\tiso={iso_n}\tchanged={changed}",
            file=sys.stderr,
        )
        for u in rep["unmatched"]:
            if u["reason"] == "ambiguous" or len(u["text"]) >= 40:
                print(
                    f"  unmatched[{u['reason']}] {u['text']!r}",
                    file=sys.stderr,
                )

    summary = {
        "files": len(files),
        "stamped": total_stamped,
        "unmatched": total_unmatched,
        "iso_converted": total_iso,
        "dry_run": args.dry_run,
        "reports": reports,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"已写报告 {args.out}", file=sys.stderr)
    print(
        f"{total_stamped} stamped  {total_unmatched} unmatched  "
        f"{total_iso} iso-headers  {len(files)} files"
        + ("  (dry-run)" if args.dry_run else ""),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
