#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Хронолит для Freewrite Traveler — заставка e-ink 1024×758.

Переиспользует корпус и логику выбора цитаты из author-clock/rpi/clock.py
(exact HH:MM → approximate ±7мин → period → fallback), но рисует под экран
Freewrite и сохраняет JPEG, готовый лечь в слот suspend-заставки устройства.

    python3 render_freewrite.py                 # текущее время → out/hronolit.jpg
    python3 render_freewrite.py --at 21:40       # конкретное время (отладка)
    python3 render_freewrite.py --at 00:00 --out out/midnight.jpg
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
CLOCK_DIR = Path.home() / "ivan_intake_station_v0" / "author-clock" / "rpi"
sys.path.insert(0, str(CLOCK_DIR))
import clock  # noqa: E402  — корпус + выбор цитаты + текстовые хелперы

# ── Геометрия экрана Freewrite Traveler ──────────────────────────────────────
W, H = 1024, 758
MARGIN = 88
SIG_ROOM = 132                      # место снизу под подпись автор/произведение

FONTS = Path(clock.FONT_DIR)        # author-clock/rpi/fonts (PT Serif с кириллицей)
REG, BOLD, ITAL = (str(FONTS / f) for f in
                   ("PTSerif-Regular.ttf", "PTSerif-Bold.ttf", "PTSerif-Italic.ttf"))


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _lw(d, words, f_reg, f_bold):
    """Ширина строки из токенов (каждое слово своим шрифтом, пробел где нужен)."""
    x = 0.0
    sp = d.textlength(" ", font=f_reg)
    for i, (w, is_ph) in enumerate(words):
        if i and w[:1] not in ".,;:!?…»)":
            x += sp
        x += d.textlength(w, font=(f_bold if is_ph else f_reg))
    return x


def layout(d, tokens, f_reg, f_bold, max_w):
    lines, cur = [], []
    for tok in tokens:
        trial = cur + [tok]
        if _lw(d, trial, f_reg, f_bold) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = [tok]
    if cur:
        lines.append(cur)
    return lines


def render(q, now, match_type):
    img = Image.new("L", (W, H), 255)          # белый фон e-ink
    d = ImageDraw.Draw(img)

    quote = q["quote"]
    phrase = clock.resolve_phrase(quote, q.get("time_phrase", ""))
    if not clock.is_clock_phrase(phrase):       # жирним ТОЛЬКО реальное показание часов
        phrase = ""
    segments = [s.strip() for s in re.split(r"\s*/\s*", quote) if s.strip()]

    max_w = W - 2 * MARGIN
    avail_h = H - 2 * MARGIN - SIG_ROOM

    size = 60
    for size in (60, 54, 49, 44, 40, 36, 32, 28, 25):
        f_reg, f_bold = font(REG, size), font(BOLD, size)
        lines = []
        for seg in segments:
            lines += layout(d, clock.tokenize(seg, phrase), f_reg, f_bold, max_w)
        line_h = int(size * 1.42)
        if len(lines) * line_h <= avail_h:
            break

    block_h = len(lines) * line_h
    y = max(MARGIN, (H - SIG_ROOM - block_h) // 2)
    space = d.textlength(" ", font=f_reg)
    for ln in lines:
        x = MARGIN
        for i, (w, is_ph) in enumerate(ln):
            if i and w[:1] not in ".,;:!?…»)":
                x += space
            fnt = f_bold if is_ph else f_reg
            d.text((x, y), w, font=fnt, fill=0)
            ww = d.textlength(w, font=fnt)
            if is_ph:                                   # тонкое подчёркивание фразы времени
                uy = y + int(size * 1.06)
                d.line((x, uy, x + ww, uy), fill=0, width=2)
            x += ww
        y += line_h

    # ── подпись: автор / произведение ───────────────────────────────────────
    by = H - SIG_ROOM + 12
    f_auth, f_work = font(ITAL, 31), font(REG, 25)
    d.line((MARGIN, by - 18, MARGIN + 96, by - 18), fill=0, width=2)
    d.text((MARGIN, by), clock.clean_display(q["author"]), font=f_auth, fill=0)

    title = clock.clean_display(q.get("work", ""))
    title = re.sub(r"\s*\((?:ок\.?\s*)?\d{3,4}(?:\s*г\.?)?\)", "", title).strip(" ,;")
    yr = f", {q['year']}" if q.get("year") else ""
    big_time = not phrase
    time_room = 210 if big_time else 96
    maxw = W - 2 * MARGIN - time_room
    disp = clock.clean_display(title + yr)
    if d.textlength(disp, font=f_work) > maxw:
        while title and d.textlength(title + "…" + yr, font=f_work) > maxw:
            title = title[:-1]
        disp = clock.clean_display(title.rstrip(" ,;(«") + "…" + yr)
    d.text((MARGIN, by + 42), disp, font=f_work, fill=0)

    # ── цифровое время ──────────────────────────────────────────────────────
    tstr = now.strftime("%H:%M")
    if big_time:                                    # нет показания часов в тексте → крупно
        f_big = font(REG, 72)
        tw = d.textlength(tstr, font=f_big)
        d.text((W - MARGIN - tw, by - 4), tstr, font=f_big, fill=0)
    else:                                           # показание уже в цитате → скромно в углу
        f_time = font(REG, 25)
        tw = d.textlength(tstr, font=f_time)
        d.text((W - MARGIN - tw, H - 62), tstr, font=f_time, fill=0)

    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", help="время HH:MM (по умолчанию — сейчас)")
    ap.add_argument("--mode", default="all")
    ap.add_argument("--out", default=str(HERE / "out" / "hronolit.jpg"))
    a = ap.parse_args()

    now = dt.datetime.now()
    if a.at:
        h, m = map(int, a.at.split(":"))
        now = now.replace(hour=h, minute=m, second=0)

    quotes = clock.load_quotes()
    q, mt = clock.select_quote(quotes, now, mode=a.mode, history={"shown": {}})
    if not q:
        print("нет подходящей цитаты"); return

    img = render(q, now, mt)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "JPEG", quality=92)
    print(f"{now:%H:%M} [{mt}] «{q['quote'][:56]}…» — {q['author']} → {out}")


if __name__ == "__main__":
    main()
