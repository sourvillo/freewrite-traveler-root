#!/bin/sh
# Поднять точку доступа Freewrite (hostapd + dnsmasq). Отдаёт wlan0 из-под NM.
nmcli device disconnect wlan0 2>/dev/null
nmcli device set wlan0 managed no 2>/dev/null
sleep 1
# ⚠️ глобальный wpa_supplicant от NM (/sbin/wpa_supplicant -u -s, БЕЗ 'wlan0' в cmdline)
# дерётся с hostapd за адаптер → глушим ПО-НАСТОЯЩЕМУ (старый паттерн его не ловил):
systemctl stop wpa_supplicant.service 2>/dev/null
pkill -x wpa_supplicant 2>/dev/null
sleep 1
ip link set wlan0 down 2>/dev/null; ip link set wlan0 up
ip addr flush dev wlan0
ip addr add 10.42.0.1/24 dev wlan0
pkill hostapd 2>/dev/null; sleep 1
hostapd -B /etc/freewrite/hostapd.conf
sleep 2
pkill -f 'dnsmasq.*wlan0' 2>/dev/null
dnsmasq --interface=wlan0 --bind-interfaces \
  --dhcp-range=10.42.0.10,10.42.0.100,255.255.255.0,12h \
  --dhcp-option=3,10.42.0.1 --dhcp-option=6,10.42.0.1 \
  --except-interface=lo --no-hosts --no-resolv 2>/dev/null
echo "AP: ssid=$(iw dev wlan0 info 2>/dev/null | awk '/ssid/{print $2}') ip=$(ip -4 addr show wlan0 | grep -oE 'inet [0-9.]+' | awk '{print $2}') hostapd=$(pgrep -c hostapd) dnsmasq=$(pgrep -fc 'dnsmasq.*wlan0')"
