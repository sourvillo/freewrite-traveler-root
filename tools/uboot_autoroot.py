#!/usr/bin/env python3
"""Авто-вход в root на Freewrite Traveler (i.MX6) через U-Boot по UART.
Ловит приглашение =>, сам вбивает команды, роняет в root-shell. Лог — в файл.
Запуск: python3 uboot_autoroot.py [--port /dev/cu.usbserial-XXXX] [--no-spam]
Метод стандартный и обратимый: i.MX6 умеет аварийную загрузку по USB (SDP)."""
import argparse
import re
import select
import sys
import time

import serial
import serial.tools.list_ports

PROMPT_RE = re.compile(rb"(=>|U-Boot>)\s*$")
BANNER_RE = re.compile(rb"U-Boot\s+20\d\d")
KERNEL_RE = re.compile(rb"(Starting kernel|Booting Linux|Linux version|Uncompressing Linux)")
SHELL_RE = re.compile(rb"(/ #|~ #|\n# |# $|root@)")


class Log:
    def __init__(self, path):
        self.f = open(path, "ab", buffering=0)
        self.path = path

    def say(self, text):
        line = f"[{time.strftime('%H:%M:%S')}] {text}\n"
        sys.stdout.write(line)
        sys.stdout.flush()
        self.f.write(line.encode())

    def raw(self, data):
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        self.f.write(data)

    def close(self):
        self.f.close()


def find_port(preferred=None):
    if preferred:
        return preferred

    def score(p):
        blob = ((p.device or "") + " " + (p.description or "")).lower()
        s = sum(10 for kw in ("usbserial", "slab", "cp210", "ftdi", "ft232", "ch340", "uart") if kw in blob)
        return s + (5 if "/dev/cu." in (p.device or "") else 0)

    ranked = sorted(serial.tools.list_ports.comports(), key=score, reverse=True)
    if not ranked or score(ranked[0]) == 0:
        return None
    return ranked[0].device


def is_prompt(buf, extra):
    return bool(PROMPT_RE.search(buf) or (extra and extra.search(buf)))


def wait_prompt(ser, log, extra, timeout=4.0):
    end = time.time() + timeout
    buf = b""
    while time.time() < end:
        chunk = ser.read(1024)
        if chunk:
            log.raw(chunk)
            buf = (buf + chunk)[-400:]
            if is_prompt(buf, extra):
                return True
    return False


def interactive(ser, log):
    if not sys.stdin.isatty():
        log.say("stdin не терминал — держу порт и печатаю вывод. Выход: Ctrl-C.")
        try:
            while True:
                chunk = ser.read(4096)
                if chunk:
                    log.raw(chunk)
        except KeyboardInterrupt:
            return
        return
    log.say("Живой терминал. Печатай команды. Выход из моста: Ctrl-]")
    import termios
    import tty
    old = termios.tcgetattr(sys.stdin)
    try:
        tty.setraw(sys.stdin.fileno())
        while True:
            r, _, _ = select.select([sys.stdin, ser], [], [], 0.05)
            if ser in r:
                data = ser.read(4096)
                if data:
                    log.raw(data)
            if sys.stdin in r:
                ch = sys.stdin.buffer.read(1)
                if not ch or ch == b"\x1d":
                    break
                ser.write(ch)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)


def inject(ser, log, extra, boot_cmd):
    ser.write(b"\x03")
    time.sleep(0.15)
    ser.write(b"\r")
    time.sleep(0.2)
    ser.reset_input_buffer()
    # Точная "production"-загрузка, как её делает boot.scr в ветке else:
    # ядро zImage-traveler-production и dtb imx6sll-traveler.dtb лежат на
    # FAT-разделе mmc 0:3. Грузим их, строим штатные bootargs через mmcargs
    # (root=/dev/mmcblk1p4), дописываем init=/bin/sh — тогда systemd (и его
    # зависший app Freewrite) не запускается, и мы падаем прямо в root-shell.
    steps = [
        "mmc dev 0",
        "mmc rescan",
        "setenv mmcpart 3",
        "setenv image zImage-traveler-production",
        "setenv fdt_file imx6sll-traveler.dtb",
        "run loadimage",
        "run loadfdt",
        "run mmcargs",
        "setenv bootargs ${bootargs} init=/bin/sh",
    ]
    for cmd in steps:
        log.say(">>> " + cmd)
        ser.write(cmd.encode() + b"\r")
        if not wait_prompt(ser, log, extra, timeout=8):
            log.say("Не дождался приглашения — продолжаю дальше.")
        time.sleep(0.1)
    boot = "bootz ${loadaddr} - ${fdt_addr}"
    log.say(">>> " + boot)
    ser.write(boot.encode() + b"\r")
    log.say("Ядро пошло. Жду root-shell…")


def main():
    ap = argparse.ArgumentParser(description="Авто-root через U-Boot по UART (Freewrite/i.MX6).")
    ap.add_argument("--port", help="например /dev/cu.usbserial-XXXX; по умолчанию автопоиск")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--log", help="файл лога; по умолчанию boot_ГГГГММДД_ЧЧММСС.log")
    ap.add_argument("--prompt", help="доп. текст приглашения, если не '=>'")
    ap.add_argument("--boot", default="run mmcboot", help="команда загрузки ядра")
    ap.add_argument("--no-spam", action="store_true", help="не спамить клавишу (только замыкание)")
    args = ap.parse_args()

    port = find_port(args.port)
    if not port:
        print("Не нашёл UART-порт. Доступно:")
        for p in serial.tools.list_ports.comports():
            print("   ", p.device, "—", p.description)
        print("Запусти с  --port /dev/cu.ТВОЙ_ПОРТ")
        sys.exit(1)

    log = Log(args.log or time.strftime("boot_%Y%m%d_%H%M%S.log"))
    extra = re.compile(re.escape(args.prompt.encode()) + rb"\s*$") if args.prompt else None
    try:
        ser = serial.Serial(port, args.baud, timeout=0.05, write_timeout=2)
    except serial.SerialException as e:
        log.say("Не открыть порт %s: %s" % (port, e))
        log.say("Закрой другие мониторы (screen/cu/miniterm) и запусти снова.")
        sys.exit(1)

    log.say("Порт %s @ %d. Лог: %s" % (port, args.baud, log.path))
    log.say("Готов. Включай устройство. Если U-Boot без задержки — сделай замыкание под Kingston.")
    if not args.no_spam:
        log.say("Спамлю клавишу для прерывания autoboot — возможно, замыкание не понадобится.")

    tail = b""
    state = "HUNT"
    last_spam = 0.0
    watch_start = 0.0
    try:
        while True:
            chunk = ser.read(4096)
            if chunk:
                log.raw(chunk)
                tail = (tail + chunk)[-400:]
                if state == "MISSED" and BANNER_RE.search(tail):
                    log.say("Новая загрузка — снова ловлю приглашение.")
                    state = "HUNT"
                    tail = b""

            if state == "HUNT":
                if is_prompt(tail, extra):
                    log.say(">>> Поймал приглашение U-Boot! Ввожу команды root.")
                    inject(ser, log, extra, args.boot)
                    tail = b""
                    watch_start = time.time()
                    state = "WATCH"
                elif KERNEL_RE.search(tail):
                    log.say("Ядро пошло грузиться — приглашение проскочили.")
                    log.say("Передёрни питание (+замыкание) — ловлю дальше.")
                    tail = b""
                    state = "MISSED"
                elif not args.no_spam and (time.time() - last_spam) > 0.03:
                    ser.write(b" ")
                    last_spam = time.time()

            elif state == "WATCH":
                if SHELL_RE.search(tail):
                    log.say("=" * 40)
                    log.say("  ГОТОВО — ты в root-shell (#). Мы внутри.")
                    log.say("=" * 40)
                    interactive(ser, log)
                    break
                elif time.time() - watch_start > 25:
                    log.say("Ядро должно было загрузиться — отдаю тебе живой терминал.")
                    log.say("Нажми Enter; увидишь '#' или '$' — ты root. Набери: id")
                    interactive(ser, log)
                    break
    except KeyboardInterrupt:
        log.say("Останов по Ctrl-C.")
    finally:
        try:
            ser.close()
        except Exception:
            pass
        log.close()


if __name__ == "__main__":
    main()
