#!/usr/bin/env python3
"""Extract Markdown data:image URIs into a sibling assets/ folder and rewrite links.

Usage:
    python extract_data_images.py [markdown-file]

Default target: MOC-饮茶室QA.md next to this script.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import sys
from pathlib import Path

DATA_IMG_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(\s*"
    r"data:image/(?P<subtype>[a-zA-Z0-9.+-]+)"
    r"(?P<params>(?:;[^,)]+)*)"
    r",(?P<data>[^)]+)\)",
    re.IGNORECASE,
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

MIME_EXT = {
    "png": ".png",
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "gif": ".gif",
    "webp": ".webp",
    "bmp": ".bmp",
    "svg+xml": ".svg",
    "x-icon": ".ico",
    "vnd.microsoft.icon": ".ico",
}

GENERIC_ALTS = {"", "img", "image", "图片", "圖", "image.png", "untitled"}


def slugify(text: str, fallback: str = "img") -> str:
    cleaned = re.sub(r"[#*`~_]+", " ", text)
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", cleaned)
    tokens = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]+", cleaned)
    slug = "-".join(tokens)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if len(slug) > 40:
        slug = slug[:40].rsplit("-", 1)[0].rstrip("-") or slug[:40]
    return slug or fallback


def nearest_heading(text: str, pos: int) -> str:
    heads = [(m.start(), m.group(2)) for m in HEADING_RE.finditer(text[:pos])]
    return heads[-1][1] if heads else ""


def extension_for(subtype: str) -> str:
    key = subtype.lower().split("+")[0] if subtype.lower().startswith("svg") else subtype.lower()
    if subtype.lower() == "svg+xml":
        return ".svg"
    return MIME_EXT.get(key, ".png")


def unique_name(assets: Path, stem: str, ext: str, used: set[str]) -> str:
    candidate = f"{stem}{ext}"
    n = 2
    while candidate in used or (assets / candidate).exists():
        candidate = f"{stem}-{n}{ext}"
        n += 1
    used.add(candidate)
    return candidate


def extract(md_path: Path, dry_run: bool = False) -> int:
    text = md_path.read_text(encoding="utf-8")
    matches = list(DATA_IMG_RE.finditer(text))
    if not matches:
        print(f"No data:image embeds in {md_path}")
        return 0

    assets = md_path.parent / "assets"
    if not dry_run:
        assets.mkdir(parents=True, exist_ok=True)

    used_names: set[str] = {p.name for p in assets.glob("*")} if assets.exists() else set()
    digest_to_name: dict[str, str] = {}
    heading_counts: dict[str, int] = {}
    pieces: list[str] = []
    last = 0

    for i, m in enumerate(matches, 1):
        subtype = m.group("subtype")
        params = (m.group("params") or "").lower()
        raw_b64 = re.sub(r"\s+", "", m.group("data"))
        alt = (m.group("alt") or "").strip()

        if "base64" not in params and not raw_b64:
            print(f"[{i}] skip: not base64", file=sys.stderr)
            continue

        try:
            payload = base64.b64decode(raw_b64, validate=False)
        except Exception as exc:
            print(f"[{i}] skip: decode failed ({exc})", file=sys.stderr)
            continue

        digest = hashlib.sha256(payload).hexdigest()
        ext = extension_for(subtype)
        heading = nearest_heading(text, m.start())
        heading_slug = slugify(heading, "img")
        alt_slug = slugify(alt, "") if alt.lower() not in GENERIC_ALTS else ""
        stem_base = alt_slug or heading_slug

        if digest in digest_to_name:
            filename = digest_to_name[digest]
            reused = True
        else:
            heading_counts[stem_base] = heading_counts.get(stem_base, 0) + 1
            stem = f"{stem_base}-{heading_counts[stem_base]:02d}"
            filename = unique_name(assets, stem, ext, used_names)
            digest_to_name[digest] = filename
            reused = False
            if not dry_run:
                (assets / filename).write_bytes(payload)

        rel = f"assets/{filename}"
        pieces.append(text[last : m.start()])
        pieces.append(f"![{alt or filename}]({rel})")
        last = m.end()

        size_kb = len(payload) / 1024
        flag = "reuse" if reused else "write"
        print(f"[{i}] {flag} {rel}  ({size_kb:.0f} KiB, {subtype})  heading={heading_slug}")

    pieces.append(text[last:])
    new_text = "".join(pieces)

    if dry_run:
        print(f"Dry run: would update {md_path} ({len(matches)} image(s))")
        return len(matches)

    md_path.write_text(new_text, encoding="utf-8", newline="\n")
    print(f"Updated {md_path.name}: {len(matches)} image(s) -> {assets}")
    return len(matches)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "markdown",
        nargs="?",
        default=str(Path(__file__).with_name("MOC-饮茶室QA.md")),
        help="Markdown file to process",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    md_path = Path(args.markdown).resolve()
    if not md_path.is_file():
        print(f"File not found: {md_path}", file=sys.stderr)
        return 1
    extract(md_path, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
