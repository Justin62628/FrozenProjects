from pathlib import Path

arc = Path(__file__).with_name("author_theory_arc.py")
block = Path(__file__).with_name("_chrono_block.py")
src = arc.read_text(encoding="utf-8")
new_fns = block.read_text(encoding="utf-8").rstrip() + "\n"

start = src.index("def md_escape_heading")
end = src.index("\n\ndef run(")
src = src[:start] + new_fns + src[end:]

old_resolve = '''    if out_md is None:
        out_md = QA / "其他" / suggest_filename(display)
    elif not out_md.is_absolute():
        out_md = (QA / out_md).resolve()
    md = render_markdown(payload, str(out_md.relative_to(QA).as_posix()))
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")
    print(f"Markdown {out_md}", file=sys.stderr)
'''
new_resolve = '''    out_md = resolve_out_md(out_md, display)
    write_out_markdown(payload, out_md)
'''
if old_resolve not in src:
    raise SystemExit("resolve block not found")
src = src.replace(old_resolve, new_resolve, 1)

old_doc = '''    python _extract/author_theory_arc.py --uin 2778807491
    python _extract/author_theory_arc.py --uin 2778807491 -o 其他/FrozenHeart冰学观发展史.md
'''
new_doc = '''    python _extract/author_theory_arc.py --uin 2778807491
    python _extract/author_theory_arc.py --uin 2778807491 -o 其他/FrozenHeart冰学观发展史.md
    python _extract/author_theory_arc.py --from-json _extract/data/author_2778807491.json -o 其他/FrozenHeart冰学观发展史.md

Markdown is a chronological 发展史 (first-seen, then later recaps). Clustering
only labels what appeared when; headings are time periods, not theory names.
'''
if old_doc not in src:
    raise SystemExit("docstring usage not found")
src = src.replace(old_doc, new_doc, 1)

old_main = '''    p.add_argument("--uin", required=True, help="QQ 号（sender.uin）")
    p.add_argument(
        "-o",
        "--out",
        type=Path,
        help="发展史 markdown（相对 饮茶室QA/）。默认 其他/<显示名>冰学观发展史.md",
    )
    args = p.parse_args(argv)
    uin = norm_uin(args.uin)
    if not uin:
        raise SystemExit("uin 不能为空")
    specs = load_group_specs(args.config, extra_paths=args.group or [])
    payload = run(uin, specs, args.out)
'''
new_main = '''    p.add_argument("--uin", help="QQ 号（sender.uin）；--from-json 时可省略")
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
'''
if old_main not in src:
    raise SystemExit("main argparse block not found")
src = src.replace(old_main, new_main, 1)

# drop unused helper if present
src = src.replace(
    '''def _period_of(t: str) -> tuple[int, str]:
    s = t or ""
    if s < "2021":
        return (0, str(s[:4] or "更早"))
    return (int(s[:4] or 0), s[:4] or "未知")


''',
    "",
)

arc.write_text(src, encoding="utf-8")
print("spliced", arc, "len", len(src.splitlines()))
