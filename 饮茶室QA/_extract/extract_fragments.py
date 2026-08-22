#!/usr/bin/env python3
"""Scan chunked QQ JSONL and write candidate theory/discussion fragments.

Usage:
    python extract_fragments.py
    python extract_fragments.py --config groups.json
    python extract_fragments.py --group PATH [--group PATH ...]

Writes data/candidates.json. Does not touch data/decisions.json.
Groups come from groups.json (N dirs or zips) and optional --group PATH.
Needles in golden_set.json (repo root of this folder) are never dropped:
matching preview/body gets reason golden_set and a high score.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from jsonl_io import add_group_args, iter_raw, load_group_specs

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = DATA / "candidates.json"
GOLDEN_PATH = HERE / "golden_set.json"
GOLDEN_SCORE = 10_000

# QQ 正文中位约 12 字；「比较长」按 ≥80 字（约 p99）。
SILENCE_MS = 30 * 60 * 1000
CUE_MS = 15 * 60 * 1000
BURST_GAP_MS = 20 * 60 * 1000
LONG_CONTINUE_MS = 45 * 60 * 1000
FOLLOW_MS = 6 * 60 * 60 * 1000
MAX_FOLLOW = 40
BURST_MIN_LONG = 3
BURST_MIN_CHARS = 400
LONG_CHAR = 80
ESSAY_CHAR = 400
MAX_INTERRUPT = 10
DISC_MIN = 180
DISC_RATIO = 3.0
NEARBY = 15
OLD_REPLY_MS = 24 * 60 * 60 * 1000
LOCATOR = 10
# 晚宴只收跨群转发，或正文里明确的冰学信号（不用 Anna/Elsa，群名片会误伤）。
TEA_SIGNAL = re.compile(
    r"冰学|饮茶室|Ahtohallan|阿塔霍|第五灵|莎雕|冰雪奇缘|质感|双桥|Athl|Northuldra",
    re.I,
)
URL_RE = re.compile(r"https?://\S+|b23\.tv/\S+")
DOC_EXT = (".pdf", ".epub", ".doc", ".docx", ".txt", ".md")



def atomic_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def file_names(elements, into: list[str]) -> None:
    for el in elements or []:
        t = el.get("type")
        d = el.get("data") or {}
        if t == "file" and d.get("filename"):
            into.append(d["filename"])
        if t == "forward":
            for m in d.get("messages") or []:
                file_names((m.get("content") or {}).get("elements"), into)


def compact(raw: dict, group: str) -> dict:
    c = raw.get("content") or {}
    els = c.get("elements") or []
    sender = raw.get("sender") or {}
    body_parts: list[str] = []
    reply = None
    has_image = False
    has_link = False
    has_forward = False
    fwd_title = ""
    fwd_n = 0
    nested: list[dict] = []
    json_url = ""
    for el in els:
        t = el.get("type")
        d = el.get("data") or {}
        if t == "text":
            body_parts.append(d.get("text") or "")
        elif t == "at":
            name = d.get("name") or ""
            body_parts.append("@" + name if name else "")
        elif t == "reply":
            reply = {
                "id": str(d.get("referencedMessageId") or d.get("messageId") or ""),
                "name": d.get("senderName") or "",
                "preview": d.get("content") or "",
                "ts": (d.get("timestamp") or 0) * 1000
                if d.get("timestamp") and d["timestamp"] < 10_000_000_000
                else d.get("timestamp") or 0,
            }
        elif t == "image":
            has_image = True
        elif t == "json":
            has_link = True
            json_url = d.get("url") or ""
            body_parts.append(d.get("title") or d.get("summary") or "")
        elif t == "forward":
            has_forward = True
            fwd_title = d.get("title") or ""
            msgs = d.get("messages") or []
            fwd_n = len(msgs)
            for m in msgs:
                ms = m.get("sender") or {}
                nested.append(
                    {
                        "id": str(m.get("id") or ""),
                        "ts": int(m.get("timestamp") or 0),
                        "uid": ms.get("uid") or "",
                        "name": ms.get("name") or "",
                        "text": ((m.get("content") or {}).get("text") or "")[:800],
                    }
                )
    body = "".join(body_parts).strip()
    text = (c.get("text") or "").strip()
    if URL_RE.search(text) or URL_RE.search(body):
        has_link = True
    files: list[str] = []
    file_names(els, files)
    return {
        "group": group,
        "id": str(raw.get("id") or ""),
        "seq": str(raw.get("seq") or ""),
        "ts": int(raw.get("timestamp") or 0),
        "time": raw.get("time") or "",
        "uid": sender.get("uid") or "",
        "name": sender.get("name") or sender.get("nickname") or "",
        "type": raw.get("type") or "",
        "system": bool(raw.get("system")),
        "body": body,
        "n": len(body),
        "text": text[:2000],
        "reply": reply,
        "has_image": has_image,
        "has_link": has_link,
        "has_forward": has_forward,
        "fwd_title": fwd_title,
        "fwd_n": fwd_n,
        "nested": nested,
        "files": files,
        "json_url": json_url,
    }


def load_group(spec: dict) -> list[dict]:
    rows = []
    for raw in iter_raw(spec["root"]):
        rows.append(compact(raw, spec["key"]))
    return rows


def uid_ts_index(rows: list[dict]) -> dict[tuple[str, int], str]:
    idx = {}
    for m in rows:
        if m["uid"] and m["ts"]:
            idx[(m["uid"], m["ts"])] = m["group"]
    return idx


def match_nested_by_group(
    nested: list[dict], other: dict[tuple[str, int], str]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in nested:
        if m["uid"] and m["ts"] and (m["uid"], m["ts"]) in other:
            src = other[(m["uid"], m["ts"])]
            counts[src] = counts.get(src, 0) + 1
    return counts


def match_nested(nested: list[dict], other: dict[tuple[str, int], str]) -> int:
    return sum(match_nested_by_group(nested, other).values())


def public_msg(m: dict, role: str = "chat") -> dict:
    return {
        "role": role,
        "group": m["group"],
        "id": m["id"],
        "seq": m["seq"],
        "time": m["time"],
        "uid": m["uid"],
        "name": m["name"],
        "type": m["type"],
        "text": m["text"],
        "reply": m["reply"],
        "files": m["files"],
        "has_image": m["has_image"],
        "has_link": m["has_link"],
        "fwd_title": m["fwd_title"],
        "fwd_n": m["fwd_n"],
        "json_url": m["json_url"],
    }


def collect_files(msgs: list[dict]) -> list[str]:
    seen: list[str] = []
    hit = set()
    for m in msgs:
        for name in m.get("files") or []:
            if name not in hit:
                hit.add(name)
                seen.append(name)
    return seen


def is_open_cue(m: dict) -> bool:
    return m["has_image"] or m["has_link"] or m["has_forward"] or bool(m["files"])


def pre_cue_index(rows: list[dict], i: int) -> int | None:
    """Same-uid image/forward/link shortly before i, even if others spoke in between."""
    uid = rows[i]["uid"]
    t0 = rows[i]["ts"]
    for k in range(i - 1, -1, -1):
        if t0 - rows[k]["ts"] > CUE_MS:
            return None
        if rows[k]["system"] or not rows[k]["uid"]:
            continue
        if rows[k]["uid"] == uid:
            return k if is_open_cue(rows[k]) else None
    return None


def silent_before(rows: list[dict], i: int) -> bool:
    uid = rows[i]["uid"]
    t0 = rows[i]["ts"]
    for k in range(i - 1, -1, -1):
        if t0 - rows[k]["ts"] > SILENCE_MS:
            return True
        if rows[k]["uid"] == uid and not rows[k]["system"]:
            return False
    return True


def next_burst_indices(rows: list[dict], i: int) -> list[int]:
    uid = rows[i]["uid"]
    idxs = [i]
    last_t = rows[i]["ts"]
    n = len(rows)
    t = i + 1
    while t < n and len(idxs) < 80:
        if rows[t]["system"] or not rows[t]["uid"]:
            t += 1
            continue
        if rows[t]["uid"] == uid:
            gap = rows[t]["ts"] - last_t
            allow = LONG_CONTINUE_MS if (rows[t]["n"] >= LONG_CHAR or rows[t]["files"]) else BURST_GAP_MS
            if gap > allow:
                break
            idxs.append(t)
            last_t = rows[t]["ts"]
            t += 1
            continue
        others = 1
        t += 1
        while t < n and others <= MAX_INTERRUPT:
            if rows[t]["system"] or not rows[t]["uid"]:
                t += 1
                continue
            if rows[t]["uid"] == uid:
                break
            others += 1
            t += 1
        if others > MAX_INTERRUPT:
            break
    return idxs


def reply_to_other(rows: list[dict], i: int, by_id: dict[str, int]) -> bool:
    rep = rows[i].get("reply")
    if not rep:
        return False
    pid = rep.get("id") or ""
    if pid in by_id:
        return rows[by_id[pid]]["uid"] != rows[i]["uid"]
    name = (rep.get("name") or "").strip()
    return bool(name and name != rows[i]["name"])


def locator_indices(rows: list[dict], core: list[int]) -> tuple[list[int], list[int]]:
    """±10 around the theory dump itself, not around old cited parents."""
    lo, hi = min(core), max(core)
    core_ids = {rows[x]["id"] for x in core}
    author = rows[core[0]]["uid"]
    before = []
    for k in range(lo - 1, -1, -1):
        if rows[k]["system"]:
            continue
        before.append(k)
        if len(before) >= LOCATOR:
            break
    before.reverse()
    after = []
    others_run = 0
    for k in range(hi + 1, len(rows)):
        if rows[k]["system"]:
            continue
        rep_id = (rows[k].get("reply") or {}).get("id") or ""
        relevant = rows[k]["uid"] == author or rep_id in core_ids
        if not relevant:
            others_run += 1
            if others_run > MAX_INTERRUPT:
                break
        else:
            others_run = 0
        after.append(k)
        if len(after) >= LOCATOR:
            break
    return before, after


def follow_replies(rows: list[dict], by_id: dict[str, int], core_ids: set[str], end_i: int) -> list[int]:
    extra = []
    live = set(core_ids)
    end_ts = rows[end_i]["ts"]
    n = len(rows)
    for j in range(end_i + 1, n):
        if rows[j]["ts"] - end_ts > FOLLOW_MS:
            break
        if len(extra) >= MAX_FOLLOW:
            break
        rep = rows[j].get("reply")
        if not rep:
            continue
        rid = rep.get("id") or ""
        if rid in live:
            extra.append(j)
            live.add(rows[j]["id"])
    return extra


def cited_parents(rows: list[dict], by_id: dict[str, int], core: list[int]) -> tuple[list[int], bool]:
    parents = []
    old = False
    seen = set()
    for i in core:
        rep = rows[i].get("reply")
        if not rep:
            continue
        pid = rep.get("id") or ""
        if pid not in by_id or pid in seen:
            continue
        seen.add(pid)
        parents.append(by_id[pid])
        rts = int(rep.get("ts") or 0)
        if rts and rows[i]["ts"] - rts >= OLD_REPLY_MS:
            old = True
        elif pid in by_id and rows[i]["ts"] - rows[by_id[pid]]["ts"] >= OLD_REPLY_MS:
            old = True
    return parents, old


def klein_ok(rows: list[dict], core: list[int], reasons: list[str]) -> bool:
    if "cross_forward" in reasons:
        return True
    blob = "".join(rows[x]["body"] + rows[x]["text"] for x in core)
    return bool(TEA_SIGNAL.search(blob))


_GOLDEN_CACHE: list[dict] | None = None


def load_golden_set() -> list[dict]:
    global _GOLDEN_CACHE
    if _GOLDEN_CACHE is not None:
        return _GOLDEN_CACHE
    if not GOLDEN_PATH.is_file():
        _GOLDEN_CACHE = []
        return _GOLDEN_CACHE
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if isinstance(data, list):
        _GOLDEN_CACHE = data
    else:
        _GOLDEN_CACHE = list(data.get("entries") or [])
    return _GOLDEN_CACHE


def golden_needles(entry: dict) -> list[str]:
    return [n for n in (entry.get("needles") or []) if n]


def text_hits_needles(text: str, needles: list[str]) -> bool:
    return any(n in text for n in needles)


def candidate_blob(c: dict) -> str:
    parts = [c.get("preview") or ""]
    for m in c.get("messages") or []:
        parts.append(m.get("text") or "")
    return "\n".join(parts)


def row_blob(m: dict) -> str:
    return (m.get("body") or "") + "\n" + (m.get("text") or "")


def golden_entries_for(group: str) -> list[dict]:
    out = []
    for g in load_golden_set():
        if g.get("group") and g["group"] != group:
            continue
        if golden_needles(g):
            out.append(g)
    return out


def golden_hit_rows(rows: list[dict], idxs: list[int], group: str) -> dict | None:
    blobs = [row_blob(rows[i]) for i in idxs]
    preferred = None
    for g in load_golden_set():
        needles = golden_needles(g)
        if not any(text_hits_needles(b, needles) for b in blobs):
            continue
        if not g.get("group") or g["group"] == group:
            return g
        preferred = preferred or g
    return preferred


def force_golden_candidate(
    spec: dict, rows: list[dict], i: int, other_idx: dict, golden: dict
) -> dict:
    kind = "discussion" if golden.get("verdict") == "keep_discussion" else "theory"
    by_id = {m["id"]: j for j, m in enumerate(rows) if m["id"]}
    core = [i]
    parents, cites_old = cited_parents(rows, by_id, core)
    follow = follow_replies(rows, by_id, {rows[x]["id"] for x in core}, core[-1])
    before, after = locator_indices(rows, core)
    reasons = ["golden_set"]
    if cites_old:
        reasons.append("cites_old")
    cand = make_candidate(
        kind,
        spec,
        rows,
        core,
        parents + follow + before + after,
        reasons,
        GOLDEN_SCORE,
        other_idx,
        {rows[x]["id"] for x in parents},
        {rows[x]["id"] for x in before + after},
    )
    if golden.get("id"):
        cand["id"] = golden["id"]
    return cand


def seal_golden_misses(
    out: list[dict], spec: dict, rows: list[dict], other_idx: dict
) -> None:
    """Force-keep golden needles that never became a candidate."""
    for g in golden_entries_for(spec["key"]):
        needles = golden_needles(g)
        if any(text_hits_needles(candidate_blob(c), needles) for c in out):
            continue
        for i, m in enumerate(rows):
            if not text_hits_needles(row_blob(m), needles):
                continue
            out.append(force_golden_candidate(spec, rows, i, other_idx, g))
            break


def apply_golden_set(cands: list[dict]) -> None:
    """Mark existing candidates that match a golden needle; never drop them."""
    goldens = load_golden_set()
    if not goldens:
        return
    for c in cands:
        blob = candidate_blob(c)
        for g in goldens:
            if not text_hits_needles(blob, golden_needles(g)):
                continue
            if "golden_set" not in (c.get("reasons") or []):
                c.setdefault("reasons", []).append("golden_set")
            c["score"] = max(int(c.get("score") or 0), GOLDEN_SCORE)
            break


def make_candidate(
    kind: str,
    spec: dict,
    rows: list[dict],
    core: list[int],
    extra: list[int],
    reasons: list[str],
    score: int,
    other_idx: dict,
    cited_ids: set[str] | None = None,
    ctx_ids: set[str] | None = None,
) -> dict:
    cited_ids = cited_ids or set()
    ctx_ids = ctx_ids or set()
    order = sorted(set(core + extra))
    seed = rows[core[0]]
    msgs = []
    cross = []
    for i in order:
        m = rows[i]
        if m["id"] in cited_ids:
            role = "cited"
        elif m["id"] in ctx_ids:
            role = "ctx"
        else:
            role = "chat"
        msgs.append(public_msg(m, role))
        if m["nested"]:
            hits = match_nested_by_group(m["nested"], other_idx)
            if hits:
                for src, n_hit in hits.items():
                    cross.append(
                        {
                            "from": src,
                            "title": m["fwd_title"],
                            "nested": m["fwd_n"],
                            "matched": n_hit,
                        }
                    )
            if hits or m["fwd_n"]:
                for n in m["nested"]:
                    src = spec["key"]
                    if n["uid"] and n["ts"] and (n["uid"], n["ts"]) in other_idx:
                        src = other_idx[(n["uid"], n["ts"])]
                    msgs.append(
                        {
                            "role": "forwarded",
                            "group": src,
                            "id": n["id"],
                            "seq": "",
                            "time": "",
                            "uid": n["uid"],
                            "name": n["name"],
                            "type": "forwarded",
                            "text": n["text"],
                            "reply": None,
                            "files": [],
                            "has_image": "[图片" in n["text"],
                            "has_link": bool(URL_RE.search(n["text"])),
                            "fwd_title": "",
                            "fwd_n": 0,
                            "json_url": "",
                        }
                    )
    cid = f"{spec['key']}:{kind}:{seed['id']}"
    preview = ""
    for x in order:
        if rows[x]["id"] in cited_ids or rows[x]["id"] in ctx_ids:
            continue
        t = rows[x]["body"] or rows[x]["text"]
        if len(t) >= 20:
            preview = t[:160]
            break
    return {
        "id": cid,
        "kind": kind,
        "group": spec["key"],
        "group_name": spec["name"],
        "score": score,
        "reasons": reasons,
        "author_uid": seed["uid"],
        "author_name": seed["name"],
        "time_start": rows[order[0]]["time"],
        "time_end": rows[order[-1]]["time"],
        "n_msgs": sum(1 for x in msgs if x["role"] not in ("forwarded", "ctx")),
        "n_ctx": sum(1 for x in msgs if x["role"] == "ctx"),
        "n_forwarded": sum(1 for x in msgs if x["role"] == "forwarded"),
        "files": collect_files([rows[i] for i in order]),
        "cross_forwards": cross,
        "preview": preview or (seed["body"] or seed["text"])[:160],
        "messages": msgs,
    }


def extract_group(spec: dict, rows: list[dict], other_idx: dict) -> list[dict]:
    out = []
    by_id = {m["id"]: i for i, m in enumerate(rows) if m["id"]}
    used_core: set[str] = set()
    n = len(rows)
    i = 0
    while i < n:
        m = rows[i]
        if m["system"] or not m["uid"]:
            i += 1
            continue

        reasons = []
        core: list[int] = []
        score = 0

        # 跨群合并转发：嵌套正文就是材料，不要求本人再写长文。
        cross_n = match_nested(m["nested"], other_idx)
        if m["has_forward"] and cross_n:
            core = [i]
            reasons.append("cross_forward")
            score = 400 + m["fwd_n"] * 4 + cross_n * 8
        if spec["primary"] and any((n or "").lower().endswith(DOC_EXT) for n in m["files"]):
            if i not in core:
                core = [i] + core
            reasons.append("file_drop")
            score = max(score, 250)

        idxs = next_burst_indices(rows, i)
        long_sum = sum(rows[x]["n"] for x in idxs if rows[x]["n"] >= LONG_CHAR)
        nlong = sum(1 for x in idxs if rows[x]["n"] >= LONG_CHAR)
        pre = pre_cue_index(rows, i)
        opener = is_open_cue(m) or pre is not None
        quiet = silent_before(rows, i)
        if nlong >= BURST_MIN_LONG and long_sum >= BURST_MIN_CHARS:
            if quiet:
                reasons.append("silent_then_burst")
            if opener:
                reasons.append("media_then_burst")
            if quiet or opener:
                core = ([pre] if pre is not None else []) + idxs
                score = max(score, long_sum + nlong * 20)
        elif spec["primary"] and m["n"] >= ESSAY_CHAR and not reply_to_other(rows, i, by_id):
            reasons.append("essay")
            core = ([pre] if pre is not None else []) + idxs
            score = max(score, m["n"] + long_sum)

        if core and reasons:
            keep = spec["primary"] or klein_ok(rows, core, reasons)
            gold = golden_hit_rows(rows, core, spec["key"])
            if gold:
                keep = True
                if "golden_set" not in reasons:
                    reasons.append("golden_set")
                score = max(score, GOLDEN_SCORE)
            if keep:
                core = list(dict.fromkeys(core))
                core_ids = {rows[x]["id"] for x in core}
                parents, cites_old = cited_parents(rows, by_id, core)
                follow = follow_replies(rows, by_id, core_ids, core[-1])
                before, after = locator_indices(rows, core)
                if cites_old:
                    reasons.append("cites_old")
                ctx = {rows[x]["id"] for x in before + after}
                out.append(
                    make_candidate(
                        "theory",
                        spec,
                        rows,
                        core,
                        parents + follow + before + after,
                        reasons,
                        score,
                        other_idx,
                        {rows[x]["id"] for x in parents},
                        ctx,
                    )
                )
                used_core.update(rows[x]["id"] for x in core)
                i = core[-1] + 1
                continue
        i += 1

    for i, m in enumerate(rows):
        if m["system"] or m.get("type") == "json" or not m.get("reply") or m["n"] < DISC_MIN:
            continue
        if m["id"] in used_core:
            continue
        gold = golden_hit_rows(rows, [i], spec["key"])
        if not spec["primary"] and not TEA_SIGNAL.search(m["body"] + m["text"]) and not gold:
            continue
        lo, hi = max(0, i - NEARBY), min(n, i + NEARBY + 1)
        others = [
            rows[k]["n"]
            for k in range(lo, hi)
            if k != i and rows[k]["uid"] != m["uid"] and rows[k]["n"] > 0
        ]
        if not others:
            continue
        med = sorted(others)[len(others) // 2]
        if med <= 0 or m["n"] < DISC_RATIO * med:
            continue
        core = [i]
        parents, cites_old = cited_parents(rows, by_id, core)
        extra = follow_replies(rows, by_id, {rows[x]["id"] for x in core + parents}, i)
        reasons = ["long_reply"]
        if gold:
            reasons.append("golden_set")
        if cites_old:
            reasons.append("cites_old")
        out.append(
            make_candidate(
                "discussion",
                spec,
                rows,
                core,
                parents + extra,
                reasons,
                GOLDEN_SCORE if gold else m["n"],
                other_idx,
                {rows[x]["id"] for x in parents},
            )
        )
    seal_golden_misses(out, spec, rows, other_idx)
    return out


def other_uid_ts_index(
    loaded: dict[str, list[dict]], skip_key: str
) -> dict[tuple[str, int], str]:
    idx: dict[tuple[str, int], str] = {}
    for key, rows in loaded.items():
        if key == skip_key:
            continue
        idx.update(uid_ts_index(rows))
    return idx


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="从 N 个 chunked JSONL / zip 提取候选片段")
    add_group_args(p)
    args = p.parse_args(argv)
    groups = load_group_specs(args.config, extra_paths=args.group)

    loaded: dict[str, list[dict]] = {}
    for spec in groups:
        print(f"loading {spec['key']} ({spec['name']}) from {spec['root']}...")
        loaded[spec["key"]] = load_group(spec)
        print(f"  {spec['key']}: {len(loaded[spec['key']])} msgs")

    print("extracting...")
    cands: list[dict] = []
    for spec in groups:
        cands += extract_group(
            spec, loaded[spec["key"]], other_uid_ts_index(loaded, spec["key"])
        )
    apply_golden_set(cands)
    cands.sort(key=lambda x: (-x["score"], x["time_start"]))
    n_by_group = {spec["key"]: len(loaded[spec["key"]]) for spec in groups}
    payload = {
        "source": [str(spec["root"]) for spec in groups],
        "n_by_group": n_by_group,
        "n_tea": n_by_group.get("tea"),
        "n_klein": n_by_group.get("klein"),
        "n_qitan": n_by_group.get("qitan"),
        "n_candidates": len(cands),
        "n_theory": sum(1 for x in cands if x["kind"] == "theory"),
        "n_discussion": sum(1 for x in cands if x["kind"] == "discussion"),
        "candidates": cands,
    }
    atomic_write(OUT, payload)
    print(
        f"wrote {OUT}  theory={payload['n_theory']}  "
        f"discussion={payload['n_discussion']}  files_on_hits="
        f"{sum(1 for x in cands if x['files'])}  cross="
        f"{sum(1 for x in cands if x['cross_forwards'])}  "
        f"groups={n_by_group}"
    )
    gold_check(cands)


def gold_check(cands: list[dict]) -> None:
    """Fixed snippets the extractor must classify correctly."""
    theory_hit = disc_hit = False
    for c in cands:
        blob = "\n".join(m.get("text") or "" for m in c.get("messages") or [])
        if c["kind"] == "theory" and "“叙事质感”" in blob and "另外分别从DS和FOS" in blob:
            theory_hit = True
        if (
            c["kind"] == "discussion"
            and "先简单评一下，这个四层法" in blob
            and "之前的理论需要把一些事实层" in blob
        ):
            disc_hit = True
    if theory_hit:
        print("gold theory OK: 叙事质感 + DS/FOS")
    else:
        print("gold theory FAIL: 叙事质感 span missing")
    if disc_hit:
        print("gold discussion OK: 四层法 + 事实层/质感层")
    else:
        print("gold discussion FAIL: 四层法 extension missing")
    for g in load_golden_set():
        needles = golden_needles(g)
        gid = g.get("id") or "?"
        hit = any(text_hits_needles(candidate_blob(c), needles) for c in cands)
        print(f"golden_set {'OK' if hit else 'FAIL'}: {gid}")


if __name__ == "__main__":
    main()
