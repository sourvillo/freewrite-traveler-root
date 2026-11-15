#!/bin/sh
# Boot-писатели, одна служба (WantedBy=sysinit → стартует рано):
# (1) во время загрузки листаем boot_full/boot_progress ~24с фиксированно (весь загрузочный экран);
# (2) в конце выбираем писателя на СЛЕДУЮЩУЮ загрузку.
# ⚠️ ОРИЕНТАЦИЯ (2026-07-11): boot-дисплей перещёлкнулся на 180° → ПОМЕНЯЛИ пулы:
#   baker-powerd (boot_full/progress) теперь ПЕРЕВОРАЧИВАЕТ → даём ПЕРЕВЁРНУТЫЙ пул (bootpool);
#   epdraw (firstboot/second) теперь как-есть → даём РОВНЫЙ пул (bootpool_up).
# (Если снова перевернётся — поменять BAKER<->EPDRAW обратно; значит флип недетерминирован.)
SH=/astrohaus/share/1024x758
BAKER=/astrohaus/share/bootpool        # boot_full/progress (baker-powerd) — перевёрнутый
EPDRAW=/astrohaus/share/bootpool       # firstboot/second (epdraw) — тоже перевёрнутый (метод исключения)
LIST="asimov austen cervantes christie dumas poe"

swap() {   # атомарная подмена boot_full/progress
  cp -f "$BAKER/$1.jpg" "$SH/.bf.tmp" 2>/dev/null && { chmod 0644 "$SH/.bf.tmp" 2>/dev/null; mv -f "$SH/.bf.tmp" "$SH/boot_full.jpg"; }
  cp -f "$BAKER/$1.jpg" "$SH/.bp.tmp" 2>/dev/null && { chmod 0644 "$SH/.bp.tmp" 2>/dev/null; mv -f "$SH/.bp.tmp" "$SH/boot_progress.jpg"; }
  logger -t freewrite-bootcycle "swap $1"
}

END=$(( $(cut -d. -f1 /proc/uptime) + 24 ))
while [ "$(cut -d. -f1 /proc/uptime)" -lt "$END" ]; do
  for w in $(echo "$LIST" | tr ' ' '\n' | shuf 2>/dev/null); do
    [ "$(cut -d. -f1 /proc/uptime)" -ge "$END" ] && break
    swap "$w"
    sleep 2
  done
done

# писатель на СЛЕДУЮЩУЮ загрузку
W=$(echo "$LIST" | tr ' ' '\n' | shuf 2>/dev/null | head -1); [ -z "$W" ] && W=dumas
cp -f "$BAKER/$W.jpg"  "$SH/boot_full.jpg"     2>/dev/null
cp -f "$BAKER/$W.jpg"  "$SH/boot_progress.jpg" 2>/dev/null
cp -f "$EPDRAW/$W.jpg" "$SH/firstboot.jpg"     2>/dev/null
cp -f "$EPDRAW/$W.jpg" "$SH/secondboot.jpg"    2>/dev/null
chown astrohaus:astrohaus "$SH"/firstboot.jpg "$SH"/boot_full.jpg "$SH"/boot_progress.jpg "$SH"/secondboot.jpg 2>/dev/null
chmod 0770 "$SH"/firstboot.jpg "$SH"/boot_full.jpg "$SH"/boot_progress.jpg "$SH"/secondboot.jpg 2>/dev/null
logger -t freewrite-bootcycle "next=$W"
