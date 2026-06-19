#!/usr/bin/env python3
# audio-router.py - automatic audio routing for the A31.
#
# The mt6358 codec doesn't switch outputs on its own. This watches the headphone
# jack (ACCDET, exposed as a switch on /dev/input/event1) and flips the routing
# between the loudspeaker (via the SMA1303 amp) and the headphones (analog DAC)
# whenever you plug or unplug. It also re-reads the real jack state every 3s, so
# the route is correct even if it missed an event. Run it as a daemon.
# See docs/audio.md.
import os, struct, select, subprocess, fcntl

EVDEV = "/dev/input/event1"   # ACCDET (headset detect)
SZ = 24                       # sizeof(struct input_event) on this arch
EV_SW = 0x05
SW_BITS = (2, 4, 6)           # SW_HEADPHONE, SW_MICROPHONE, SW_LINEOUT

def amix(args):
    subprocess.run(["amixer", "-c0"] + args,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# the four mixer cells that wire the playback streams (DL) into I2S1 (-> amp)
I2S1_ROUTE = ("I2S1_CH1 DL1_CH1", "I2S1_CH2 DL1_CH2",
              "I2S1_CH1 DL2_CH1", "I2S1_CH2 DL2_CH2")

def route_speaker():
    amix(["sset", "HPL Mux", "Open"]); amix(["sset", "HPR Mux", "Open"])
    for c in I2S1_ROUTE:
        amix(["cset", "name=" + c, "on"])
    amix(["cset", "name=Ext_Speaker_Amp", "1"])
    amix(["cset", "name=Force AMP Power Down", "0"])
    amix(["cset", "name=Power Up(1:Up_0:Down)", "1"])
    amix(["sset", "Speaker Mute Switch(1:muted_0:un)", "0"])
    amix(["sset", "Speaker", "150"])

def route_headphones():
    # cut the speaker hard first (route off + amp down + mute)
    for c in I2S1_ROUTE:
        amix(["cset", "name=" + c, "off"])
    amix(["cset", "name=Force AMP Power Down", "1"])
    amix(["cset", "name=Power Up(1:Up_0:Down)", "0"])
    amix(["sset", "Speaker Mute Switch(1:muted_0:un)", "1"])
    amix(["cset", "name=Ext_Speaker_Amp", "0"])
    # then bring the headphone path up: DL -> analog DAC (ADDA) -> HP
    amix(["cset", "name=ADDA_DL_CH1 DL1_CH1", "1"])
    amix(["cset", "name=ADDA_DL_CH2 DL1_CH2", "1"])
    amix(["sset", "HPL Mux", "Audio Playback"]); amix(["sset", "HPR Mux", "Audio Playback"])
    amix(["sset", "Headset_PGAL_GAIN", "0Db"]);  amix(["sset", "Headset_PGAR_GAIN", "0Db"])

def setup_mic():
    amix(["sset", "PGA L Mux", "AIN0"]); amix(["sset", "PGA R Mux", "AIN0"])
    amix(["sset", "ADC L Mux", "Left Preamplifier"])
    amix(["sset", "ADC R Mux", "Right Preamplifier"])
    amix(["sset", "Audio_PGA1_Setting", "24Db"]); amix(["sset", "Audio_PGA2_Setting", "24Db"])
    amix(["cset", "name=UL1_CH1 ADDA_UL_CH1", "1"]); amix(["cset", "name=UL1_CH2 ADDA_UL_CH2", "1"])

EVIOCGSW = (2 << 30) | (ord('E') << 8) | 0x1b | (8 << 16)
def jack_present(fd):
    buf = bytearray(8)
    try:
        fcntl.ioctl(fd, EVIOCGSW, buf, True)
        sw = int.from_bytes(buf, "little")
        return bool(sw & sum(1 << b for b in SW_BITS))
    except Exception:
        return None

def log(m):
    print("[audio-router] " + m, flush=True)

cur = None  # current route: True = headphones, False = speaker
def apply(hp):
    global cur
    if hp == cur:
        return
    cur = hp
    if hp:
        route_headphones(); log("-> headphones")
    else:
        route_speaker();   log("-> speaker")

def main():
    setup_mic()
    fd = os.open(EVDEV, os.O_RDONLY)
    apply(bool(jack_present(fd)))
    log("running (re-checks every 3s + on events)")
    while True:
        r, _, _ = select.select([fd], [], [], 3.0)
        if r:
            try:
                d = os.read(fd, SZ * 16)
            except Exception:
                d = b""
            for i in range(0, len(d) - SZ + 1, SZ):
                _, _, typ, code, val = struct.unpack_from("<qqHHi", d, i)
                if typ == EV_SW and code in SW_BITS:
                    apply(bool(val))
        else:
            st = jack_present(fd)
            if st is not None:
                apply(st)

if __name__ == "__main__":
    main()
