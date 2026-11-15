#!/bin/sh
# Опустить точку, вернуть wlan0 в NetworkManager (для домашнего WiFi).
pkill -f 'dnsmasq.*wlan0' 2>/dev/null
pkill -x hostapd 2>/dev/null
ip addr flush dev wlan0 2>/dev/null
# вернуть wpa_supplicant (ap-up его глушил) — иначе NM не поднимет клиентский WiFi
systemctl start wpa_supplicant.service 2>/dev/null
nmcli device set wlan0 managed yes 2>/dev/null
sleep 2
# подключить домашнюю сеть автоподключаемым профилем (имя не хардкодим)
nmcli device connect wlan0 2>/dev/null
echo "wlan0 вернулся в NM"
