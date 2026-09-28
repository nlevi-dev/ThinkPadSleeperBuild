> **Historical investigation:** written before reviewing Levi’s solution. See the
> [solution retrospective](../SOLUTION.md) for corrections, the identified selector,
> and the missing firmware-integrity check. Candidate images are CPU experiments,
> not validated flash images. Paths below refer to this analysis directory.

# CS5211 reassessment — 2026-09-28

This review rechecks earlier assistant conclusions and the repository owner's
assumptions against raw ROM bytes, instruction execution, and vendor documents.
It supersedes the stronger claims in the earlier notes where they disagree.

Follow-up: [full-CPU black-box experiments](cs5211-blackbox-2026-09-28.md)
extend this review with 2,267 experiments and an independent uCsim cross-check.
They identify the clock calculation and further separate brightness/power
controls, without identifying the serializer's exact format bits.

## Evidence and limits

- Upstream reviewed: `nlevi-dev/ThinkPadSleeperBuild`, master `bad0c35`.
- Earlier analysis branch: `CS5211`, `02fb63a`.
- Original ROM SHA-256:
  `a7a5b681eb62026afcb11232635fb68251f40ca0348f6b513913bc51bb4a2451`.
- Patched ROM SHA-256:
  `0bc171d52bf83b89698ba3d899d6e993790ffe528d2bf871efa61d6130a9c4b2`.
- These ROMs differ at 1,200 bytes, all below `0x0800`. Their firmware and
  non-EDID data are identical. All sixteen patched EDIDs pass the checksum.
- Rechecked the Ghidra listing with independent radare2 decoding and a bounded
  instruction interpreter: `python3 scripts/audit_cs5211.py binaries/dump_CS5211.txt`.
  Results are in `artifacts/cs5211-review-2026-09-28/audit.json`.
- The interpreter executes selected real instructions, including the profile
  writes and Timer 0 ISR. It does not model the CS5211's hardware, startup ROM
  loader, undocumented registers, or full firmware execution.
- No panel capture, simulation source, measured wire trace, or successful
  firmware variant is available in the reviewed repository. The visible fault
  has not been reproduced on hardware in this review.

## What remains plausible about the colour diagnosis

The Samsung specification shows dual-pixel, 18-bit LVDS: three data lanes and
one clock per odd/even channel. CS5211 datasheet section 4.5 explicitly gives
the two mappings. Its 24-bit SPWG mode places component bits 0–5 on the first
three lanes; its 24-bit OpenLDI mode places bits 2–7 there. The unused fourth
lane contains bits 6–7 or 0–1 respectively.

Therefore the proposed SPWG24-to-18-bit mismatch is electrically plausible.
For an unmodified 8-bit component `x`, it predicts received code `x & 63`,
where compatible JEIDA/OpenLDI24 predicts `x >> 2`. This is loss of the upper
two bits, not reversal of all bits. A linear ramp should repeat four times,
with sharp drops at 63→64, 127→128, and 191→192.

| Source component | Compatible 18-bit received code | SPWG24 mismatch received code |
| ---: | ---: | ---: |
| 0 | 0 | 0 |
| 32 | 8 | 32 |
| 63 | 15 | 63 |
| 64 | 16 | 0 |
| 127 | 31 | 63 |
| 128 | 32 | 0 |
| 191 | 47 | 63 |
| 192 | 48 | 0 |
| 255 | 63 | 63 |

These are digital receiver codes, not predicted camera brightness. Source
gamma, colour management, range conversion, and dithering can alter which
codes actually reach the bridge.

Correct black, white, and saturated primaries are insufficient proof: any
permutation of bits within a colour also preserves all-zero and all-one
values. Recreating a similar picture in a simulation proves compatibility
with a hypothesis, not uniqueness. Also, the owner reports the replacement
panel may not be genuine Samsung; its behaviour in the T60 is a valuable
reference, while the Samsung PDF is only a specification proxy for that unit.

Ranked possibilities and discriminating predictions:

1. **SPWG24-to-18-bit mismatch:** repeated ramp cycles, exact modulo-64
   boundaries, and source weights 64/128 disappear with an unchanged pixel path.
2. **Other bit/lane wiring or serializer mapping error:** individual bit-weight
   patches respond in the wrong order, or a pure colour leaks into another
   channel. Odd/even wiring faults differ between alternating pixel columns.
3. **Source-side depth/range/colour conversion:** behaviour changes with the
   transmitted DP format, gamma state, or source. Record actual format rather
   than assuming an EDID request was honoured.
4. **Bridge processing or bad calibration:** a conventional gamma error usually
   leaves ramps monotonic; an arbitrary LUT can be nonmonotonic and cannot be
   excluded solely from appearance. No such LUT has been identified here.

Terminology: TI uses JEIDA/Format 1 and VESA/Format 2. This CS5211 datasheet
uses OpenLDI and SPWG for the corresponding bit placements. Our earlier
generic correction that OpenLDI is only a family name was incomplete in this
chip's documentation context. For 18-bit operation, its two mappings coincide.
JEIDA24 is compatible at the bit-placement level; actual source depth,
dual-port operation, clocking, and wiring still have to agree.

## Corrections to our firmware analysis

### Profile byte 11 is not masked to its low nibble

The true write at logical PC `0x0511–0x0524` is:

```text
XDATA[0x01f4] = profile[11] | ((ROM[0x1122] & 0x0f) << 4)
```

There is no `AND 0x0f` on the profile value. The default global byte is zero,
so all eight bits of profile byte 11 pass through unchanged. The audit tests
all 256 profile values with six global values. Our previous nibble formula
and suggested limitation to low-bit tests were wrong.

The other documented profile writes agree with the bytes. In the copy slice,
profile byte 3 bit 3 is forced clear and byte 4 bit 3 is forced set; changing
either source bit has no effect. Bytes 12–15 are not read by that slice. Thus
34 of the generator's 128 single-bit trials have identical copy-slice writes.
This is not a claim about unmodelled hardware use of those bytes.

### The profile table is not the only configuration source

The global block at physical `0x1110–0x1122` also controls initialization:

| Physical ROM | Observed use (logical PC references) |
| --- | --- |
| `0x1110` | Written to XDATA `0x0602` (`0x02c2`). |
| `0x1111` | ORed with retained high bits of `0x0603` (`0x02d1`). |
| `0x1112` | Low two bits select control modes; bits 4 and 5 enable/modify later routines (`0x0356`, `0x058b`, `0x0599`, `0x0d35`). |
| `0x1113–0x111a` | Written to `0x01d1`, `0x01f7`, `0x01d0`, `0x01d3`, `0x01f8`, `0x01d4`, `0x01f9`, `0x01d6`; several also feed delay calculations. |
| `0x111b–0x111d` | Initialize a bounded 0–10 control level and its limits, used by the timer/control routines. |
| `0x111e`, bit 0 | Selects two distinct initialization paths (`0x01c5`). See below. |
| `0x111f–0x1121` | Conditionally copied into XDATA `0x00e4–0x00e6` when `0x111e` bit 0 is clear and `0x1121 != 0xaa`. |
| `0x1122`, low nibble | Shifted into the high nibble of `0x01f4` and ORed with profile byte 11. |

`ROM[0x111e]` is `0x01` in both original and EDID-patched dumps. Its paths are:

| Bit 0 | XDATA `0x01bb` | XDATA `0x00e3` | Conditional `0x00e4–0x00e6` writes |
| ---: | ---: | ---: | --- |
| 1 (original) | `0x14` | `0x10` | Skipped |
| 0 | `0x94` | `0x50` | Per the three constants and sentinel test above |

This establishes a real mode flag and additional candidate registers. It does
**not** identify that flag as VESA/JEIDA. `0x00e3` and `0x01e3` are distinct
addresses. No hardware bit meanings can be inferred from similar numbers alone.

A later independent lead improves the interpretation: screenshots of the
actual CS5211 E2PROM tool V2.9 in
[Witheart's configuration notes](https://github.com/Witheart/witheart.github.io/blob/8439994a1ac80d1ad512aeb29c47ab1c699be5d6/_posts/2026-04-28-rk-android-ubuntu-%E9%80%9A%E7%94%A8%E5%BC%80%E5%8F%91%E6%8C%87%E5%8D%97-cs5211-%E5%B1%8F%E5%8F%82%E8%AE%BE%E7%BD%AE%E6%B3%A8%E6%84%8F%E4%BA%8B%E9%A1%B9.md)
show the global controls: DP speed/lanes/interface, internal 27 MHz versus
external crystal with SSC, LVDS slew rate, PWM, brightness buttons, and
power sequencing. The conditional three-byte writes behind `0x111e` bit 0 fit
clock-source/SSC configuration. This is a supported inference, not a verified
register definition, and suggests deprioritizing that flag as a mapping test.
The screenshot's firmware version differs from this ROM. No executable or
paired generated ROMs were obtained. Screenshot copies are preserved in the
review artifacts as `PixPin_2026-04-28_15-54-06.png` and `...15-54-27.png`.

The old claim that LVDS mapping **must** be in profile bytes 8–11 is withdrawn.
They remain convenient candidates; their values or register adjacency do not
prove their roles. Literal initialization writes elsewhere can also select a
mode. A negative profile sweep would not rule out a firmware solution.

“Boot-only” was also too strong. The copy routine is in the link setup loop;
the path from `0x0644` returns to `0x03a6`, from which setup can recur. One
static write site does not mean the register is written only once per boot.

### The 11-byte curve has an identified timer use

At physical `0x100b`, `02 0c 48` is the Timer 0 vector on the standard 8051.
The ISR at logical `0x0c48–0x0cbb` was absent from the earlier reset-reachable
Ghidra listing. It explicitly reads internal RAM `0x16 + level` and
`0x16 + (10 - level)`, loads TH0, clears TL0, and alternates XDATA `0x00b3`
between `0x2c` and `0x20`. Level 10 selects a constant output state.

That connects `ff fb f6 f1 ec e6 e2 dd d8 d3 00` to timer duty-cycle generation.
Backlight control is a strong interpretation, supported by the chip's
advertised brightness controls; the physical pin driven by `0x00b3` remains
unverified. This table is not evidence of per-channel RGB gamma correction.

### The other opaque data was partitioned incorrectly

Physical `0x0800–0x0803` is `2c 8b 31 de`. It is followed by **three identical
128-byte blocks**, starting at `0x0804`, `0x0884`, and `0x0904`. The recurring
`0f 06 05 03` bytes are the last four bytes of each block, not demonstrated
record headers. Our 124-byte segmentation was arbitrary.

The purpose is unknown. Neither “scrambled gamma/dither LUT” nor “definitely
not a LUT” is supported. A boot loader or hardware engine can consume data
without an obvious copy loop in this 8051 image. No RGB LUT has been identified;
absence of one has not been proved.

## Latest automated testing code

At `bad0c35`, the earlier misaddressed EDID[0x1e] experiments have been removed
and checksums are repaired. The old review's 6,313-variant count is stale.
Current generation produces 1,282 candidates and 1,250 unique non-baseline
images (before accounting for identical hardware effects).

Remaining concrete problems:

- **Incorrect EDID labels.** EDID 1.4 byte `0x14` low nibble `5` means
  DisplayPort; `6` is reserved. `0x95` means 6 bpc + DisplayPort, `0xa5` means
  8 bpc + DisplayPort. `0x96` and `0xa6` are not JEIDA selectors. A 6-bpc EDID
  experiment is useful as a source-depth experiment, with actual DP format
  recorded; it is not proof that LVDS mapping changed.
- **Executable bytes treated as a header.** `0x1000–0x100f` contains reset
  and interrupt vectors. Flipping `0x1000` from `02` to `03`, for example,
  changes `LJMP` into `RR A`. Remove these from mapping sweeps.
- **Missing global candidates.** No generated candidate touches
  `0x1110–0x1122`. This means the current test set does not cover all known
  configurable initialization paths.
- **Unverified writes.** Arduino ignores `Wire.endTransmission()` status and
  the host assumes `current_rom = next_rom` without readback. A failed write
  can remain undetected and invalidate subsequent differential flashing.
- **Outcome is not colour correctness.** `xrandr` connectivity detects the
  source-to-bridge link. Camera files allow later inspection, but an absent
  capture can still yield a CONNECTED log. Manual mode records only Enter.
- **Power sequencing is unverified.** The script writes before shutting down
  the source. Neither an ATX LED nor switching Arduino pin 12 proves the bridge
  has reset or that the EEPROM bus is isolated. Check the board's actual power
  and reset wiring before interpreting a negative experiment.
- **Old files remain in the queue.** Generation writes new filenames into an
  existing directory without replacing the old set. If run over a previous
  generation, removed experiments can still be tested. Use a fresh run directory
  and manifest with ROM hashes.

## Recommended next experiment

1. Establish a diagnostic image on the working T60 and on the bridge using the
   same panel. Use raw 0–255 RGB and grey ramps, values around 63/64, 127/128,
   191/192, individual bit weights 1,2,4,8,16,32,64,128, and alternating odd/even
   pixel patterns. Use native resolution; record any scaling, gamma, dithering,
   and source format. Photograph with fixed exposure without clipped highlights.
2. If the modulo-64 prediction matches, prioritize LVDS mapping/depth work. If
   colours cross channels or odd/even columns differ, revisit lane mapping and
   wiring before assuming a one-bit firmware fix. This image is diagnostic even
   if the exact register remains unknown.
3. Make the flash loop trustworthy: dump and save the baseline, check each I2C
   transaction, read back each candidate, compare all 8 KiB, confirm the bridge
   reloads it, and restore the baseline between inconclusive runs. Record
   successful capture/manual colour classification as a separate outcome.
4. Start with the meaningful single-bit profile tests (94 affect the known
   copy slice), keeping the other bytes at baseline. Include byte 11's high
   bits. Broad exhaustive combinations are harder to interpret.
5. Use the global block to map clock, timing, brightness and slew-rate controls;
   it must not be ignored, but the newly found tool screenshot makes `0x111e`
   bit 0 a lower-priority LVDS-mapping candidate. Do not substitute changing
   clock source for a demonstrated format change.
6. A known-good CS5211 ROM generated for the same timing but different LVDS
   mapping remains the best way to assign a semantic name to a bit. Chip pins
   53/54 (`S_SDA`/`S_SCL`) are documented for internal register access, distinct
   from EEPROM-master pins 50/51; access protocol and voltage must be established
  before using them. The public PDF provides no usable full register map.

### A source-pixel workaround that also tests the hypothesis

If the path really discards the upper two component bits, pre-encode each
desired RGB8 component `x` as `x >> 2`. Then the physical receiver gets
`(x >> 2) & 63`, exactly the desired six-bit code. This is a derived conditional
workaround, not a tested repair. Correct operation depends on preserving
those encoded bytes through the GPU, link, and bridge.

Generate the probes with:

```sh
python3 scripts/cs5211_diagnostic_pattern.py artifacts/cs5211-review-2026-09-28
```

`normal-vs-compensated.png` contains paired normal and compressed grey/R/G/B
ramps, bit-weight patches, and alternating odd/even pixel patterns.
`whole-image-compensated.png` applies the transformation to all pixels.
The second image should look very dark on a healthy path, but should recover
the first image's intended appearance under the exact low-six-bit fault.
The generator verifies the saved PNG pixel values at all ramp levels.

For a later desktop workaround, a GPU per-channel LUT that compresses the
signal into 0–63 might implement this mapping, but quantization and dithering
must be checked. Changing panel backlight brightness cannot perform it.

## Sources

- Capstone CS5211 datasheet, in upstream `Screen/docs/specs_CapStone_CS5211.pdf`,
  sections 3, 4.4–4.8; local extracted copy in the review artifact directory.
- Samsung LTN141P4-L03 specification, section 5.4, page 17.
- TI [SNLA014A](https://www.ti.com/lit/an/snla014a/snla014a.pdf), sections 1 and 3.
- VESA [E-EDID A2](https://glenwing.github.io/docs/VESA-EEDID-A2.pdf), table 3.11,
  page 24: digital interface and bit-depth fields.
- Keil [8051 interrupt vectors](https://www.keil.com/appnotes/files/apnt_103.pdf).

No firmware has been flashed during this review. A working colour fix and the
specific CS5211 mapping register remain unconfirmed.
