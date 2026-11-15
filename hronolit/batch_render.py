#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пре-рендер Хронолита на весь день: 1440 кадров HHMM.jpg (по одному на минуту).
Заливается на устройство; on-device селектор кладёт нужный по текущему времени
в слот suspend-заставки. Работает офлайн, без облака.

    python3 batch_render.py            # рендер всех минут в ./frames/
    python3 batch_render.py --force    # перерисовать даже существующие
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_freewrite as R          # render() + модуль clock (корпус, выбор)

clock = R.clock
OUT = HERE / "frames"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    quotes = clock.load_quotes()
    base = dt.datetime(2026, 1, 1, 0, 0, 0)      # дата не важна, нужны только HH:MM

    done = skipped = 0
    for m in range(1440):
        now = base + dt.timedelta(minutes=m)
        hhmm = now.strftime("%H%M")
        path = OUT / f"{hhmm}.jpg"
        if path.exists() and not a.force:
            skipped += 1
            continue
        q, mt = clock.select_quote(quotes, now, mode="all", history={"shown": {}})
        if not q:
            continue
        img = R.render(q, now, mt)
        img.convert("RGB").save(path, "JPEG", quality=88)
        done += 1
        if done % 200 == 0:
            print(f"  …{done} нарисовано (сейчас {hhmm})", flush=True)

    total = len(list(OUT.glob("*.jpg")))
    size_mb = sum(f.stat().st_size for f in OUT.glob("*.jpg")) / 1e6
    print(f"готово: нарисовано {done}, пропущено {skipped}; "
          f"всего {total} кадров, {size_mb:.1f} МБ в {OUT}")


if __name__ == "__main__":
    main()
