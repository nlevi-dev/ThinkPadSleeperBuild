# CS5211 serial-ROM dump

`dump_CS5211.txt` is an 8 KiB, 16-byte-per-line hexadecimal dump from the
external serial ROM used with a Capstone CS5211 eDP-to-LVDS bridge. It contains
more than an EDID record.

## Layout

| ROM offset | Size | Contents |
| --- | ---: | --- |
| `0x0000–0x07ff` | 2 KiB | 16 identical 128-byte EDID records |
| `0x0800–0x0fff` | 2 KiB | bridge configuration data and reserved space |
| `0x1000–0x1e83` | 3716 B | CS5211's 8051 firmware |
| `0x1e84–0x1fff` | 380 B | zero-filled space |

The repeated EDID is deliberate. CS5211 selects one of 16 panel configurations
with its GPIO[3:0] pins, and each configuration has a 128-byte EDID slot. The
original dump uses the same record for every slot.

The original EDID has a valid checksum and identifies itself as PNP `CS_`,
product `0x5211`, serial `1025`, manufactured in week 5 of 2013. It advertises
a digital DisplayPort input and 1920×1080 timings at approximately 60 Hz and
50 Hz. `patch_cs5211.py` replaces all 16 copies and recalculates the checksum.

## Firmware

The firmware starts at ROM `0x1000`, mapped as logical 8051 address `0x0000`.
The first instruction, `02 01 30`, is `LJMP 0x0130`, the reset path. The code
at logical `0x02c2` loads compact constants at `0x0110–0x0122` with `MOVC` and
writes them to bridge register space, including `0x0602`, `0x0603`, and
`0x01d0–0x01f9`. This is the actionable panel/bridge configuration lookup area.

## Colour and brightness

No gamma or RGB calibration lookup table appears in this ROM: the firmware has
no 16-, 32-, 64-, 128-, or 256-entry monotonic byte sequence. The CS5211
supports backlight/brightness control and dithering, but this ROM does not
contain an RGB gain, white-point, or gamma table. The poor colour balance in
the CCFL-to-LED conversion is therefore unlikely to be correctable by patching
this ROM. Investigating the LED-strip spectrum, panel optics, and backlight
drive current is the more promising path.

## Reproduce the analysis

```sh
python3 analyze_cs5211_rom.py dump_CS5211.txt
```

The expected original-ROM SHA-256 is:

```
a7a5b681eb62026afcb11232635fb68251f40ca0348f6b513913bc51bb4a2451
```
