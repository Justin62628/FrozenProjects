#!/usr/bin/env python3
"""Read QQChatExporter chunked JSONL from a directory or a .zip.

A path may be:
  - a `*_chunked_jsonl` directory with `chunks/c*.jsonl`
  - a `.zip` of that export (members like `…/chunks/c*.jsonl`)
  - a single `.jsonl` file

Zip inner names may be UTF-8 or a legacy OEM code page; match by
`chunks/c*.jsonl` suffix, do not require the top folder name to decode.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "groups.json"

# Known keys so CLI --group can reuse stable ids.
_NAME_KEYS = {
    "冰学三点饮茶室": "tea",
    "克莱恩家的晚宴": "klein",
    "冰学奇谈会议室": "qitan",
    "❄️冰学奇谈会议室": "qitan",
}


def _norm_zip_name(name: str) -> str:
    return name.replace("\\", "/")


def is_chunk_jsonl_name(name: str) -> bool:
    n = _norm_zip_name(name)
    leaf = n.rsplit("/", 1)[-1]
    if not (leaf.startswith("c") and leaf.endswith(".jsonl")):
        return False
    return "/chunks/" in f"/{n}" or n.startswith("chunks/")


def is_zip_path(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".zip"


def list_zip_chunk_names(zf: zipfile.ZipFile) -> list[str]:
    names = [n for n in zf.namelist() if is_chunk_jsonl_name(n)]
    names.sort()
    return names


def read_manifest(source: Path) -> dict | None:
    """Return manifest.json from a dir or zip, or None."""
    source = source.expanduser()
    if is_zip_path(source):
        with zipfile.ZipFile(source) as zf:
            mans = [
                n
                for n in zf.namelist()
                if _norm_zip_name(n).rstrip("/").endswith("manifest.json")
            ]
            if not mans:
                return None
            return json.loads(zf.read(mans[0]).decode("utf-8"))
    man = source / "manifest.json"
    if man.is_file():
        return json.loads(man.read_text(encoding="utf-8"))
    return None


def list_chunk_labels(source: Path) -> list[str]:
    """Human-readable chunk labels (paths or zip member names)."""
    source = source.expanduser()
    if not source.exists():
        return []
    if is_zip_path(source):
        with zipfile.ZipFile(source) as zf:
            return list_zip_chunk_names(zf)
    if source.is_file() and source.suffix.lower() == ".jsonl":
        return [str(source)]
    chunks = source / "chunks"
    if chunks.is_dir():
        files = sorted(chunks.glob("c*.jsonl"))
        if files:
            return [str(p) for p in files]
    return [str(p) for p in sorted(source.glob("*.jsonl")) if p.is_file()]


def iter_jsonl_lines(source: Path) -> Iterator[str]:
    """Yield utf-8 text lines from a dir, zip, or .jsonl file."""
    source = source.expanduser()
    if not source.exists():
        raise FileNotFoundError(f"找不到导出：{source}")

    if is_zip_path(source):
        with zipfile.ZipFile(source) as zf:
            names = list_zip_chunk_names(zf)
            if not names:
                raise FileNotFoundError(f"zip 里没有 chunks/c*.jsonl：{source}")
            for name in names:
                with zf.open(name, "r") as raw:
                    wrapper = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                    yield from wrapper
        return

    if source.is_file() and source.suffix.lower() == ".jsonl":
        with source.open("r", encoding="utf-8") as f:
            yield from f
        return

    chunks = source / "chunks"
    files: list[Path] = []
    if chunks.is_dir():
        files = sorted(chunks.glob("c*.jsonl"))
    if not files:
        files = sorted(p for p in source.glob("*.jsonl") if p.is_file())
    if not files:
        raise FileNotFoundError(f"找不到 jsonl：{source}")
    for fp in files:
        with fp.open("r", encoding="utf-8") as f:
            yield from f


def iter_raw(source: Path) -> Iterator[dict]:
    for line in iter_jsonl_lines(source):
        line = line.strip()
        if line:
            yield json.loads(line)


def infer_group_meta(path: Path, primary: bool = True) -> dict:
    stem = path.name
    if stem.lower().endswith(".zip"):
        stem = stem[:-4]
    if stem.endswith("_chunked_jsonl"):
        stem = stem[: -len("_chunked_jsonl")]
    m = re.match(r"^group_(.+?)_(\d+)(?:_|$)", stem)
    name = m.group(1) if m else stem
    key = _NAME_KEYS.get(name)
    if not key:
        stripped = name.lstrip("❄❄️ \t")
        key = _NAME_KEYS.get(stripped)
    if not key:
        key = re.sub(r"[^\w]+", "_", name).strip("_") or "group"
    return {"key": key, "name": name, "root": path, "primary": primary}


def load_group_specs(
    config: Path | None = None,
    extra_paths: list[Path] | None = None,
    skip_missing: bool = True,
) -> list[dict]:
    """Load N groups from groups.json and/or --group PATH."""
    specs: list[dict] = []
    seen_keys: set[str] = set()
    cfg = config if config is not None else DEFAULT_CONFIG
    if cfg and Path(cfg).is_file():
        data = json.loads(Path(cfg).read_text(encoding="utf-8"))
        for item in data.get("groups") or []:
            path = Path(item["path"]).expanduser()
            if not path.exists():
                msg = f"警告：群导出不存在，跳过 {item.get('key')}: {path}"
                if skip_missing:
                    print(msg, file=sys.stderr)
                    continue
                raise FileNotFoundError(msg)
            key = str(item["key"])
            if key in seen_keys:
                raise SystemExit(f"重复的 group key：{key}")
            seen_keys.add(key)
            specs.append(
                {
                    "key": key,
                    "name": item.get("name") or key,
                    "root": path,
                    "primary": bool(item.get("primary", True)),
                }
            )
    for raw in extra_paths or []:
        path = Path(raw).expanduser()
        if not path.exists():
            msg = f"警告：--group 路径不存在，跳过 {path}"
            if skip_missing:
                print(msg, file=sys.stderr)
                continue
            raise FileNotFoundError(msg)
        meta = infer_group_meta(path)
        if meta["key"] in seen_keys:
            # same key: override path (CLI wins)
            for spec in specs:
                if spec["key"] == meta["key"]:
                    spec["root"] = path
                    spec["name"] = meta["name"] or spec["name"]
                    break
            continue
        seen_keys.add(meta["key"])
        specs.append(meta)
    if not specs:
        raise SystemExit("没有可用的群导出（检查 groups.json 或 --group PATH）")
    return specs


def add_group_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="群列表 JSON（name/key/path/primary）",
    )
    p.add_argument(
        "--group",
        action="append",
        type=Path,
        default=[],
        metavar="PATH",
        help="额外或覆盖的 chunked_jsonl 目录 / zip（可重复）",
    )
