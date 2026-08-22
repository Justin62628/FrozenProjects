#!/usr/bin/env python3
"""Dump full (untruncated) JSONL messages for a list of candidate IDs."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonl_io import iter_raw, load_group_specs

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CST = timezone(timedelta(hours=8))
IMG_RE = __import__("re").compile(r"\[图片(?::[^\]]*)?\]")


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


def fmt_time_raw(raw: dict) -> str:
    t = raw.get("time") or ""
    if t:
        return iso_to_cst(t)
    ts = int(raw.get("timestamp") or 0)
    if ts:
        if ts > 10_000_000_000:
            ts //= 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(CST)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return ""


def sender_name(raw: dict) -> str:
    s = raw.get("sender") or {}
    return s.get("name") or s.get("groupCard") or s.get("nickname") or ""


def msg_text(raw: dict) -> str:
    return ((raw.get("content") or {}).get("text") or "").strip()


def body_text(raw: dict) -> str:
    text = msg_text(raw)
    if text.startswith("[回复消息]"):
        text = text[len("[回复消息]") :].lstrip()
    text = IMG_RE.sub("", text)
    text = __import__("re").sub(r"[ \t]+\n", "\n", text)
    text = __import__("re").sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def md_italic(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace("*", r"\*")
    return "*" + escaped + "*"


def quote_lines(text: str) -> list[str]:
    out = []
    for part in text.split("\n"):
        if part.strip():
            out.append("> " + md_italic(part) if False else "> " + part)
        else:
            out.append(">")
    return out


def format_one(raw: dict) -> str:
    if raw.get("recalled") or raw.get("system"):
        return ""
    name = sender_name(raw)
    who = f"{fmt_time_raw(raw)}  {name}".rstrip()
    body = body_text(raw)
    if not body:
        return ""
    reply = ""
    for el in (raw.get("content") or {}).get("elements") or []:
        if el.get("type") != "reply":
            continue
        d = el.get("data") or {}
        nm = (d.get("senderName") or "").strip()
        prev = (d.get("content") or "").replace("\r\n", "\n")
        prev = IMG_RE.sub("", prev).strip()
        if nm and prev:
            reply = f"↪ {nm}：{prev[:200]}"
        elif prev:
            reply = f"↪ {prev[:200]}"
        break
    lines = [f"> *{who}*"]
    if reply:
        lines.append(f"> *{reply}*")
    for ln in body.split("\n"):
        if ln.strip():
            lines.append("> " + ln.rstrip())
        else:
            lines.append(">")
    return "\n".join(lines)


def main() -> None:
    ids = [x.strip() for x in sys.argv[1:] if x.strip()]
    if not ids:
        raise SystemExit("usage: _gapfill_dump.py ID [ID ...]")
    cands_obj = json.loads((DATA / "candidates.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cands_obj["candidates"]}
    wanted: dict[str, set[str]] = {}
    meta = {}
    for cid in ids:
        c = by_id.get(cid)
        if not c and cid.count(":") == 1:
            g, mid = cid.split(":", 1)
            wanted.setdefault(g, set()).add(mid)
            meta[cid] = {
                "id": cid,
                "group": g,
                "author_name": "",
                "time_start": "",
                "time_end": "",
                "preview": "",
                "messages": [{"role": "chat", "id": mid}],
            }
            continue
        if not c:
            print("missing candidate", cid, file=sys.stderr)
            continue
        g = c["group"]
        msg_ids = set()
        for m in c.get("messages") or []:
            if m.get("role") in ("ctx", "forwarded"):
                continue
            if m.get("id"):
                msg_ids.add(str(m["id"]))
        seed = cid.split(":")[-1]
        msg_ids.add(seed)
        wanted.setdefault(g, set()).update(msg_ids)
        meta[cid] = c

    specs = {s["key"]: s for s in load_group_specs()}
    found: dict[str, dict] = {}
    for g, ids_need in wanted.items():
        spec = specs[g]
        left = set(ids_need)
        for raw in iter_raw(spec["root"]):
            rid = str(raw.get("id") or "")
            if rid in left:
                found[rid] = raw
                left.remove(rid)
                if not left:
                    break
        if left:
            print(f"{g} missing {len(left)} ids", file=sys.stderr)

    out_dir = DATA / "_gapfill_dump"
    out_dir.mkdir(exist_ok=True)
    index = []
    for cid, c in meta.items():
        blocks = []
        times = []
        authors = []
        full_n = 0
        for m in c.get("messages") or []:
            if m.get("role") in ("ctx", "forwarded"):
                continue
            rid = str(m.get("id") or "")
            raw = found.get(rid)
            if not raw:
                continue
            block = format_one(raw)
            if not block:
                continue
            blocks.append(block)
            t = fmt_time_raw(raw)
            if t:
                times.append(t)
            authors.append(sender_name(raw))
            full_n += len(body_text(raw))
        text = "\n\n".join(blocks) + ("\n" if blocks else "")
        fp = out_dir / (cid.replace(":", "_") + ".md")
        fp.write_text(text, encoding="utf-8")
        index.append(
            {
                "id": cid,
                "author": c.get("author_name"),
                "group": c.get("group"),
                "time_start": min(times) if times else iso_to_cst(c.get("time_start") or ""),
                "time_end": max(times) if times else iso_to_cst(c.get("time_end") or ""),
                "n_blocks": len(blocks),
                "full_chars": full_n,
                "preview": (c.get("preview") or "")[:120],
                "file": fp.name,
            }
        )
        print(f"{full_n:6d}c {len(blocks):3d}blk {cid} {index[-1]['time_start']}")
    (out_dir / "_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
