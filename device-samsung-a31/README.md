# device-samsung-a31

This folder is the postmarketOS device-package material for my Samsung Galaxy A31 (SM-A315G, MediaTek MT6768 / Helio P65). There was no existing pmaports port for any MT6768 Samsung when I started, so all of this is downstream and hand-built.

Two files live here:

- **`deviceinfo`** — the device definition: flash method, boot.img offsets, partition names, screen size. Every flash/boot value in it was confirmed by parsing the *real* boot.img off the phone, not guessed. It's a plain AOSP header-v2 image (base `0x40078000`, pagesize 2048, kernel `0x8000`, ramdisk `0x07c08000`, tags/dtb `0x0bc08000`), with **no** MediaTek `0x88168858` header, so don't set any `deviceinfo_bootimg_mtk_label_*`. Flashing is `heimdall-bootimg` (Samsung has no fastboot), kernel partition `BOOT`, system partition `USERDATA`.
- **`APKBUILD`** — the package for `linux-samsung-a31`, the downstream 4.14.186 kernel (Galaxy-MT6768 LineageOS fork, branch lineage-19.1, commit `48d7bfb`) with the handful of `prepare()` seds that actually make it compile and the connsys/touch fixes. Read the comments in it; they explain each one.

## How to actually build this

These two files aren't a standalone package you can `pmbootstrap build` from this repo. They're meant to be dropped into your local pmaports checkout:

```
pmaports/device/downstream/device-samsung-a31/   <- deviceinfo (+ the usual APKBUILD, modules-initfs, etc.)
pmaports/device/downstream/linux-samsung-a31/    <- this APKBUILD + the kernel config
```

The kernel APKBUILD expects a config file named **`config-samsung-a31.aarch64`** sitting next to it — and it's right here in this folder. That's the actual config off my running device (pulled from `/proc/config.gz`), the one that produces the kernel I'm using, so it's not a guess. It started life as the kernel tree's `arch/arm64/configs/a31_defconfig` with the important additions being

```
CONFIG_DEVTMPFS=y
CONFIG_DEVTMPFS_MOUNT=y
```

(without those, pmOS's init has no `/dev` and you get a very confusing early boot failure) plus a couple of disables. The reasoning behind the changes — why `COMPAT_VDSO`/`IKHEADERS` had to go, the touch and connsys bits — is in **[../docs/kernel.md](../docs/kernel.md)**, along with the build fixes that took me the longest to figure out.

For getting the result onto the phone (download mode, the 32 MB boot partition gotcha where the kernel has to be gzipped, the matched boot+root pairing), see **[../docs/flashing.md](../docs/flashing.md)**.

## One warning before you flash anything

`EFS` is `mmcblk0p3` and `sec_efs` is `mmcblk0p4`. Those hold your IMEI and modem calibration. **Never** write to them, never `dd` over them, don't include them in any Heimdall PIT operation. There's no recovering them if you nuke them, and a phone with a dead EFS won't talk to a cellular network again. The deviceinfo here only ever touches `BOOT` and `USERDATA`, which is deliberate.

If you've got a different MT6768 Samsung and some of these offsets are wrong for you, parse your own boot.img rather than trusting mine. The parser I used is in `../tools/`.
