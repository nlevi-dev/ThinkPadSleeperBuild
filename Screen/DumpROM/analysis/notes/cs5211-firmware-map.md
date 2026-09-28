> **Historical investigation:** written before reviewing Levi’s solution. See the
> [solution retrospective](../SOLUTION.md) for corrections, the identified selector,
> and the missing firmware-integrity check. Candidate images are CPU experiments,
> not validated flash images. Paths below refer to this analysis directory.

# CS5211 firmware map

Reassessed on 2026-09-28: see [the evidence review](cs5211-reassessment-2026-09-28.md)
for global configuration paths, the timer ISR, and revised confidence levels.

This is a static-analysis map of `binaries/cs5211-8051-firmware.bin`, extracted
from the ThinkPadSleeperBuild serial-ROM dump. Firmware logical addresses below
map to physical serial-ROM offset `0x1000 + address`.

## Confirmed boot path

| Firmware address | Behaviour | Evidence |
| --- | --- | --- |
| `0x0000` | Reset vector: `LJMP 0x0130`. | Direct instruction. |
| `0x0130–0x0138` | Clears internal RAM `0x00–0x7f`; sets stack pointer to `0x3a`. | Direct instructions. |
| `0x0177–0x01bb` | Interprets a compact internal-RAM initialization stream at `0x0e1f`. | `MOVC` stream reader and handlers. |
| `0x01c0–0x0323` | Programs fixed CS5211 XDATA registers and copies firmware constants at `0x0110–0x011a`. | Direct `MOVX` writes. |
| `0x0266–0x0270` | Reads XDATA `0x00ca`, masks its low nibble, and shifts it left four bits into RAM `0x08`. | Direct instructions. |
| `0x045b–0x0524` | Uses RAM `0x08` as a table index; writes a 12-byte profile record to XDATA. | Direct `MOVC` and `MOVX` sequence. |

## GPIO-selected profile records

The profile index is:

```text
profile = XDATA[0x00ca] & 0x0f
profile_record = firmware[0x0010 + profile * 16]
```

All sixteen records are identical in this image:

```text
01 00 00 01 08 00 00 08 03 03 44 04 aa aa aa aa
```

The firmware consumes the first twelve bytes as follows:

| Profile byte | XDATA register written | Value in every profile |
| ---: | ---: | ---: |
| `+0` | `0x009f` | `0x01` |
| `+1` | `0x01dc` | `0x00` |
| `+2` | `0x01de` | `0x00` |
| `+3` | `0x01e1` | `0x01` with bit 3 cleared |
| `+4` | `0x01e2` | `0x08` with bit 3 set |
| `+5` | `0x01e3` | `0x00` |
| `+6` | `0x01e4` | `0x00` |
| `+7` | `0x01e7` | `0x08` |
| `+8` | `0x01ed` | `0x03` |
| `+9` | `0x01f2` | `0x03` |
| `+10` | `0x01f3` | `0x44` |
| `+11` | `0x01f4` | Full profile byte ORed with `(firmware[0x0122] & 0x0f) << 4` |

The XDATA register names and bit meanings remain unknown because the public
datasheet does not publish this register map. This record is the leading
candidate for LVDS format, data mapping, and timing configuration. It is a more
useful patch target than EDID for an 18/24-bit panel mismatch.

### Exact write semantics

These are direct instruction-level facts, independent of any guessed register
names. The byte locations are firmware addresses; add `0x1000` for the physical
serial-ROM address.

| Profile byte | Firmware operation | Resulting XDATA value in this ROM |
| ---: | --- | ---: |
| `+0` | write unchanged | `XDATA[0x009f] = 0x01` |
| `+1`, `+2` | write unchanged | `XDATA[0x01dc] = 0x00`; `XDATA[0x01de] = 0x00` |
| `+3` | `value & 0xf7` | `XDATA[0x01e1] = 0x01`; bit 3 is forcibly clear |
| `+4` | `value | 0x08` | `XDATA[0x01e2] = 0x08`; bit 3 is forcibly set |
| `+5`, `+6`, `+7` | write unchanged | `XDATA[0x01e3] = 0x00`; `XDATA[0x01e4] = 0x00`; `XDATA[0x01e7] = 0x08` |
| `+8`, `+9`, `+10` | write unchanged | `XDATA[0x01ed] = 0x03`; `XDATA[0x01f2] = 0x03`; `XDATA[0x01f3] = 0x44` |
| `+11` | `((firmware[0x0122] & 0x0f) << 4) | value` | `XDATA[0x01f4] = 0x04` |

For profile `n`, profile byte `p` is at firmware `0x0010 + 0x10*n + p`, or
physical serial-ROM `0x1010 + 0x10*n + p`. All sixteen copies should be kept
identical when changing a global output mode.

`0x009f` is also re-written with `0x01` by the later initialization routine at
firmware `0x0cf7`; the remaining profile registers have no later direct read or
write site identified outside the copy sequence. The setup loop can revisit
that sequence; this is not proof of a once-per-boot write.

## LVDS mapping diagnosis

The LTN141P4-L03 panel's own electrical specification defines its active data
lanes as follows for both odd and even pixels:

```text
lane 0: G0  R5 R4 R3 R2 R1 R0
lane 1: B1  B0 G5 G4 G3 G2 G1
lane 2: DE  VS HS B5 B4 B3 B2
```

This is the common three-lane, dual-pixel, 18-bit LVDS wire layout. It makes a
VESA/SPWG 24-bit transmitter and a JEIDA 24-bit transmitter behave differently
when the fourth data lane is absent:

| Transmitter mapping | Bits received by this 18-bit panel on lanes 0–2 | Result |
| --- | --- | --- |
| VESA/SPWG 24-bit | source `R5–R0`, `G5–G0`, `B5–B0` | The panel uses the *least-significant* six bits. Full-scale and zero remain plausible; intermediate shades are badly wrong. |
| JEIDA 24-bit | source `R7–R2`, `G7–G2`, `B7–B2` | The panel receives the intended six most-significant bits. The unused fourth lane carries the discarded low bits. |
| 18-bit mode | the three expected 6-bit components | Correct if port count and odd/even order also match. |

This predicts the reported symptoms: primary full-scale colours and white/black
work, while intermediate values show severe false colours or patterns. It is a
better fit than gamma correction.

The CS5211 datasheet calls the compatible 24-bit mapping OpenLDI and the other
SPWG. Their bit placements correspond to TI's JEIDA/Format 1 and VESA/Format 2.
Register names and bit assignments are absent from the public document.

The profile block is a candidate, but global configuration at ROM
`0x1110–0x1122` and literal register writes also configure the chip. The claim
that the selection must be in the profile block is withdrawn. JEIDA24 is
compatible at the bit-placement level; the actual fault and selector bit
remain unconfirmed.

## Internal-RAM initialization stream

The table at `0x0e1f` initializes RAM through the interpreter at `0x0177`.
The reproducible decoder is `scripts/decode_cs5211_boot_table.py`.

| RAM range | Initial values |
| --- | --- |
| `0x0b` | `fd` |
| `0x0c` | `90` |
| `0x0f` | `00` |
| `0x10` | `0a` |
| `0x13–0x15` | `00 00 00` |
| `0x16–0x20` | `ff fb f6 f1 ec e6 e2 dd d8 d3 00` |
| `0x25` | `00` |

The Timer 0 ISR at logical `0x0c48` uses this curve for complementary timer
reloads and alternates XDATA `0x00b3`. This is duty-cycle generation, plausibly
for brightness, rather than evidence of an RGB gamma table.

## Other code regions

| Firmware range | Current classification |
| --- | --- |
| `0x03a6–0x0646` | XDATA state polling, retry loops, profile application, and feature-dependent setup. |
| `0x0647–0x0a1f` | Multiword arithmetic helpers; not all numeric representations have been established. |
| `0x0a20–0x0c47` | Executed clock-ratio calculation: reads two BE24 values at `0x0549/0x054c` plus rate at `0x060a`, selects dividers at 25/50/100 thresholds, writes fixed-point value to `0x0564–0x0566`. Strongly consistent with DP Mvid/Nvid pixel-clock recovery. |
| `0x0cbc–0x0d2f` | Restores a fixed register set when the `0x01b4` marker changes. |
| `0x0d30–0x0d8c` | Brightness button polling; directions can be swapped by global ROM `0x1112` bit 5. |
| `0x0d8d–0x0dd9` | Power-button edge detection/toggle, enabled by global ROM `0x1112` bit 4. |
| `0x0dda–0x0e1e` | Delay argument preparation and busy wait. |
| `0x0e5c–0x0e83` | Delay/counter and timer-related helper code. |
| `0x0c48–0x0cbb` | Timer 0 duty-cycle ISR, reached through vector `0x000b`. |

## Evidence against a firmware RGB calibration path

The full-CPU follow-up is in [the execution report](cs5211-blackbox-2026-09-28.md),
including mutation, clock, button, recovery, and independent uCsim experiments.

No code path copying an identified RGB calibration table has been found. The
11-byte internal-RAM sequence has a verified timer use. Global constants and
the 12-byte profile both feed register writes.

This does not prove the CS5211 lacks image processing. Its advertised dithering,
gamma, and dynamic-backlight hardware may be configured through opaque XDATA
bits. Packed data, a hardware consumer, or an internal boot loader could escape
the byte scans and instruction paths reviewed here. Absence of a LUT is unproved.

## Safe conclusion

The firmware has a single, identical 16-profile LVDS configuration. EDID patching
does not alter it. Before changing unknown bytes, obtain a CS5211 serial-ROM
image known to drive a dual-channel 18-bit panel and diff its profile bytes
(`0x0010–0x010f`) and resulting XDATA writes against this image.
