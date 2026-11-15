#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Freewrite web-export: сервер на устройстве.
Телефон (на точке «Freewrite») открывает http://10.42.0.1 → видит черновики
УЖЕ ОТФОРМАТИРОВАННЫМИ («Иван-разметка» → markdown), копирует/скачивает .md.
  /            — HTML-страница (форматированное превью + копировать/скачать)
  /export.md   — все черновики одним markdown-файлом
  /apple-touch-icon.png — иконка (портрет Азимова) для кнопки на «Домой»
"""
import http.server
import subprocess
import json
import html
import datetime
import urllib.parse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from freewrite_format import to_markdown, md_to_html  # noqa: E402

PORT = 80
MODES = {1: "Заметки", 2: "Пост", 3: "Дневник"}
ICON = "/etc/freewrite/apple-touch-icon.png"


def drafts():
    q = ('SELECT json_agg(row_to_json(t)) FROM (SELECT id,folder_id,title,body,'
         '"updatedAt" FROM document WHERE length(btrim(body))>0 ORDER BY "updatedAt" DESC) t;')
    try:
        r = subprocess.run(["su", "-", "postgres", "-c", "psql -d freewrite -tA"],
                           input=q, capture_output=True, text=True, timeout=15)
        return json.loads((r.stdout or "").strip() or "[]") or []
    except Exception:
        return []


def md_all(ds):
    parts = [f"<!-- Freewrite — {datetime.datetime.now():%Y-%m-%d %H:%M} -->\n"]
    for d in ds:
        parts.append(to_markdown(d.get("body") or ""))
        parts.append("\n---\n")
    return "\n".join(parts)


def page(ds):
    n = len(ds)
    rows = []
    for d in ds:
        mode = MODES.get(d.get("folder_id"), "Заметки")
        upd = html.escape(str(d.get("updatedAt") or "")[:16].replace("T", " "))
        md = to_markdown(d.get("body") or "")
        doc = md_to_html(md)
        src = html.escape(md)
        rows.append(f"""
      <article>
        <div class="meta"><span class="tag">{mode}</span><span class="when">{upd}</span></div>
        <div class="doc">{doc}</div>
        <textarea class="src" hidden>{src}</textarea>
        <button onclick="cp(this)">Скопировать markdown</button>
      </article>""")
    body = "".join(rows) or '<p class="empty">Пока пусто — напиши что-нибудь.</p>'
    return f"""<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Черновики</title>
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Черновики">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<style>
:root{{color-scheme:light dark}}
*{{box-sizing:border-box}}
body{{margin:0;font:18px/1.65 Georgia,'Times New Roman',serif;background:#f6f5f1;color:#1a1a1a;padding:16px 14px 60px}}
@media(prefers-color-scheme:dark){{body{{background:#111;color:#e8e8e8}}article{{background:#1b1b1b !important;border-color:#2a2a2a !important}}}}
header{{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:16px}}
h1.top{{font-size:21px;margin:0}}
.count{{opacity:.5;font-size:14px}}
.dl{{display:block;text-align:center;background:#1a1a1a;color:#fff;text-decoration:none;padding:14px;border-radius:12px;margin-bottom:18px;font-weight:600;font-family:-apple-system,system-ui}}
@media(prefers-color-scheme:dark){{.dl{{background:#eee;color:#111}}}}
article{{background:#fff;border:1px solid #e6e4de;border-radius:14px;padding:14px 18px 16px;margin-bottom:14px}}
.meta{{display:flex;gap:8px;align-items:center;margin-bottom:4px;font-size:12px;font-family:-apple-system,system-ui}}
.tag{{background:#e9e6dd;color:#5a5343;padding:2px 8px;border-radius:99px;font-weight:600}}
@media(prefers-color-scheme:dark){{.tag{{background:#33302a;color:#d8cdb8}}}}
.when{{opacity:.45}}
.doc h1{{font-size:22px;margin:.3em 0 .4em}}
.doc h2{{font-size:18px;margin:1em 0 .3em;font-family:-apple-system,system-ui;font-weight:700}}
.doc p{{margin:.5em 0}}
.doc ul{{margin:.5em 0;padding-left:1.3em}}
.doc blockquote{{margin:.6em 0;padding-left:14px;border-left:3px solid #cbb;color:#666;font-style:italic}}
button{{font:15px -apple-system,system-ui;background:none;border:1px solid #ccc;border-radius:10px;padding:8px 14px;color:inherit;margin-top:8px}}
.empty{{opacity:.5;text-align:center;padding:40px 0}}
</style></head><body>
<header><h1 class="top">✍️ Черновики</h1><span class="count">{n} черновик(ов)</span></header>
<a class="dl" href="/export.md" download="chernoviki.md">⬇︎ Скачать всё одним .md</a>
{body}
<script>
// синхронизируем часы Freewrite с этого телефона (у него точное время)
try{{fetch('/settime?ts='+Date.now()).then(r=>{{if(r.ok){{var c=document.querySelector('.count');if(c)c.textContent+=' · ⌚ часы выставлены';}}}}).catch(()=>{{}});}}catch(e){{}}
function cp(b){{var t=b.closest('article').querySelector('.src').value;
navigator.clipboard.writeText(t).then(()=>{{b.innerText='Скопировано ✓';setTimeout(()=>b.innerText='Скопировать markdown',1500)}})}}
</script></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p == "/settime":
            # синк часов с телефона (у него точное время по сотовой): ?ts=<epoch-ms>
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            ts = (qs.get("ts", [""])[0] or "").strip()
            ok = False
            if ts.isdigit():
                secs = int(ts) // 1000
                # здравый диапазон (не мусор): 2024-01-01 .. 2035
                if 1704067200 < secs < 2050000000:
                    try:
                        subprocess.run(["date", "-s", "@%d" % secs], capture_output=True, timeout=8)
                        subprocess.run(["hwclock", "-w"], capture_output=True, timeout=8)
                        subprocess.run(["/usr/local/bin/hronolit-tick.sh"], capture_output=True, timeout=8)
                        ok = True
                    except Exception:
                        ok = False
            self._send(200 if ok else 400, "text/plain; charset=utf-8", b"ok" if ok else b"bad")
            return
        if p == "/apple-touch-icon.png":
            try:
                with open(ICON, "rb") as f:
                    self._send(200, "image/png", f.read())
            except Exception:
                self._send(404, "text/plain; charset=utf-8", b"no icon")
            return
        ds = drafts()
        if p == "/export.md":
            self._send(200, "text/markdown; charset=utf-8", md_all(ds).encode("utf-8"))
        elif p in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", page(ds).encode("utf-8"))
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    http.server.HTTPServer(("0.0.0.0", PORT), H).serve_forever()
