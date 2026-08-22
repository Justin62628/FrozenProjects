#!/usr/bin/env python3
"""Extract one QQ author's messages, cluster into theories, bind to the vault.

Usage (cwd = 饮茶室QA):

    $env:PYTHONIOENCODING='utf-8'
    python _extract/author_theory_arc.py --uin 2778807491
    python _extract/author_theory_arc.py --uin 2778807491 -o 其他/FrozenHeart冰学观发展史.md
    python _extract/author_theory_arc.py --from-json _extract/data/author_2778807491.json -o 其他/FrozenHeart冰学观发展史.md

Markdown is a chronological 发展史 (first-seen, then later recaps). Clustering
only labels what appeared when; headings are time periods, not theory names.

Reads groups.json (tea / qitan / klein; dir or zip) via jsonl_io.
Writes sidecar JSON under _extract/data/author_<uin>.json (gitignored).
Local char n-gram TF-IDF (scikit-learn) seeds from vault notes + golden_set
+ 语录 headings, then agglomerative leftover clusters. Requires
`pip install -r _extract/requirements.txt`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering, MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

from jsonl_io import add_group_args, iter_raw, load_group_specs

HERE = Path(__file__).resolve().parent
QA = HERE.parent
REPO = QA.parent
DATA = HERE / "data"
GOLDEN_PATH = HERE / "golden_set.json"
CST = timezone(timedelta(hours=8))

LONG_CHAR = 80
SLOGAN_CHAR = 18
ESSAY_CHAR = 400
SEED_COSINE = 0.16
SEED_COSINE_OTHER = 0.28
NEEDLE_MIN = 12
NEEDLE_BIND = 20
LEFTOVER_DIST = 0.62
LEFTOVER_MIN_POSTS = 2
LEFTOVER_MIN_CHARS = 280
MAX_LEFTOVER_KMEANS = 220
QUOTE_LEN = 90
GENERIC_NEEDLES = {
    "第五灵",
    "elsa",
    "anna",
    "ahtohallan",
    "athl",
    "frozen",
    "northuldra",
    "arendelle",
    "冰雪",
    "魔法",
    "女王",
    "姐妹",
    "冰二",
    "冰一",
}

VAULT_DIRS = (
    "核心",
    "冰学独立理论与分析",
    "冰学讨论",
    "同人",
    "其他",
)
SKIP_NOTE = re.compile(r"^(MOC-|NOTE-|_source)", re.I)
IMG_RE = re.compile(r"\[图片(?::[^\]]*)?\]")
FACE_RE = re.compile(r"\[(?:动画)?表情\]|\[emoji:[^\]]*\]")
FORWARD_RE = re.compile(r"^\[转发消息")
URL_RE = re.compile(r"https?://\S+|b23\.tv/\S+")
YAML_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.M)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")
RECAP_RE = re.compile(
    r"以前写过|之前写过|20年的理论|20年理论|我之前提出|详见|回指|那段分析|我好久都没更",
)
INDEX_STEMS = {
    "FrozenHeart语录",
    "游鱼语录",
    "核心FAQ",
    "冰学发展简史",
    "JU：冰学演化史",
    "常见缩写",
    "饮茶室是干嘛的",
    "冰雪时间线发生顺序（冰雪编年史）",
    "Klein：F2常见问题与解答",
}
AUTHOR_PREFIX = {
    "frozenheart": "FH",
    "fh": "FH",
    "klein": "Klein",
    "土豆": "土豆",
    "游鱼": "游鱼",
    "ju": "JU",
    "纳西妲": "纳西妲",
    "馄饨": "馄饨",
    "chaosice": "馄饨",
}


def atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def norm_uin(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def sender_uin(raw: dict) -> str:
    s = raw.get("sender") or {}
    return norm_uin(s.get("uin") if s.get("uin") not in (None, "", 0, "0") else s.get("uinStr"))


def sender_uid(raw: dict) -> str:
    s = raw.get("sender") or {}
    return str(s.get("uid") or s.get("uidStr") or "")


def sender_name(raw: dict) -> str:
    s = raw.get("sender") or {}
    return (s.get("name") or s.get("groupCard") or s.get("nickname") or "").strip()


def fmt_time(raw: dict) -> str:
    t = raw.get("time") or ""
    if t:
        try:
            dt = datetime.fromisoformat(str(t).replace("Z", "+00:00")).astimezone(CST)
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


def parse_cst(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
    except ValueError:
        return None


def strip_noise(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = IMG_RE.sub("", text)
    text = FACE_RE.sub("", text)
    if text.startswith("[回复消息]"):
        text = text[len("[回复消息]") :].lstrip()
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def body_text(raw: dict) -> str:
    c = raw.get("content") or {}
    text = strip_noise(c.get("text") or "")
    if FORWARD_RE.match(text):
        text = ""
    parts: list[str] = []
    for el in c.get("elements") or []:
        t = el.get("type")
        d = el.get("data") or {}
        if t == "text":
            parts.append(d.get("text") or "")
        elif t == "at":
            name = (d.get("name") or "").strip()
            if name:
                parts.append("@" + name)
    joined = strip_noise("".join(parts))
    return joined or text


def has_image_only(raw: dict, body: str) -> bool:
    if body:
        return False
    for el in (raw.get("content") or {}).get("elements") or []:
        if el.get("type") in {"text", "at", "json", "file", "forward"}:
            d = el.get("data") or {}
            if (d.get("text") or d.get("filename") or d.get("title") or "").strip():
                return False
    return True


def walk_nested(raw: dict) -> list[dict]:
    out: list[dict] = []
    for el in (raw.get("content") or {}).get("elements") or []:
        if el.get("type") != "forward":
            continue
        for m in (el.get("data") or {}).get("messages") or []:
            out.append(m)
            out.extend(walk_nested(m))
    return out


def counts(text: str) -> dict:
    text = text or ""
    cjk = len(CJK_RE.findall(text))
    latin = len(LATIN_WORD_RE.findall(text))
    return {
        "chars": len(text),
        "cjk": cjk,
        "latin_words": latin,
        "words": cjk + latin,
    }


def add_counts(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = int(out.get(k, 0)) + int(v)
    return out


def is_generic_needle(s: str) -> bool:
    t = s.strip().lower()
    if len(t) < NEEDLE_MIN:
        return True
    if t in GENERIC_NEEDLES:
        return True
    return False


def load_golden() -> list[dict]:
    if not GOLDEN_PATH.is_file():
        return []
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return list(data.get("entries") or [])


def parse_yaml_block(raw: str) -> tuple[dict, str]:
    m = YAML_RE.match(raw)
    if not m:
        return {}, raw
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.strip().startswith("-"):
            continue
        k, v = line.split(":", 1)
        key = k.strip()
        if key in {"title", "area", "source", "time_start", "time_end"}:
            meta[key] = v.strip().strip("\"'")
    body = raw[m.end() :]
    return meta, body


def wikilink_of(path: Path) -> str:
    try:
        rel = path.relative_to(REPO).with_suffix("").as_posix()
    except ValueError:
        rel = path.stem
    return f"[[{rel}]]"


def vault_kind(rel_posix: str) -> str:
    if "/同人/" in f"/{rel_posix}":
        return "fanfic"
    if "/冰学讨论/" in f"/{rel_posix}":
        return "discussion"
    if "/核心/" in f"/{rel_posix}":
        return "core"
    if "/其他/" in f"/{rel_posix}":
        return "other"
    return "theory"


def extract_needles_from_body(body: str, title: str) -> list[str]:
    needles: list[str] = []
    if title and not is_generic_needle(title):
        bare = re.sub(r"^[A-Za-z0-9]+：", "", title).strip()
        if bare and not is_generic_needle(bare):
            needles.append(bare)
        needles.append(title)
    for m in HEADING_RE.finditer(body):
        h = m.group(2).strip()
        h = re.sub(r"\[\[([^\]|#]+).*?\]\]", r"\1", h)
        if h and not is_generic_needle(h):
            needles.append(h)
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(">") :
            s = s.lstrip(">").strip()
            s = s.strip("*").strip()
            s = re.sub(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s+", "", s)
            if 24 <= len(s) <= 160 and not is_generic_needle(s[:40]):
                needles.append(s[:80])
        elif s.startswith("主张：") and len(s) > 20:
            needles.append(s[3:].strip()[:80])
    # distinctive mid-length lines (not chat dumps)
    for para in re.split(r"\n{2,}", body):
        p = re.sub(r"\[\[([^\]|#]+).*?\]\]", r"\1", para)
        p = strip_noise(p)
        p = re.sub(r"^#+\s+", "", p).strip()
        if 36 <= len(p) <= 140 and CJK_RE.search(p):
            needles.append(p[:100])
    seen: set[str] = set()
    out: list[str] = []
    for n in needles:
        n = re.sub(r"\s+", " ", n).strip()
        if len(n) < NEEDLE_MIN or n.lower() in seen:
            continue
        if is_generic_needle(n):
            continue
        seen.add(n.lower())
        out.append(n)
        if len(out) >= 40:
            break
    return out


def load_vault_notes() -> list[dict]:
    notes: list[dict] = []
    for folder in VAULT_DIRS:
        root = QA / folder
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if SKIP_NOTE.match(path.name) or path.name.startswith("_"):
                continue
            raw = path.read_text(encoding="utf-8")
            meta, body = parse_yaml_block(raw)
            title = meta.get("title") or path.stem
            rel = path.relative_to(REPO).with_suffix("").as_posix()
            seed_text = f"{title}\n{path.stem}\n" + strip_noise(body)[:8000]
            claim = ""
            for line in body.splitlines():
                s = line.strip()
                if s.startswith("主张："):
                    claim = s[3:].strip()
                    break
            notes.append(
                {
                    "path": rel,
                    "file": str(path.relative_to(QA).as_posix()),
                    "title": title,
                    "area": meta.get("area") or folder,
                    "kind": vault_kind("/" + rel),
                    "wikilink": wikilink_of(path),
                    "time_start": meta.get("time_start") or "",
                    "claim": claim,
                    "seed_text": seed_text,
                    "needles": extract_needles_from_body(body, title),
                    "headings": [
                        m.group(2).strip()
                        for m in HEADING_RE.finditer(body)
                        if m.group(1) != "#"
                    ],
                }
            )
    golden_by_dest: dict[str, list[str]] = defaultdict(list)
    for g in load_golden():
        dest = (g.get("dest_hint") or "").replace("\\", "/").removesuffix(".md")
        for n in g.get("needles") or []:
            if n and not is_generic_needle(n):
                golden_by_dest[dest].append(n)
    for note in notes:
        extra = golden_by_dest.get(note["path"]) or golden_by_dest.get(
            note["path"].removeprefix("饮茶室QA/")
        )
        if extra:
            have = {x.lower() for x in note["needles"]}
            for n in extra:
                if n.lower() not in have:
                    note["needles"].append(n)
                    have.add(n.lower())
            note["seed_text"] = note["seed_text"] + "\n" + "\n".join(extra)
    return notes


def display_prefix(name: str) -> str:
    key = name.strip().lower()
    if key in AUTHOR_PREFIX:
        return AUTHOR_PREFIX[key]
    for k, v in AUTHOR_PREFIX.items():
        if k in key:
            return v
    return ""


def collect_author_messages(specs: list[dict], uin: str) -> tuple[list[dict], dict]:
    """Return compact posts (top-level + nested same-uin) and raw stats."""
    posts: list[dict] = []
    names: Counter[str] = Counter()
    uids: Counter[str] = Counter()
    stats = {
        "scanned": 0,
        "author_top": 0,
        "author_nested": 0,
        "skipped_recalled": 0,
        "skipped_system": 0,
        "skipped_empty": 0,
        "skipped_image": 0,
        "kept": 0,
        "by_group": {},
    }
    seen_ids: set[str] = set()

    def consider(raw: dict, group: str, nested: bool) -> None:
        stats["scanned"] += 1
        if sender_uin(raw) != uin:
            return
        if nested:
            stats["author_nested"] += 1
        else:
            stats["author_top"] += 1
        nm = sender_name(raw)
        if nm:
            names[nm] += 1
        uid = sender_uid(raw)
        if uid:
            uids[uid] += 1
        gstat = stats["by_group"].setdefault(
            group,
            {
                "top": 0,
                "nested": 0,
                "kept": 0,
                "chars": 0,
                "cjk": 0,
                "words": 0,
            },
        )
        if nested:
            gstat["nested"] += 1
        else:
            gstat["top"] += 1
        if raw.get("recalled"):
            stats["skipped_recalled"] += 1
            return
        if raw.get("system"):
            stats["skipped_system"] += 1
            return
        body = body_text(raw)
        if has_image_only(raw, body) and not body:
            stats["skipped_image"] += 1
            return
        if not body:
            stats["skipped_empty"] += 1
            return
        mid = str(raw.get("id") or "")
        key = mid or f"{group}:{fmt_time(raw)}:{hash(body)}"
        if key in seen_ids:
            return
        seen_ids.add(key)
        ct = counts(body)
        gstat["kept"] += 1
        gstat["chars"] += ct["chars"]
        gstat["cjk"] += ct["cjk"]
        gstat["words"] += ct["words"]
        stats["kept"] += 1
        posts.append(
            {
                "id": mid,
                "group": group,
                "nested": nested,
                "time": fmt_time(raw),
                "ts": int(raw.get("timestamp") or 0),
                "uid": uid,
                "name": nm,
                "n": ct["chars"],
                "cjk": ct["cjk"],
                "words": ct["words"],
                "text": body,
            }
        )

    for spec in specs:
        key = spec["key"]
        print(f"扫描 {key} …", file=sys.stderr)
        n_before = stats["author_top"]
        for raw in iter_raw(spec["root"]):
            consider(raw, key, False)
            for nested in walk_nested(raw):
                consider(nested, key, True)
        print(
            f"  {key}: 顶层 {stats['author_top'] - n_before} 条该 uin",
            file=sys.stderr,
        )

    stats["display_name"] = names.most_common(1)[0][0] if names else ""
    stats["names"] = names.most_common(12)
    stats["uid"] = uids.most_common(1)[0][0] if uids else ""
    stats["uids"] = uids.most_common(8)
    posts.sort(key=lambda p: (p["time"], p["ts"], p["id"]))
    return posts, stats


def all_needles(notes: list[dict]) -> list[tuple[str, str]]:
    """(needle, note_path) longest-first."""
    pairs: list[tuple[str, str]] = []
    for note in notes:
        for n in note["needles"]:
            if not is_generic_needle(n):
                pairs.append((n, note["path"]))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


def slogan_hit(text: str, needles: list[tuple[str, str]]) -> str | None:
    for n, path in needles:
        if len(n) >= SLOGAN_CHAR and n in text:
            return path
    return None


def filter_clusterable(
    posts: list[dict], notes: list[dict]
) -> list[dict]:
    needles = all_needles(notes)
    out: list[dict] = []
    for p in posts:
        hit = slogan_hit(p["text"], needles)
        long = p["n"] >= LONG_CHAR
        if long or hit:
            q = dict(p)
            q["keep_reason"] = "long" if long else "slogan"
            q["slogan_note"] = hit or ""
            out.append(q)
    return out


def tfidf_matrix(docs: list[str]):
    vec = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        min_df=1,
        max_features=60_000,
        lowercase=False,
    )
    return normalize(vec.fit_transform(docs))


def stem_of(note: dict) -> str:
    return Path(note["file"]).stem


def is_index_note(note: dict) -> bool:
    return stem_of(note) in INDEX_STEMS


def is_theirs(note: dict, prefix: str, display: str = "") -> bool:
    name = Path(note["file"]).name
    title = note["title"]
    if prefix and (f"{prefix}：" in name or f"{prefix}：" in title):
        return True
    if display and display in title:
        return True
    return False


def needle_bind(text: str, notes: list[dict], prefer_prefix: str) -> tuple[str | None, str]:
    best_path = None
    best_len = 0
    best_pref = False
    for note in notes:
        pref = bool(prefer_prefix) and (
            f"{prefer_prefix}：" in note["title"]
            or f"{prefer_prefix}：" in Path(note["file"]).name
        )
        for n in note["needles"]:
            if len(n) < NEEDLE_BIND or n not in text:
                continue
            better = len(n) > best_len or (len(n) == best_len and pref and not best_pref)
            if better:
                best_path = note["path"]
                best_len = len(n)
                best_pref = pref
    if best_path and best_len >= NEEDLE_BIND:
        return best_path, f"needle:{best_len}"
    return None, ""


def notes_by_path(notes: list[dict]) -> dict[str, dict]:
    return {n["path"]: n for n in notes}


def assign_to_seeds(
    kept: list[dict],
    notes: list[dict],
    prefer_prefix: str,
    display: str = "",
) -> tuple[dict[str, list[int]], list[int], list[str]]:
    """Return path->indices, leftover indices, bind reasons aligned to kept."""
    docs = [k["text"][:12000] for k in kept]
    seed_docs = [n["seed_text"][:12000] for n in notes]
    matrix = tfidf_matrix(docs + seed_docs)
    n_posts = len(kept)
    sim = cosine_similarity(matrix[:n_posts], matrix[n_posts:])
    boost = np.array(
        [1.15 if is_theirs(n, prefer_prefix, display) else 1.0 for n in notes]
    )
    scored = sim * boost
    by_path: dict[str, list[int]] = defaultdict(list)
    leftover: list[int] = []
    reasons = [""] * n_posts

    for i, post in enumerate(kept):
        path, why = needle_bind(post["text"], notes, prefer_prefix)
        if not path and post.get("slogan_note"):
            path, why = post["slogan_note"], "slogan"
        if path:
            by_path[path].append(i)
            reasons[i] = why
            continue
        best_j = int(np.argmax(scored[i]))
        best = float(scored[i, best_j])
        note = notes[best_j]
        if is_index_note(note):
            leftover.append(i)
            reasons[i] = f"leftover-index:{best:.3f}"
            continue
        thresh = (
            SEED_COSINE
            if is_theirs(note, prefer_prefix, display)
            else SEED_COSINE_OTHER
        )
        if best >= thresh:
            by_path[note["path"]].append(i)
            reasons[i] = f"cosine:{best:.3f}"
        else:
            leftover.append(i)
            reasons[i] = f"leftover:{best:.3f}"
    return by_path, leftover, reasons


def cluster_leftover(kept: list[dict], leftover: list[int]) -> list[list[int]]:
    if not leftover:
        return []
    if len(leftover) == 1:
        return [leftover]
    texts = [kept[i]["text"][:12000] for i in leftover]
    arr = tfidf_matrix(texts)
    n = len(leftover)
    if n <= MAX_LEFTOVER_KMEANS:
        model = AgglomerativeClustering(
            n_clusters=None,
            metric="cosine",
            linkage="average",
            distance_threshold=LEFTOVER_DIST,
        )
        labels = model.fit_predict(arr.toarray())
    else:
        k = max(8, min(36, n // 12))
        model = MiniBatchKMeans(
            n_clusters=k, random_state=0, n_init=4, batch_size=256
        )
        labels = model.fit_predict(arr)
    buckets: dict[int, list[int]] = defaultdict(list)
    for loc, lab in enumerate(labels):
        buckets[int(lab)].append(leftover[loc])
    return list(buckets.values())


def cluster_label(posts: list[dict]) -> str:
    longest = max(posts, key=lambda p: p["n"])
    text = re.sub(r"\s+", " ", longest["text"]).strip()
    # prefer a CJK clause
    for part in re.split(r"[。！？\n]", text):
        part = part.strip()
        if 12 <= len(part) <= 40:
            return part
    return text[:36] + ("…" if len(text) > 36 else "")


def recap_kind(post: dict, first_time: str) -> str:
    if RECAP_RE.search(post["text"]):
        return "recap"
    ft = parse_cst(first_time)
    pt = parse_cst(post["time"])
    if ft and pt and (pt - ft).days >= 180 and post["n"] < ESSAY_CHAR:
        return "restatement"
    if post["n"] >= ESSAY_CHAR:
        return "formulation"
    return "note"


def build_cluster(
    cluster_id: str,
    members: list[dict],
    note: dict | None,
    bind_reason: str,
    prefix: str = "",
    display: str = "",
) -> dict:
    members = sorted(members, key=lambda p: (p["time"], p["ts"]))
    first = members[0]["time"]
    last = members[-1]["time"]
    essays = [p for p in members if p["n"] >= ESSAY_CHAR]
    first_essay = essays[0]["time"] if essays else first
    vault_time = (note or {}).get("time_start") or ""
    canonical_first = vault_time or first_essay
    total = {"chars": 0, "cjk": 0, "words": 0}
    by_group: dict[str, dict] = {}
    by_year: dict[str, dict] = {}
    stages: list[dict] = []
    quotes: list[dict] = []
    for i, p in enumerate(members):
        total = add_counts(total, {"chars": p["n"], "cjk": p["cjk"], "words": p["words"]})
        g = by_group.setdefault(p["group"], {"n": 0, "chars": 0, "cjk": 0, "words": 0})
        g["n"] += 1
        g["chars"] += p["n"]
        g["cjk"] += p["cjk"]
        g["words"] += p["words"]
        year = (p["time"] or "")[:4] or "unknown"
        y = by_year.setdefault(year, {"n": 0, "chars": 0, "cjk": 0, "words": 0})
        y["n"] += 1
        y["chars"] += p["n"]
        y["cjk"] += p["cjk"]
        y["words"] += p["words"]
        kind = recap_kind(p, first)
        if i == 0:
            kind = "first"
        stages.append(
            {
                "time": p["time"],
                "group": p["group"],
                "id": p["id"],
                "kind": kind,
                "n": p["n"],
                "preview": re.sub(r"\s+", " ", p["text"])[:QUOTE_LEN],
            }
        )
        if (kind in {"first", "formulation"} or p["n"] >= ESSAY_CHAR) and len(quotes) < 4:
            quotes.append(
                {
                    "time": p["time"],
                    "group": p["group"],
                    "text": re.sub(r"\s+", " ", p["text"])[:QUOTE_LEN],
                }
            )
        elif kind == "recap" and len(quotes) < 5:
            quotes.append(
                {
                    "time": p["time"],
                    "group": p["group"],
                    "text": re.sub(r"\s+", " ", p["text"])[:QUOTE_LEN],
                }
            )
    label = note["title"] if note else cluster_label(members)
    kind = note["kind"] if note else "unbound"
    theirs = bool(note) and is_theirs(note, prefix, display)
    return {
        "id": cluster_id,
        "label": label,
        "kind": kind,
        "theirs": theirs,
        "claim": (note or {}).get("claim") or "",
        "vault": note["path"] if note else "",
        "wikilink": note["wikilink"] if note else "",
        "bind_reason": bind_reason,
        "first_time": first,
        "first_essay": first_essay,
        "canonical_first": canonical_first,
        "vault_time": vault_time,
        "last_time": last,
        "n_posts": len(members),
        "chars": total["chars"],
        "cjk": total["cjk"],
        "words": total["words"],
        "groups": by_group,
        "years": by_year,
        "stages": stages,
        "quotes": quotes,
        "member_ids": [p["id"] for p in members],
    }


def year_stats(posts: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in posts:
        year = (p["time"] or "")[:4] or "unknown"
        y = out.setdefault(year, {"n": 0, "chars": 0, "cjk": 0, "words": 0})
        y["n"] += 1
        y["chars"] += p["n"]
        y["cjk"] += p["cjk"]
        y["words"] += p["words"]
    return out


def suggest_filename(display: str) -> str:
    if not display:
        return "作者冰学观发展史.md"
    if display.lower() in {"frozenheart", "fh"} or "FrozenHeart" in display:
        return "FrozenHeart冰学观发展史.md"
    safe = re.sub(r'[\\/:*?"<>|]', "", display).strip()
    return f"{safe}冰学观发展史.md"


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


def run(uin: str, specs: list[dict], out_md: Path | None) -> dict:
    notes = load_vault_notes()
    print(f"库内种子 {len(notes)} 篇", file=sys.stderr)
    posts, scan = collect_author_messages(specs, uin)
    kept = filter_clusterable(posts, notes)
    print(f"保留文本 {len(posts)}，聚类候选 {len(kept)}", file=sys.stderr)

    display = scan.get("display_name") or ""
    prefix = display_prefix(display)
    by_path, leftover, reasons = assign_to_seeds(kept, notes, prefix, display)
    leftover_groups = cluster_leftover(kept, leftover)
    index = notes_by_path(notes)

    clusters: list[dict] = []
    for path, idxs in by_path.items():
        note = index.get(path)
        members = [kept[i] for i in idxs]
        why = reasons[idxs[0]] if idxs else "seed"
        cid = "seed:" + (note["file"] if note else path)
        clusters.append(build_cluster(cid, members, note, why, prefix, display))

    for n, group in enumerate(leftover_groups, start=1):
        members = [kept[i] for i in group]
        chars = sum(m["n"] for m in members)
        if len(members) < LEFTOVER_MIN_POSTS and chars < LEFTOVER_MIN_CHARS:
            continue
        clusters.append(
            build_cluster(f"unsup:{n}", members, None, "unsupervised", prefix, display)
        )

    # merge clusters that landed on the same vault path (tiny + seed)
    merged: dict[str, dict] = {}
    unbound_list: list[dict] = []
    for c in clusters:
        key = c.get("vault") or ""
        if not key:
            unbound_list.append(c)
            continue
        if key not in merged:
            merged[key] = c
            continue
        # keep richer label; sum is approximate (rebuild from stages)
        a, b = merged[key], c
        if b["chars"] > a["chars"]:
            a, b = b, a
        a["n_posts"] += b["n_posts"]
        a["chars"] += b["chars"]
        a["cjk"] += b["cjk"]
        a["words"] += b["words"]
        a["stages"] = sorted(a["stages"] + b["stages"], key=lambda s: s["time"])
        if a["stages"]:
            a["first_time"] = a["stages"][0]["time"]
            a["last_time"] = a["stages"][-1]["time"]
        merged[key] = a
    clusters = list(merged.values()) + unbound_list
    clusters.sort(key=lambda c: (c["first_time"], -c["cjk"]))

    total = {"chars": 0, "cjk": 0, "words": 0}
    for p in posts:
        total["chars"] += p["n"]
        total["cjk"] += p["cjk"]
        total["words"] += p["words"]

    payload = {
        "author": {
            "uin": uin,
            "uid": scan.get("uid") or "",
            "display_name": display,
            "names": scan.get("names") or [],
            "prefix": prefix,
        },
        "stats": {
            "author_top": scan.get("author_top", 0),
            "author_nested": scan.get("author_nested", 0),
            "kept": scan.get("kept", 0),
            "clustered": len(kept),
            "skipped_recalled": scan.get("skipped_recalled", 0),
            "skipped_system": scan.get("skipped_system", 0),
            "skipped_empty": scan.get("skipped_empty", 0),
            "skipped_image": scan.get("skipped_image", 0),
            "chars": total["chars"],
            "cjk": total["cjk"],
            "words": total["words"],
            "by_group": scan.get("by_group") or {},
            "by_year": year_stats(posts),
            "time_start": posts[0]["time"] if posts else "",
            "time_end": posts[-1]["time"] if posts else "",
        },
        "clusters": clusters,
        "unbound": [c for c in clusters if not c.get("vault")],
    }
    json_path = DATA / f"author_{uin}.json"
    atomic_write_json(json_path, payload)
    print(f"JSON {json_path}", file=sys.stderr)

    out_md = resolve_out_md(out_md, display)
    write_out_markdown(payload, out_md)
    payload["_out_md"] = str(out_md)
    payload["_out_json"] = str(json_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="按 QQ uin 抽消息、聚类理论、绑定库内笔记")
    add_group_args(p)
    p.add_argument("--uin", help="QQ 号（sender.uin）；--from-json 时可省略")
    p.add_argument(
        "-o",
        "--out",
        type=Path,
        help="发展史 markdown（相对 饮茶室QA/）。默认 其他/<显示名>冰学观发展史.md",
    )
    p.add_argument(
        "--from-json",
        type=Path,
        help="只从 sidecar JSON 重渲 markdown，不重扫群聊",
    )
    args = p.parse_args(argv)
    if args.from_json:
        path = args.from_json
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        display = (payload.get("author") or {}).get("display_name") or ""
        out_md = resolve_out_md(args.out, display)
        write_out_markdown(payload, out_md)
        a = payload.get("author") or {}
        st = payload.get("stats") or {}
        print(
            f"{a.get('display_name') or '?'} uin={a.get('uin')} "
            f"clusters={len(payload.get('clusters') or [])} "
            f"(render-only from {path.name})",
            file=sys.stderr,
        )
        return 0
    uin = norm_uin(args.uin)
    if not uin:
        raise SystemExit("需要 --uin 或 --from-json")
    specs = load_group_specs(args.config, extra_paths=args.group or [])
    payload = run(uin, specs, args.out)
    a = payload["author"]
    st = payload["stats"]
    print(
        f"{a['display_name'] or '?'} uin={a['uin']} uid={a['uid']} "
        f"top={st['author_top']} kept={st['kept']} clustered={st['clustered']} "
        f"clusters={len(payload['clusters'])} unbound={len(payload['unbound'])}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
