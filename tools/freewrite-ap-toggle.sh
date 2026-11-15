#!/bin/sh
# Тумблер точки доступа «Freewrite»: hostapd поднят → выключить, иначе → включить.
# Печатает новое состояние (on/off) в stdout.
# ⚠️ finchley работает НЕ под root, а точке нужен root → эскалируемся через sudo
# (правило в /etc/sudoers.d/freewrite; при повторном заходе уже root — пропускаем).
if [ "$(id -u)" != "0" ]; then
  exec /usr/bin/sudo -n /usr/local/bin/freewrite-ap-toggle.sh "$@"
fi
if pgrep -x hostapd >/dev/null 2>&1; then
  /usr/local/bin/freewrite-ap-down.sh >/dev/null 2>&1
  echo "off"
else
  /usr/local/bin/freewrite-ap-up.sh >/dev/null 2>&1
  echo "on"
fi
