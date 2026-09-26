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
`0x01d0–0x01f9`.

The actionable per-panel configuration is a 16-record table at physical ROM
`0x1010–0x110f`. On startup, the firmware reads `XDATA[0x00ca] & 0x0f`, selects
one 16-byte record, and copies its first 12 bytes to CS5211 XDATA registers
`0x009f`, `0x01dc`, `0x01de`, `0x01e1–0x01e4`, `0x01e7`, `0x01ed`, and
`0x01f2–0x01f4`. All sixteen records are identical in the original image:

```text
01 00 00 01 08 00 00 08 03 03 44 04 aa aa aa aa
```

The public CS5211 documentation does not name those XDATA registers, but this
is the boot-only block that selects LVDS format, data mapping, and timing. See
[firmware-map.md](firmware-map.md) for the verified register writes and source
offsets.

## Colour and brightness

No RGB calibration lookup table appears in this ROM: there is no separately
stored per-channel, 16/64/256-entry curve copied to an RGB-sized register bank.
The CS5211 does support gamma, dithering, and backlight control, but those
features do not explain the observed colour artifacts after the EDID patch.

The replacement Samsung LTN141P4-L03 panel is a dual-pixel, 18-bit LVDS panel.
Its specification assigns its three data lanes as `G0 R5…R0`, `B1 B0 G5…G1`,
and `DE VS HS B5…B2` for each odd/even channel. A VESA/SPWG 24-bit transmitter
puts the source's low six component bits on those lanes, causing correct
black/full-scale colours and corrupt intermediate shades. JEIDA 24-bit puts
the high six bits there and is backward-compatible with the panel's 18-bit
wiring. The strongest current hypothesis is that the CS5211 is configured for
VESA/SPWG 24-bit output and needs JEIDA mapping and/or 18-bit mode.

`OpenLDI` describes the LVDS display-link family; VESA/SPWG and JEIDA are
alternate data mappings, not synonyms. TI's [LVDS mapping application note]
(https://www.ti.com/lit/an/snla014a/snla014a.pdf) documents why JEIDA 24-bit
works with an 18-bit receiver while VESA/SPWG 24-bit does not.

## Reproduce the analysis

```sh
python3 analyze_cs5211_rom.py dump_CS5211.txt
```

To make a controlled test image, modify one profile byte across all 16 records
without changing EDID or other firmware bytes:

```sh
python3 patch_cs5211_profile.py dump_CS5211.txt candidate.txt --set 0x0a=0x45
```

The expected original-ROM SHA-256 is:

```
a7a5b681eb62026afcb11232635fb68251f40ca0348f6b513913bc51bb4a2451
```
