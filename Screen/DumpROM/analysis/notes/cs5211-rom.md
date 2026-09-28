> **Historical investigation:** written before reviewing Levi’s solution. See the
> [solution retrospective](../SOLUTION.md) for corrections, the identified selector,
> and the missing firmware-integrity check. Candidate images are CPU experiments,
> not validated flash images. Paths below refer to this analysis directory.

# CS5211 serial-ROM dump

Source: `Screen/DumpROM/dump_CS5211.txt` from `nlevi-dev/ThinkPadSleeperBuild`.

Reassessed on 2026-09-28: see [the evidence review](cs5211-reassessment-2026-09-28.md).

## Layout

| Physical range | Size | Contents |
| --- | ---: | --- |
| `0x0000–0x07ff` | 2048 B | 16 identical EDID records |
| `0x0800–0x0fff` | 2048 B | configuration and blank/reserved space |
| `0x1000–0x1e83` | 3716 B | 8051 firmware |
| `0x1e84–0x1fff` | 380 B | erased (`0x00`) space |

The firmware begins with `02 01 30`: the 8051 reset vector `LJMP 0x0130`. Its logical address `0x0000` corresponds to physical ROM offset `0x1000`.

## EDID record

The 128-byte EDID data at offset `0x0000` is valid EDID 1.4:

- PNP ID: `CS_`; product ID: `0x5211`; serial: `1025`.
- Manufacture date: week 5 of 2013.
- Digital DisplayPort input; 8 bits per colour channel (`0xa5`).
- Display size: 53 × 30 cm.
- Native timing: 1920 × 1080.
- Text descriptor: `1920x1080`.

The CS5211 is an eDP-to-LVDS bridge. Its serial ROM is designed to carry both EDID and bridge configuration/firmware, so the dump is not only panel metadata.

## Ghidra projects

- `projects/cs5211-rom.gpr` views the full 8 KiB serial ROM as data.
- `projects/cs5211-8051.gpr` imports the extracted firmware as `8051:BE:16:default` and runs analysis.

Open `cs5211-8051`, then run `scripts/AnnotateCS5211.java` from Ghidra's Script Manager if its labels are not already present.

## Lookup-table and colour-adjustment assessment

The global configuration area is `0x0110–0x0122` in the extracted 8051 image, alongside sixteen profiles at `0x0010–0x010f`. During startup, the code at `0x02c2` loads global values with `MOVC` and writes them to CS5211 external-register addresses including `0x0602`, `0x0603`, and `0x01d0–0x01f9`.

Another structured area has four bytes at `0x0800`, followed by three identical 128-byte blocks at `0x0804`, `0x0884`, and `0x0904`. The earlier 124-byte segmentation was arbitrary. Every payload value is in the range `0x0`–`0xf`; its purpose remains unknown, including whether it participates in image processing.

No RGB calibration LUT has been identified. A scan for monotonic byte sequences cannot rule out packed, encoded, or hardware-loaded tables. The chip documentation advertises gamma correction, dithering, and backlight control without exposing their full register map. The small internal-RAM curve is used by the Timer 0 ISR for duty-cycle generation.

The four configuration pins select up to 16 panel profiles from one ROM image. That supports the interpretation of the 16 EDID records but does not identify the `0x0800` region. The reviewed EDID-patched ROM modifies only the EDID area.
