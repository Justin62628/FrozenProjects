#!/usr/bin/env python3
"""Copy formatted messages between two records in a chunked QQ JSONL export.

Usage:
    python copy_range.py PATH --start "全文" --end "全文"
    python copy_range.py PATH -s "全文" -e "全文" -o slice.md
    python copy_range.py PATH -s "全文" -e "全文" --print --no-clipboard

PATH is a QQChatExporter `*_chunked_jsonl` directory, a `.zip` of that export,
or a single `.jsonl`. Zip members named like `chunks/c*.jsonl` are streamed
(no unzip). Start/end match the record's complete content.text (strip 后全等).
两端都包含。默认写入剪贴板；摘要打到 stderr。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonl_io import iter_jsonl_lines, list_chunk_labels

CST = timezone(timedelta(hours=8))
IMG_RE = re.compile(r"\[图片(?::[^\]]*)?\]")


def resolve_source(root: Path) -> Path:
    root = root.expanduser()
    if not root.exists():
        raise SystemExit(f"找不到导出：{root}")
    labels = list_chunk_labels(root)
    if not labels and not (root.is_file() and root.suffix.lower() == ".jsonl"):
        raise SystemExit(f"找不到 jsonl（目录或 zip 内 chunks/c*.jsonl）：{root}")
    return root


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


def strip_images(text: str) -> str:
    text = IMG_RE.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def md_italic(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace("*", r"\*").replace("_", r"\_")
    return f"*{escaped}*"


def quote_lines(text: str, depth: int = 0) -> list[str]:
    mark = ">" * (depth + 1)
    out: list[str] = []
    for part in text.split("\n"):
        if part.strip():
            out.append(f"{mark} {md_italic(part)}")
        else:
            out.append(mark)
    return out


def reply_line(raw: dict) -> str:
    for el in (raw.get("content") or {}).get("elements") or []:
        if el.get("type") != "reply":
            continue
        d = el.get("data") or {}
        name = (d.get("senderName") or "").strip()
        preview = strip_images(
            (d.get("content") or "").replace("\r\n", "\n").replace("\r", "\n")
        )
        if name and preview:
            return f"↪ {name}：{preview}"
        if preview:
            return f"↪ {preview}"
        if name:
            return f"↪ {name}"
    return ""


def body_text(raw: dict) -> str:
    text = msg_text(raw)
    if text.startswith("[回复消息]"):
        text = text[len("[回复消息]") :].lstrip()
    return strip_images(text.replace("\r\n", "\n").replace("\r", "\n"))


def nested_forwards(raw: dict) -> list[dict]:
    out: list[dict] = []
    for el in (raw.get("content") or {}).get("elements") or []:
        if el.get("type") != "forward":
            continue
        d = el.get("data") or {}
        out.append(d)
    return out


def format_one(raw: dict, depth: int = 0) -> str:
    if raw.get("recalled"):
        return ""

    name = sender_name(raw)
    if raw.get("system"):
        name = name or "系统"
        who = f"{fmt_time(raw)}  [系统] {name}".rstrip()
    else:
        who = f"{fmt_time(raw)}  {name}".rstrip()

    body = body_text(raw)
    fwds = nested_forwards(raw)
    nested: list[str] = []
    for fwd in fwds:
        title = (fwd.get("title") or "聊天记录").strip()
        n = fwd.get("messageCount") or len(fwd.get("messages") or [])
        children = [c for m in fwd.get("messages") or [] if (c := format_one(m, depth + 1))]
        if not children:
            continue
        nested.extend(quote_lines(f"[转发] {title}（{n}条）", depth))
        nested.extend(children)

    if fwds and body.startswith("[转发消息"):
        body = ""

    if not body and not nested:
        return ""

    reply = reply_line(raw)
    lines = quote_lines(who, depth)
    if reply:
        lines.extend(quote_lines(reply, depth))
    if body:
        lines.extend(body.split("\n"))
    lines.extend(nested)
    return "\n".join(lines).rstrip()


def format_slice(rows: list[dict], folder: Path) -> tuple[str, int]:
    if not rows:
        return "", 0
    blocks = [b for r in rows if (b := format_one(r))]
    label = folder.name
    head = (
        f"# {label}  {fmt_time(rows[0])} → {fmt_time(rows[-1])}  {len(blocks)}条\n"
    )
    return head + "\n\n".join(blocks) + "\n", len(blocks)


def find_range(
    source: Path,
    start: str,
    end: str,
    contains: bool,
    nth_start: int,
) -> list[dict]:
    start_n = 0
    collecting = False
    rows: list[dict] = []
    same = start == end
    start_seen_in_collect = False

    safe_skip = '"' not in start and "\\" not in start
    for line in iter_jsonl_lines(source):
        if not line.strip():
            continue
        if not collecting and safe_skip and start not in line:
            continue
        raw = json.loads(line)
        text = msg_text(raw)
        hit_start = start in text if contains else text == start
        hit_end = end in text if contains else text == end
        if not collecting:
            if not hit_start:
                continue
            start_n += 1
            if start_n < nth_start:
                continue
            collecting = True
            rows.append(raw)
            if same:
                start_seen_in_collect = True
                continue
            if hit_end:
                return rows
            continue
        rows.append(raw)
        if same:
            if hit_end and start_seen_in_collect:
                return rows
            continue
        if hit_end:
            return rows

    if not collecting:
        raise SystemExit(f"找不到起始记录（exact={'off' if contains else 'on'}）：{start!r}")
    if same and len(rows) == 1:
        return rows
    raise SystemExit(f"已找到起始、但未找到结束记录：{end!r}（已收集 {len(rows)} 条）")


def copy_clipboard(text: str) -> None:
    if sys.platform == "win32":
        import ctypes

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        payload = text.encode("utf-16-le") + b"\x00\x00"
        if not user32.OpenClipboard(None):
            raise OSError("OpenClipboard failed")
        try:
            user32.EmptyClipboard()
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
            if not handle:
                raise OSError("GlobalAlloc failed")
            locked = kernel32.GlobalLock(handle)
            if not locked:
                kernel32.GlobalFree(handle)
                raise OSError("GlobalLock failed")
            ctypes.memmove(locked, payload, len(payload))
            kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(CF_UNICODETEXT, handle):
                kernel32.GlobalFree(handle)
                raise OSError("SetClipboardData failed")
        finally:
            user32.CloseClipboard()
        return

    try:
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    subprocess.run(
        ["xclip", "-selection", "clipboard"],
        input=text,
        text=True,
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="按起止全文抽取 JSONL 记录并复制")
    p.add_argument(
        "folder",
        type=Path,
        help="chunked_jsonl 目录、同名 .zip，或单个 .jsonl",
    )
    p.add_argument("--start", "-s", required=True, help="起始记录的完全文本")
    p.add_argument("--end", "-e", required=True, help="结束记录的完全文本")
    p.add_argument("-o", "--out", type=Path, help="同时写入该文件")
    p.add_argument("--print", dest="do_print", action="store_true", help="把全文打到 stdout")
    p.add_argument("--no-clipboard", action="store_true", help="不写剪贴板")
    p.add_argument("--contains", action="store_true", help="按子串匹配，而不是全文全等")
    p.add_argument("--nth-start", type=int, default=1, metavar="N", help="第 N 次起始命中（从 1 计）")
    args = p.parse_args(argv)

    start = args.start.strip()
    end = args.end.strip()
    if not start or not end:
        raise SystemExit("start / end 不能为空")
    if args.nth_start < 1:
        raise SystemExit("--nth-start 必须 ≥ 1")

    source = resolve_source(args.folder)
    rows = find_range(source, start, end, args.contains, args.nth_start)
    text, n_out = format_slice(rows, source)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")

    copied = False
    if not args.no_clipboard:
        try:
            copy_clipboard(text)
            copied = True
        except Exception as exc:
            print(f"剪贴板写入失败：{exc}", file=sys.stderr)

    print(
        f"{n_out} 条  {fmt_time(rows[0])} → {fmt_time(rows[-1])}"
        + (f"（源 {len(rows)}）" if n_out != len(rows) else "")
        + (f"  已写 {args.out}" if args.out else "")
        + ("  已复制" if copied else "  未复制"),
        file=sys.stderr,
    )
    if args.do_print or (not copied and not args.out):
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
