#!/bin/sh
# Freewrite RTC без батарейки → при каждом включении часы сбрасываются в 2019.
# Этот агент на Маке при каждом запуске: если устройство подключено (en8/USB) —
# выставляет ему точное время с Мака и обновляет кадр Хронолита.
HOST=192.168.99.190
KEY="$HOME/.ssh/freewrite_ed25519"

ping -c1 -t2 "$HOST" >/dev/null 2>&1 || exit 0   # не подключено — тихо выходим

NOW="$(date '+%Y-%m-%d %H:%M:%S')"
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 \
    -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$HOME/.ssh/known_hosts" \
    root@"$HOST" \
    "date -s '$NOW' >/dev/null 2>&1; hwclock -w 2>/dev/null; /usr/local/bin/hronolit-tick.sh 2>/dev/null" \
    >/dev/null 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') synced $HOST"
