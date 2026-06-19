#!/bin/sh
# connsys-up.sh - power on the MediaTek connsys chip and bring wlan0 into being.
# Run on the phone as root. Assumes you've already harvested the firmware into
# /lib/firmware (see docs/wifi.md). This mirrors what runs at boot on my device.
set +e
HERE="$(cd "$(dirname "$0")/.." && pwd)"

# Build the patched openmttools if they're not built yet (native musl build).
if [ ! -x /tmp/mtinit ] || [ ! -x /tmp/mtdaemon ]; then
    echo "building mtinit/mtdaemon..."
    cc -O2 -o /tmp/mtinit   "$HERE/connsys/mtinit.c"   || exit 1
    cc -O2 -o /tmp/mtdaemon "$HERE/connsys/mtdaemon.c" || exit 1
fi

# The kernel reads WMT.cfg; the SOC settings live in WMT_SOC.cfg, so make them
# the same. (mtdaemon also points the kernel at WMT_SOC.cfg over an ioctl, but
# copying the file matches the stock flow and is one less thing to get wrong.)
cp /lib/firmware/WMT_SOC.cfg /lib/firmware/WMT.cfg 2>/dev/null

# mtinit probes the SOC (reports chip 0x6768) and makes the kernel create
# /dev/stpwmt, /dev/wmtWifi and /dev/stpbt.
/tmp/mtinit
[ -e /dev/wmtWifi ] || { echo "no /dev/wmtWifi - mtinit didn't take, check dmesg"; exit 1; }
sleep 1

# mtdaemon downloads the firmware to the chip and powers it on. Keep it running.
setsid /tmp/mtdaemon -p /lib/firmware >/var/log/mtdaemon.log 2>&1 &
sleep 7

# function-on WiFi -> creates wlan0
echo 1 > /dev/wmtWifi
sleep 5
ip link set wlan0 up

ip link show wlan0 >/dev/null 2>&1 \
    && echo "wlan0 is up - now run setup-wifi.sh" \
    || echo "no wlan0 yet - check 'tail /var/log/mtdaemon.log' and 'dmesg | tail'"
