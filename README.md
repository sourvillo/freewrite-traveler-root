# Freewrite Traveler — Root Access & Custom Firmware

Full, reproducible documentation of getting persistent root on the
[Freewrite Traveler](https://getfreewrite.com/) (Astrohaus) — an e-ink
distraction-free typewriter that is an ordinary Debian-on-i.MX6 Linux box
underneath, locked from the outside.

**Read the writeup → [`index.html`](index.html)** (open it in a browser;
bilingual RU/EN, light/dark). It covers, in order: hardware & locks,
teardown, finding UART, the `init=/bin/sh` root technique, what didn't work
(USB-C, Secure Boot), the system map, what we changed and why, anti-brick
notes, and a disclaimer.

> Made by an owner, for an owner's own device. Freewrite® and Astrohaus®
> are trademarks of their respective holders; this project is neither
> affiliated with nor endorsed by them.

## What's here

```
index.html            the writeup (open directly, or serve via GitHub Pages)
docs/boot-logs/        a real UART capture of the exact moment root is gained
tools/                 scripts that run ON the device after root
  uboot_autoroot.py       drives the U-Boot interrupt + init=/bin/sh handoff over UART
  freewrite-httpd.py       tiny web server on the device: export drafts as Markdown over WiFi
  freewrite_format.py      the "Ivan-markup" → Markdown/HTML conversion it uses
  freewrite-ap-up.sh       bring up a local WiFi AP on the device (hostapd + dnsmasq)
  freewrite-ap-down.sh     tear it back down
  freewrite-ap-toggle.sh   toggle the AP from a hardware key
  hostapd.conf             AP config template (placeholder passphrase — change it)
  freewrite-bootcycle.*    systemd unit + script around boot-time behavior
  freewrite-led-off.*      systemd unit + script to silence an LED
  freewrite-sync.py        Mac-side: pulls drafts off the device's Postgres DB over SSH
  freewrite-timesync.sh    Mac-side: pushes correct time/TZ to the device (no RTC battery)
hronolit/               source for the "Chronolith" screensaver (a literary quote
                         naming the current hour, replacing the stock writer portraits)
  render_freewrite.py      renders one frame for a given time
  batch_render.py          batch-renders a day's worth of frames
```

## What's deliberately *not* here

- Astrohaus's own application source (the Electron app extracted from the
  device). Getting root on hardware you own is one thing; redistributing
  someone else's proprietary source is another — not done here.
- The stock writer-portrait screensavers and the `ginger.jpg` easter egg
  mentioned in the writeup. Both are named and described, but the actual
  image files are Astrohaus's artwork / a developer's candid photo, not
  ours to republish.

## Safety

This voids the warranty and can brick the device. No bootloader or kernel
is ever flashed (see "Anti-brick" in the writeup) — the technique only
overrides what the already-signed kernel is told to run, for one boot — but
it's still real risk on real hardware. Don't try it on a machine you're not
ready to lose.

## License

The write-up text is © the author; feel free to quote with attribution.
The scripts in `tools/` and `hronolit/` are MIT-licensed — see
[`LICENSE`](LICENSE).
