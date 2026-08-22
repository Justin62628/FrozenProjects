#!/usr/bin/env python3
"""Local review UI for extract_fragments.py candidates.

Usage:
    python review_server.py
    python review_server.py --port 8765

List defaults to oldest-first (time_start ascending). Filters and
/api/decisions are unchanged. Decisions persist in data/decisions.json
(not overwritten by extract).
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CANDIDATES = DATA / "candidates.json"
DECISIONS = DATA / "decisions.json"

PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>饮茶室片段筛选</title>
<style>
:root { --bg:#111; --fg:#eee; --muted:#9aa; --card:#1b1b1b; --acc:#c9a227; --ok:#3d9; --no:#d66; }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.45 system-ui,sans-serif; background:var(--bg); color:var(--fg); }
header { padding:10px 16px; border-bottom:1px solid #333; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
select, button, input { font:inherit; }
button { background:#2a2a2a; color:var(--fg); border:1px solid #444; padding:6px 10px; cursor:pointer; }
button.ok { border-color:var(--ok); }
button.no { border-color:var(--no); }
button.pri { border-color:var(--acc); color:var(--acc); }
#layout { display:grid; grid-template-columns:320px 1fr; height:calc(100vh - 52px); }
#list { overflow:auto; border-right:1px solid #333; }
#list button.item { display:block; width:100%; text-align:left; border:0; border-bottom:1px solid #222; padding:10px 12px; background:transparent; }
#list button.item.active { background:#252018; }
#list .k { font-size:12px; color:var(--acc); }
#list .muted { color:var(--muted); font-size:12px; }
#main { overflow:auto; padding:16px 20px 48px; }
.meta { color:var(--muted); font-size:13px; margin-bottom:8px; }
.files { color:#8cf; margin:8px 0; }
.cross { background:#1e2a1e; padding:8px 10px; margin:8px 0; }
.msg { background:var(--card); padding:10px 12px; margin:8px 0; border-left:3px solid #444; }
.msg.forwarded { border-left-color:var(--acc); opacity:.95; }
.msg.cited { border-left-color:#88c; }
.msg.ctx { border-left-color:#555; opacity:.75; }
.msg .who { color:var(--muted); font-size:12px; }
.msg .reply { color:#c8b; font-size:13px; margin:4px 0; }
pre { white-space:pre-wrap; word-break:break-word; margin:6px 0 0; font:inherit; }
mark { background:#53480a; color:#ffe9a0; padding:0 2px; }
.note { width:100%; margin-top:8px; background:#1a1a1a; color:var(--fg); border:1px solid #333; padding:6px; }
</style>
</head>
<body>
<header>
  <strong>片段筛选</strong>
  <select id="filter">
    <option value="unscored">未标</option>
    <option value="all">全部</option>
    <option value="theory">候选·理论</option>
    <option value="discussion">候选·讨论</option>
    <option value="cross">有跨群转发</option>
    <option value="files">带文件</option>
    <option value="keep_theory">已留·理论</option>
    <option value="keep_discussion">已留·讨论</option>
    <option value="reject">扔掉</option>
    <option value="later">待定</option>
  </select>
  <select id="sort">
    <option value="time_asc" selected>时间↑ 旧→新</option>
    <option value="time_desc">时间↓ 新→旧</option>
    <option value="score_desc">分数↓</option>
  </select>
  <input id="q" type="search" placeholder="搜索关键词" style="width:220px;background:#1a1a1a;color:var(--fg);border:1px solid #444;padding:6px 8px;">
  <span id="pos" class="muted"></span>
  <button class="pri" data-v="keep_theory">理论 1</button>
  <button class="ok" data-v="keep_discussion">讨论 2</button>
  <button class="no" data-v="reject">扔掉 3</button>
  <button data-v="later">待定 4</button>
  <span id="save" class="muted"></span>
</header>
<div id="layout">
  <nav id="list"></nav>
  <article id="main"></article>
</div>
<script>
let cands=[], decisions={}, view=[], idx=0;
const $ = id => document.getElementById(id);
async function load() {
  const a = await fetch('/api/candidates').then(r => r.json());
  const d = await fetch('/api/decisions').then(r => r.json());
  cands = a.candidates || [];
  decisions = d.decisions || {};
  apply();
}
function hay(c) {
  const parts = [c.preview, c.author_name, c.group_name, (c.files||[]).join(' '), (c.reasons||[]).join(' ')];
  for (const m of c.messages||[]) parts.push(m.text, m.name);
  return parts.join('\n').toLowerCase();
}
function timeKey(c) {
  return c.time_start || c.time_end || '';
}
function apply() {
  const f = $('filter').value;
  const q = ($('q').value || '').trim().toLowerCase();
  const s = ($('sort') && $('sort').value) || 'time_asc';
  view = cands.filter(c => {
    const v = (decisions[c.id]||{}).verdict || '';
    if (f==='unscored') { if (v) return false; }
    else if (f==='all') {}
    else if (f==='theory' || f==='discussion') { if (c.kind!==f) return false; }
    else if (f==='cross') { if (!(c.cross_forwards||[]).length) return false; }
    else if (f==='files') { if (!(c.files||[]).length) return false; }
    else if (v!==f) return false;
    if (q && !hay(c).includes(q)) return false;
    return true;
  });
  view.sort((a, b) => {
    if (s === 'score_desc') {
      const d = (b.score || 0) - (a.score || 0);
      return d || timeKey(a).localeCompare(timeKey(b));
    }
    if (s === 'time_desc') return timeKey(b).localeCompare(timeKey(a));
    return timeKey(a).localeCompare(timeKey(b));
  });
  if (idx >= view.length) idx = Math.max(0, view.length-1);
  renderList(); render();
}
function esc(s) { return (s||'').replace(/[<>]/g,''); }
function hl(s) {
  const q = ($('q').value || '').trim();
  s = esc(s);
  if (!q) return s;
  const safe = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return s.replace(new RegExp(safe, 'gi'), m => '<mark>'+m+'</mark>');
}
function renderList() {
  $('list').innerHTML = view.map((c,i) => {
    const v = (decisions[c.id]||{}).verdict || '';
    return `<button class="item ${i===idx?'active':''}" data-i="${i}">
      <div class="k">${c.kind} · ${c.group_name} ${v?('· '+v):''}</div>
      <div>${hl(c.preview||'')}</div>
      <div class="muted">${c.time_start||''} · ${c.author_name||''} · ${c.n_msgs}条</div>
    </button>`;
  }).join('') || '<p class="muted" style="padding:12px">没有条目</p>';
  $('pos').textContent = view.length ? `${idx+1}/${view.length}` : '0/0';
}
function render() {
  const c = view[idx];
  if (!c) { $('main').innerHTML = '<p class="muted">先跑 extract_fragments.py</p>'; return; }
  const d = decisions[c.id] || {};
  const files = (c.files||[]).map(x => `<code>${x}</code>`).join(' ');
  const cross = (c.cross_forwards||[]).map(x =>
    `转发自 ${x.from}「${x.title}」嵌套 ${x.nested}，对上 ${x.matched}`).join('<br>');
  const msgs = (c.messages||[]).map(m => {
    const reply = m.reply ? `<div class="reply">↩ ${m.reply.name||''}: ${(m.reply.preview||'').slice(0,180)}</div>` : '';
    const extra = [m.has_image?'[图]':'', m.has_link?'[链接]':'', m.fwd_title?`[转发 ${m.fwd_n}]`:''].filter(Boolean).join(' ');
    return `<div class="msg ${m.role}">
      <div class="who">${m.time||''} · ${m.name||''} · ${m.role}${extra?(' · '+extra):''}</div>
      ${reply}<pre>${hl(m.text||'')}</pre>
    </div>`;
  }).join('');
  $('main').innerHTML = `
    <div class="meta">${c.kind} · ${c.group_name} · ${c.author_name}<br>
    ${c.time_start} → ${c.time_end}<br>理由：${(c.reasons||[]).join(', ')} · 分 ${c.score}</div>
    ${cross?`<div class="cross">${cross}</div>`:''}
    ${files?`<div class="files">文件：${files}</div>`:'<div class="muted">无文件附件</div>'}
    ${msgs}
    <textarea class="note" id="note" rows="2" placeholder="备注">${d.note||''}</textarea>
  `;
}
async function decide(verdict) {
  const c = view[idx];
  if (!c) return;
  const note = ($('note')||{}).value || '';
  const res = await fetch('/api/decisions', {
    method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id:c.id, verdict, note})
  });
  const j = await res.json();
  decisions = j.decisions || decisions;
  $('save').textContent = '已存 '+verdict;
  if ($('filter').value==='unscored') apply();
  else { idx = Math.min(idx+1, Math.max(0, view.length-1)); renderList(); render(); }
}
$('filter').onchange = () => { idx=0; apply(); };
$('sort').onchange = () => { idx=0; apply(); };
$('q').oninput = () => { idx=0; apply(); };
$('list').onclick = e => {
  const b = e.target.closest('[data-i]');
  if (!b) return;
  idx = +b.dataset.i;
  renderList(); render();
};
document.querySelectorAll('button[data-v]').forEach(b => b.onclick = () => decide(b.dataset.v));
document.addEventListener('keydown', e => {
  if (e.target.tagName==='TEXTAREA' || e.target.tagName==='INPUT') return;
  if (e.key==='1') decide('keep_theory');
  if (e.key==='2') decide('keep_discussion');
  if (e.key==='3') decide('reject');
  if (e.key==='4') decide('later');
  if (e.key==='j' || e.key==='ArrowDown') { idx=Math.min(idx+1, view.length-1); renderList(); render(); }
  if (e.key==='k' || e.key==='ArrowUp') { idx=Math.max(idx-1, 0); renderList(); render(); }
});
load();
</script>
</body>
</html>
"""


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_decisions(obj: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = DECISIONS.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DECISIONS)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args)

    def _send(self, code: int, body, ctype: str) -> None:
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, PAGE, "text/html; charset=utf-8")
            return
        if path == "/api/candidates":
            if not CANDIDATES.exists():
                self._send(200, '{"candidates":[],"error":"run extract_fragments.py first"}', "application/json")
                return
            self._send(200, CANDIDATES.read_text(encoding="utf-8"), "application/json; charset=utf-8")
            return
        if path == "/api/decisions":
            obj = load_json(DECISIONS, {"decisions": {}})
            if "decisions" not in obj:
                obj = {"decisions": obj}
            self._send(200, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")
            return
        self._send(404, "not found", "text/plain")

    def do_PUT(self):
        if urlparse(self.path).path != "/api/decisions":
            self._send(404, "not found", "text/plain")
            return
        n = int(self.headers.get("Content-Length") or 0)
        rec = json.loads(self.rfile.read(n).decode("utf-8"))
        obj = load_json(DECISIONS, {"decisions": {}})
        if "decisions" not in obj:
            obj = {"decisions": obj}
        cid = rec.get("id")
        if not cid:
            self._send(400, '{"error":"id required"}', "application/json")
            return
        obj["decisions"][cid] = {
            "verdict": rec.get("verdict") or "",
            "note": rec.get("note") or "",
        }
        save_decisions(obj)
        self._send(200, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"http://127.0.0.1:{args.port}")
    if not CANDIDATES.exists():
        print("candidates.json missing — run extract_fragments.py first")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
