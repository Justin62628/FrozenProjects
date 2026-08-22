# 饮茶室片段提取

```bash
cd 饮茶室QA
python _extract/extract_fragments.py
python _extract/review_server.py
```

- **Golden set:** `_extract/golden_set.json` (git-tracked). Needles in preview/body are never dropped; they get reason `golden_set` and a high score. `data/` stays local/gitignored.
- **Review list:** defaults to **oldest first** (`time_start` ascending). Use the 时间↑/↓ / 分数↓ control to change. Filter and `/api/decisions` are unchanged.
- **Author arc:** `_extract/author_theory_arc.py --uin QQ号`. Needs `pip install -r _extract/requirements.txt` (scikit-learn). Writes `_extract/data/author_<uin>.json` and a 发展史 markdown.
