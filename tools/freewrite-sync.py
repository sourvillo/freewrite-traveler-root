#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Freewrite home-sync agent (сторона Мака). launchd раз в минуту.
Находит устройство (USB-гаджет ИЛИ домашний WiFi по MAC) и, если доступно:
  1) выставляет время + TZ Москва (RTC без батарейки),
  2) тянет черновики из БД `document` → .md в AI-Brain и Obsidian (дедуп).
Работает и по проводу, и по воздуху. Только stdlib.
"""
import json
import subprocess
import re
import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from freewrite_format import to_markdown

USB_IP = "192.168.99.190"          # USB-гаджет (стабильный)
MAC = "18:fe:34:ce:0a:5c"          # wlan0 — для поиска в LAN при смене DHCP
KEY = str(Path.home() / ".ssh/freewrite_ed25519")
KNOWN = str(Path.home() / ".ssh/known_hosts")
AIBRAIN = Path.home() / "Documents/AI-Brain/freewrite_drafts"
OBSIDIAN = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Freewrite"
# Режимы = физический переключатель папок A/B/C на устройстве. Поменять маппинг — здесь:
MODES = {1: "Заметки", 2: "Пост", 3: "Дневник"}
STATE = Path.home() / "freewrite-firmware/sync/draftsync.state.json"
IPCACHE = Path.home() / "freewrite-firmware/sync/device_ip"   # последний WiFi-адрес
FOLDER = {1: "a", 2: "b", 3: "c"}


def dests_for(folder_id):
    """AI-Brain (плоско, для конвейера) + Obsidian по под-папке режима."""
    return [AIBRAIN, OBSIDIAN / MODES.get(folder_id, "Заметки")]


def ping(ip):
    return subprocess.run(["ping", "-c1", "-t1", ip], capture_output=True).returncode == 0


def norm_mac(s):
    try:
        return ":".join(str(int(x, 16)) for x in s.split(":"))
    except Exception:
        return s.lower()


def arp_ip():
    try:
        out = subprocess.run(["arp", "-an"], capture_output=True, text=True, timeout=5).stdout
        target = norm_mac(MAC)
        for ln in out.splitlines():
            m = re.search(r"\(([\d.]+)\) at ([0-9a-fA-F:]+)", ln)
            if m and norm_mac(m.group(2)) == target:
                return m.group(1)
    except Exception:
        pass
    return None


def find_host():
    if ping(USB_IP):                       # провод — быстрый и стабильный
        return USB_IP
    try:                                   # кэш WiFi-адреса
        c = IPCACHE.read_text().strip()
        if c and ping(c):
            return c
    except Exception:
        pass
    ip = arp_ip()                          # поиск в LAN по MAC
    if ip and ping(ip):
        try:
            IPCACHE.write_text(ip)
        except Exception:
            pass
        return ip
    return None


def ssh(host, cmd, inp=None, timeout=25):
    try:
        return subprocess.run(
            ["ssh", "-i", KEY, "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
             "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={KNOWN}",
             f"root@{host}", cmd],
            input=inp, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        class R:
            stdout = ""
            stderr = str(e)
            returncode = 1
        return R()


def set_time(host):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ssh(host,
        "[ -f /usr/share/zoneinfo/Europe/Moscow ] && ln -sf /usr/share/zoneinfo/Europe/Moscow /etc/localtime; "
        f"date -s '{now}' >/dev/null 2>&1; hwclock -w 2>/dev/null; "
        "/usr/local/bin/hronolit-tick.sh 2>/dev/null; true")


def get_drafts(host):
    q = ('SELECT json_agg(row_to_json(t)) FROM (SELECT id,uuid,folder_id,title,body,'
         '"createdAt","updatedAt" FROM document WHERE length(btrim(body))>0 ORDER BY "updatedAt") t;')
    r = ssh(host, "su - postgres -c 'psql -d freewrite -tA'", inp=q)
    out = (r.stdout or "").strip()
    if not out:
        return []
    try:
        return json.loads(out) or []
    except Exception:
        return []


def slug(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = re.sub(r'[/\\:*?"<>|]', "", s)
    return s[:50].strip() or "untitled"


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def md_for(d):
    folder = FOLDER.get(d.get("folder_id"), "?")
    mode = MODES.get(d.get("folder_id"), "Заметки")
    fm = ("---\n"
          f"title: {slug(d.get('title'))}\n"
          "source: Freewrite Traveler\n"
          f"mode: {mode}\n"
          f"folder: {folder}\n"
          f"created: {d.get('createdAt', '')}\n"
          f"updated: {d.get('updatedAt', '')}\n"
          "---\n\n")
    return fm + to_markdown(d.get("body") or "")


def main():
    host = find_host()
    if not host:
        return
    # на проводе — освежаем кэш WiFi-адреса для будущего беспроводного синка
    if host == USB_IP:
        r = ssh(USB_IP, "ip -4 addr show wlan0 2>/dev/null | grep -oE 'inet [0-9.]+' | awk '{print $2}'")
        wip = (r.stdout or "").strip()
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", wip):
            try:
                IPCACHE.write_text(wip)
            except Exception:
                pass
    set_time(host)
    drafts = get_drafts(host)
    if not drafts:
        return
    st = load_state()
    changed = 0
    for d in drafts:
        u = d.get("uuid")
        if not u:
            continue
        rec = st.get(u, {})
        fname = rec.get("file") or f"{slug(d.get('title'))} — {u[:8]}.md"
        if rec.get("file") and rec.get("updated") == d.get("updatedAt"):
            continue
        content = md_for(d)
        for dest in dests_for(d.get("folder_id")):
            try:
                dest.mkdir(parents=True, exist_ok=True)
                (dest / fname).write_text(content, encoding="utf-8")
            except Exception as e:
                print(f"{datetime.datetime.now():%H:%M:%S} dest fail {dest}: {e}", file=sys.stderr)
        st[u] = {"file": fname, "updated": d.get("updatedAt")}
        changed += 1
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=0))
    # Отметить на устройстве, что эти черновики уже на Маке → в статус-баре
    # покажется «Synced to your Mac» (модель document.lastSynced смотрит uploaded).
    # Postbox мёртв, штатный аплоад отключён — метку ставим мы. COALESCE держит
    # первое время синка стабильным. WHERE uuid IN — один UPDATE на весь прогон.
    if st:
        uuids = ",".join("'" + str(u).replace("'", "") + "'" for u in st.keys())
        mark = ('UPDATE document SET uploaded=true, '
                f'"uploadedAt"=COALESCE("uploadedAt", now()) WHERE uuid IN ({uuids});')
        ssh(host, "su - postgres -c 'psql -d freewrite -tA'", inp=mark)
    if changed:
        print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} [{host}] synced {changed} draft(s)")


if __name__ == "__main__":
    main()
