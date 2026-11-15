# -*- coding: utf-8 -*-
"""«Иван-разметка» → markdown → HTML. Пишешь почти без синтаксиса:
- `!` в начале строки = большой заголовок, `!!` = подзаголовок;
  без меток вовсе — авто: первая строка = заголовок, короткая одинокая = подзаголовок;
- пустая строка = новый абзац; `- ` = список; `> ` = цитата;
- `..жирное..` и `//курсив//` — как на Freewrite.
Используется и синком (Мак, .md), и веб-экспортом (устройство, превью)."""
import re
import html as _html

_HEAD_MAXLEN = 55
_HEAD_STOP = set(".!?…»\":;,")


def _inline(s):
    s = re.sub(r"\.\.(.+?)\.\.", r"**\1**", s)      # ..жирное..
    s = re.sub(r"//(.+?)//", r"*\1*", s)            # //курсив//
    return s


def to_markdown(raw):
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    # ! в начале строки = большой заголовок, !! = подзаголовок. Если такие метки в тексте
    # есть — Иван размечает сам, авто-угадайку заголовков отключаем.
    marked = any(l.lstrip().startswith("!") for l in lines)
    out, i, n = [], 0, len(lines)
    while i < n and not lines[i].strip():
        i += 1
    if i < n and not marked:                        # авто: первая строка → H1
        out += ["# " + _inline(lines[i].strip()), ""]
        i += 1
    while i < n:
        s = lines[i].strip()
        prev_blank = (i == 0) or (not lines[i - 1].strip())
        next_blank = (i + 1 >= n) or (not lines[i + 1].strip())
        if not s:
            out.append("")
        elif s.startswith("!!"):               # !! подзаголовок
            if out and out[-1] != "":
                out.append("")
            out += ["## " + _inline(s[2:].strip()), ""]
        elif s.startswith("!"):                # ! большой заголовок
            if out and out[-1] != "":
                out.append("")
            out += ["# " + _inline(s[1:].strip()), ""]
        elif re.match(r"^[-—–]\s+", s):             # список
            out.append("- " + _inline(re.sub(r"^[-—–]\s+", "", s)))
        elif s.startswith(">"):                     # цитата
            out.append("> " + _inline(s.lstrip("> ").strip()))
        elif not marked and prev_blank and next_blank and len(s) <= _HEAD_MAXLEN and s[-1] not in _HEAD_STOP:
            out += ["## " + _inline(s), ""]         # авто: короткая одинокая строка → подзаголовок
        else:
            out.append(_inline(s))
        i += 1
    md = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return md + "\n"


def _inline_html(s):
    s = _html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<em>\1</em>", s)
    return s


def md_to_html(md):
    blocks = re.split(r"\n\s*\n", (md or "").strip())
    out = []
    for b in blocks:
        bl = b.strip()
        if not bl:
            continue
        if bl.startswith("# "):
            out.append("<h1>" + _inline_html(bl[2:].strip()) + "</h1>")
        elif bl.startswith("## "):
            out.append("<h2>" + _inline_html(bl[3:].strip()) + "</h2>")
        elif all(l.strip().startswith("- ") for l in bl.split("\n") if l.strip()):
            items = "".join("<li>" + _inline_html(l.strip()[2:]) + "</li>"
                            for l in bl.split("\n") if l.strip())
            out.append("<ul>" + items + "</ul>")
        elif bl.startswith(">"):
            q = " ".join(l.lstrip("> ").strip() for l in bl.split("\n"))
            out.append("<blockquote>" + _inline_html(q) + "</blockquote>")
        else:
            out.append("<p>" + _inline_html(bl.replace("\n", " ")) + "</p>")
    return "\n".join(out)
