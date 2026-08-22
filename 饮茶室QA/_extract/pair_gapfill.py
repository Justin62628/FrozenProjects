#!/usr/bin/env python3
"""Gap-fill adjacent conversations between two QQ UINs for 2021-2022."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
OUT = DATA / "pair_gapfill_2778807491_2669766268_2021_2022.json"
CONFIG = HERE / "groups.json"

sys.path.insert(0, str(HERE))
from jsonl_io import iter_raw, load_group_specs  # noqa: E402
from author_theory_arc import body_text, sender_name, sender_uid, sender_uin, walk_nested  # noqa: E402

TARGET = {"2778807491", "2669766268"}
TARGET_NAMES = {"2778807491": "FrozenHeart", "2669766268": "渔父"}
UIDS = {"u_uqYRlo5ZEl3UlDaX-LAPtQ", "u_s17564ReUCMAnRNA3wQs7A"}
START = 1609459200000  # 2021-01-01 UTC
END = 1672617600000  # 2023-01-01 UTC
PAIR_WINDOW = 45 * 60 * 1000
MERGE_WINDOW = 6 * 60 * 60 * 1000
CONTEXT_MS = 15 * 60 * 1000

SIGNALS = {
    "Ahtohallan": ["Ahtohallan", "Antohallan", "阿塔霍"],
    "第五灵": ["第五灵", "the fifth spirit", "fifth spirit"],
    "桥": ["双桥", "一桥", "bridge", "两座桥"],
    "魔法心理": ["魔法", "fear", "love", "人性", "心理", "情绪", "意识"],
    "F2线": ["F2", "F2后", "Elsa", "Anna", "姐妹", "莎雕", "娜雕"],
    "设定材料": ["FOS", "DS", "PN", "AIF", "Anthology", "JN", "小说"],
    "梦与记忆": ["梦", "回忆", "记忆", "Voice", "声音", "预知"],
    "永生寿命": ["永生", "长生", "寿命", "死亡", "死后", "老去"],
    "世界观": ["四灵", "自然", "人类", "Northuldra", "Arendelle", "世界观", "规则"],
    "理论措辞": ["理论", "假设", "推测", "我认为", "说明", "因此", "由此", "核心", "本质"],
}


def iso_ms(ts: int) -> str:
    # Export timestamps are UTC; the vault uses China Standard Time.
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).astimezone(timezone(timedelta(hours=8)))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def compact(m: dict, group: str, nested: bool) -> dict:
    ts = int(m.get("timestamp") or 0)
    return {
        "group": group,
        "id": str(m.get("id") or ""),
        "seq": str(m.get("seq") or ""),
        "ts": ts,
        "time": iso_ms(ts) if ts else str(m.get("time") or ""),
        "uin": sender_uin(m),
        "uid": sender_uid(m),
        "name": sender_name(m),
        "text": body_text(m),
        "nested": nested,
    }


def collect() -> dict[str, list[dict]]:
    streams: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()
    for spec in load_group_specs(CONFIG):
        for raw in iter_raw(spec["root"]):
            for m, nested in [(raw, False), *[(x, True) for x in walk_nested(raw)]]:
                uin = sender_uin(m)
                ts = int(m.get("timestamp") or 0)
                if uin not in TARGET or not (START <= ts < END):
                    continue
                key = (spec["key"], str(m.get("id") or ""), uin)
                if key in seen:
                    continue
                seen.add(key)
                streams[spec["key"]].append(compact(m, spec["key"], nested))
    for arr in streams.values():
        arr.sort(key=lambda x: (x["ts"], x["id"]))
    return streams


def signal_hits(text: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for label, terms in SIGNALS.items():
        found = [term for term in terms if term.lower() in text.lower()]
        if found:
            hits[label] = found
    return hits


def make_sessions(arr: list[dict]) -> list[dict]:
    last: dict[str, int | None] = {uin: None for uin in TARGET}
    hits: list[tuple[int, int, int]] = []
    for i, m in enumerate(arr):
        last[m["uin"]] = m["ts"]
        if all(last.values()):
            lo = min(int(last[uin]) for uin in TARGET)
            hi = max(int(last[uin]) for uin in TARGET)
            if hi - lo <= PAIR_WINDOW:
                hits.append((i, lo, hi))
    groups: list[dict] = []
    for i, lo, hi in hits:
        if groups and lo - groups[-1]["last_pair_ts"] <= MERGE_WINDOW:
            groups[-1]["last_pair_ts"] = hi
            groups[-1]["last_hit_i"] = i
        else:
            groups.append({"first_pair_ts": lo, "last_pair_ts": hi, "first_hit_i": i, "last_hit_i": i})

    sessions: list[dict] = []
    for no, g in enumerate(groups, 1):
        lo = g["first_pair_ts"] - CONTEXT_MS
        hi = g["last_pair_ts"] + CONTEXT_MS
        msgs = [m for m in arr if lo <= m["ts"] <= hi]
        text = "\n".join(f"{m['name'] or TARGET_NAMES.get(m['uin'], m['uin'])}: {m['text']}" for m in msgs if m["text"])
        counts = Counter(m["uin"] for m in msgs)
        signals = signal_hits(text)
        sessions.append(
            {
                "session": no,
                "group": msgs[0]["group"] if msgs else "tea",
                "time_start": msgs[0]["time"] if msgs else iso_ms(g["first_pair_ts"]),
                "time_end": msgs[-1]["time"] if msgs else iso_ms(g["last_pair_ts"]),
                "first_pair_time": iso_ms(g["first_pair_ts"]),
                "last_pair_time": iso_ms(g["last_pair_ts"]),
                "n_messages": len(msgs),
                "n_frozenheart": counts["2778807491"],
                "n_yufu": counts["2669766268"],
                "chars": len(text),
                "signals": signals,
                "messages": msgs,
            }
        )
    return sessions


def candidate_gapfill() -> list[dict]:
    p = DATA / "candidates.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    out: list[dict] = []
    for c in d.get("candidates", []):
        if not str(c.get("time_start", "")).startswith(("2021-", "2022-")):
            continue
        msgs = c.get("messages", [])
        uids = {m.get("uid") for m in msgs}
        if not (uids & UIDS):
            continue
        out.append(
            {
                "id": c.get("id"),
                "kind": c.get("kind"),
                "group": c.get("group"),
                "time_start": c.get("time_start"),
                "time_end": c.get("time_end"),
                "score": c.get("score"),
                "reasons": c.get("reasons", []),
                "author_uid": c.get("author_uid"),
                "author_name": c.get("author_name"),
                "n_msgs": c.get("n_msgs"),
                "preview": c.get("preview", ""),
                "uids": sorted(uids & UIDS),
                "has_both": bool(uids & UIDS == UIDS),
                "messages": msgs,
            }
        )
    return out


def main() -> None:
    streams = collect()
    sessions: list[dict] = []
    for group, arr in streams.items():
        sessions.extend(make_sessions(arr))
    sessions.sort(key=lambda s: s["first_pair_time"])
    for i, s in enumerate(sessions, 1):
        s["session"] = i

    all_msgs = [m for arr in streams.values() for m in arr]
    stats = {
        "period": "2021-01-01 to 2022-12-31",
        "groups_with_target": sorted(streams),
        "groups_with_adjacent_sessions": sorted({s["group"] for s in sessions}),
        "messages_total": len(all_msgs),
        "messages_by_uin": Counter(m["uin"] for m in all_msgs),
        "messages_by_year": Counter(m["time"][:4] for m in all_msgs),
        "messages_by_year_uin": Counter(f'{m["time"][:4]}:{m["uin"]}' for m in all_msgs),
        "messages_by_group": Counter(m["group"] for m in all_msgs),
        "chars_total": sum(len(m["text"]) for m in all_msgs),
        "sessions": len(sessions),
        "sessions_by_year": Counter(s["first_pair_time"][:4] for s in sessions),
        "sessions_with_theory_signals": sum(1 for s in sessions if any(k in s["signals"] for k in ("理论措辞", "第五灵", "桥", "Ahtohallan", "世界观"))),
    }
    payload = {
        "source": str(CONFIG),
        "targets": TARGET_NAMES,
        "stats": stats,
        "candidate_intersections": candidate_gapfill(),
        "sessions": sessions,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(OUT), "stats": stats, "candidate_intersections": len(payload["candidate_intersections"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
