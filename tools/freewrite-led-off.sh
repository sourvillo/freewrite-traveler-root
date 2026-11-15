#!/bin/sh
# Гасим RGB-лампу корпуса (красный светодиод у кнопки питания) — по просьбе Ивана.
# Короткий цикл (~24с) на случай, если что-то зажигает лампу во время загрузки.
end=$(( $(cut -d. -f1 /proc/uptime) + 24 ))
while [ "$(cut -d. -f1 /proc/uptime)" -lt "$end" ]; do
  for n in APA APA-R APA-G APA-B; do
    echo none > /sys/class/leds/$n/trigger 2>/dev/null
    echo 0 > /sys/class/leds/$n/brightness 2>/dev/null
  done
  sleep 2
done
