# CS5211 solution retrospective: what the firmware did and did not tell us

Reviewed against Levi's commit
[`93c5c9f2e0772ec6089b54aa51863dafe25a8505`](https://github.com/nlevi-dev/ThinkPadSleeperBuild/commit/93c5c9f2e0772ec6089b54aa51863dafe25a8505)
("firmware resolved", 2026-09-28). Levi obtained labelled configuration-tool
output and reports a working panel. This investigation has no physical panel
access and does not independently confirm his hardware observations.

## 1. Exact solution, checked against the bytes

Relative to our previous **EDID-only** image, the committed solution changes
exactly 20 bytes:

| Physical EEPROM offset | Before → after | Effect / evidence |
|---|---|---|
| `1013 + 10*n`, `n=0..15` (hex) | `01 → 05` | Bit 2 of profile byte 3 changes in every record. |
| `0ffa..0ffd` | `1b 6c aa c2 → da 96 05 52` | Firmware integrity field, called checksum in Levi's tool-derived table. |

All EDIDs, other profile bytes, opaque blocks and executable instructions are
unchanged relative to that EDID-only image. The previous original-to-EDID-only
change was 1,200 bytes, entirely below `0800`.

The upstream `patch_cs5211.py`, applied to the original ROM and panel EDID CSV,
reproduces the committed solved image **byte for byte**. Its SHA-256 is:

`6ed6777839ac1a158ed1382f5c55f7abf7f9a2f0cfe82d582c493484ea39ea1e`

### Register interpretation supplied by the labelled modes

The firmware itself establishes `XDATA[01e1] = profile[3] & f7`.
Levi's four labelled configurations supply the missing hardware interpretation:

| Bits per component | Mapping | Profile byte 3 | Firmware checksum, as published |
|---:|---|---:|---:|
| 8 | VESA | `01` | `1b6caac2` |
| 8 | JEIDA | `05` | `da960552` |
| 6 | VESA | `03` | `9c58e855` |
| 6 | JEIDA | `07` | `5da247c5` |

Within these configurations:

- `01e1.bit2`: 0 = VESA, 1 = JEIDA.
- `01e1.bit1`: 0 = 8 bits/component, 1 = 6 bits/component.
- Bit 0 stays 1 in all four modes; those examples do not establish its meaning.
- Bit 3 is cleared by the firmware independently of profile contents.
- 6 bits/component means RGB18; 8 means RGB24. Neither means 16-bit RGB.

This identifies the output-format field using **labelled external evidence plus
our recovered dataflow**. Disassembly alone did not name these hardware bits.
The published solution uses JEIDA RGB24 to drive the RGB18 panel; it does not
change the depth bit. The fact that it changes only `01e1` also shows our later
symmetric-pair modifications were unnecessary for this solution.

## 2. We already generated the correct selector edit—and missed acceptance

The archived manifest includes `candidate-p03-bit2.bin`. Its hash agrees with a
fresh reconstruction of the exact sixteen `01 → 05` edits. It differs from
Levi's solution **only in the four checksum bytes**, retaining `1b6caac2`.

Our CPU harness copies EEPROM `1000..1fff` into 8051 CODE and starts at PC 0.
EEPROM `0ffa..0ffd` is outside that copied region. The application does not
validate this field. Consequently, the stale-checksum candidate and the solved
image produce identical emulator traces for **all 16 profile straps**. Both
change only XDATA `01e1` (`01 → 05`) relative to the EDID-only baseline.

This is the major methodological miss. "Reaches the link loop in the emulator"
was a valid instruction-execution result but insufficient evidence that a
physical CS5211 would accept the image. Levi reports rejection without the
matching checksum. Whether validation is in an internal boot ROM, hardware
loader, or another mechanism is not established by this external EEPROM dump.

**All 93 single-bit candidates and 56 coupled/literal candidates in the older
reports are CPU experiments, not validated flash images.** They retain the
baseline integrity field. The PR includes their manifests and generators, not
149 ready-to-flash binaries. The generators explicitly report this limitation.

## 3. Additional finding after seeing the solution: a checksum delta model

Plain `zlib.crc32` of the full tail or a body length of `0e86` does not equal
either stored checksum. The adjacent bytes at `0ffe..0fff` are `0e86`; treating
that as a length remains a hypothesis.

However, the following **fixed-image differential rule** predicts every checksum
in Levi's four-entry mode table exactly:

```python
from zlib import crc32

def reverse32(x):
    return int(f"{x:032b}"[::-1], 2)

predicted_new_checksum = old_checksum ^ reverse32(
    crc32(old_rom[0x1000:0x1e84]) ^
    crc32(new_rom[0x1000:0x1e84])
)
```

The slice is half-open: last included byte `1e83`, payload length `0e84`.
Bit reversal of a 32-bit word is different from reversing its four bytes.
For the mapping change, the CRC difference is `09f55f83`; reversing its bits
gives `c1faaf90`, exactly `1b6caac2 XOR da960552`.

A bounded exploratory search tested common CRC32 polynomials, reflection,
byte-group ordering, initial/final conventions and nearby payload ends. Its
reproducible search is in `scripts/cs5211_checksum_probe.py`. The simple rule
above was selected after inspecting the solution, not predicted beforehand.

**Limits:** the four modes provide two independently changed bits plus their
combination, always at the same sixteen offsets. They are not four independent
hardware validations. The rule does not identify the absolute checksum's
initial state, any fixed prefix/suffix, exact general payload boundaries, or
validation mechanism. Alternative coverage models can be indistinguishable on
these edits. It is a useful hypothesis for additional same-image edits; it is
not a replacement for the manufacturer's checksum algorithm. The shipped
patcher is left unchanged and still uses its reported mode table.

## 4. How we could have approached it from the firmware

There is no vendor C source in the repository. "From source" here means the
actual 8051 instructions, our readable reconstruction, and—once available—the
configuration patcher's source. The shortest defensible route would have been:

### Step 1: establish the image boundary before any mutation campaign

Map the entire EEPROM, including the bytes immediately preceding the reset
vector. `1000` is executable code (`LJMP`), not an arbitrary header. The six
nonzero bytes at `0ffa..0fff` immediately before that entry deserve explicit
integrity/length hypotheses. Determine what the loader does before PC 0, or mark
image acceptance as untested if that loader is absent.

We should have made two separate claims: "this CPU will write the intended
register value" and "the chip accepts the modified ROM." Only the first was
available from our tools. Boot success in our harness cannot test the second.

### Step 2: trace configuration reads to register writes

GPIO `00ca & 0f` is multiplied by 16 and stored in IRAM `08`. The decisive
sequence, visible before Levi's solution, is:

```text
CODE 04bd: MOV  A,08              ; selected profile displacement
CODE 04bf: MOV  DPTR,#0013        ; profile 0 starts at CODE 0010, byte +3
CODE 04c2: MOVC A,@A+DPTR
CODE 04c3: ANL  A,#f7
CODE 04c5: MOV  DPTR,#01e1
CODE 04c8: MOVX @DPTR,A
```

Physical source address is `1013 + 10*n` in hexadecimal. Bit 2 survives the
mask. Changing `01` to `05` therefore changes exactly register `01e1.bit2`.
This sequence is byte-checked by the solution verifier.

### Step 3: keep a small, explicit hypothesis set

Record all twelve register destinations and masks, isolate clock-affecting
settings, and test single surviving profile bits. `profile[3].bit2` was already
in that set. The pipeline needed an image-integrity step before hardware tests.
A larger enumeration of paired constants did not solve the missing acceptance
problem and had no new observable that could identify colour semantics.

No instruction here proves that bit 2 means JEIDA. Naming it from its numeric
position or nearby register values would have been a guess. A single opaque
firmware with no relevant peripheral readback admits multiple hardware
interpretations; additional CPU coverage cannot resolve that ambiguity.

### Step 4: use labelled tool outputs as a semantic oracle

Generate otherwise-identical VESA/JEIDA and 6/8-bit configurations and diff them.
Separate profile changes from changes in the integrity field. Cross the profile
diffs with the recovered write map to name the actual register bits. Levi's
patcher now records precisely these four labelled configurations; that external
information closes the gap.

This is a firmware/software-only route once the configuration utility or its
labelled output is available. If restricted to the original single dump and
CPU emulator, we could recover the candidate and dataflow, but could not
honestly prove the selector's name or a valid checksum repair. Reverse-engineering
the vendor utility or loader would be another software route, if obtainable.

### Step 5: verify acceptance and colour separately

First verify the reconstructed output exactly matches a known accepted image.
Then use physical panel evidence to check gradients, bit weights and odd/even
pixels. Our diagnostic PNGs support that final stage, but we have no measurement
from running them. Published hardware success belongs to Levi; it should not be
retroactively described as our emulator discovering the fix.

## 5. Other findings retained from the investigation

See [the archive index](README.md) for evidence and reproduction commands.

- Sixteen 128-byte EDID blocks occupy `0000..07ff` (2,048 bytes).
- Sixteen 16-byte profiles occupy `1010..110f`; the active profile is latched at
  startup and its output settings are rewritten after link recovery.
- Twelve profile register destinations, forced masks, and the profile/global
  OR interaction at `01f4` were recovered and tested.
- DP M/N arithmetic, divider branches and exact software float rounding were
  reconstructed, including 2,048 wide-domain checks.
- Brightness is an eleven-entry PWM table, not an RGB correction LUT. Malformed
  configured limits can lead to an out-of-table read in the brightness ISR.
- Power/button paths, timeouts, recovery, initialization constants and application
  coverage are documented with CPU traces and independent uCsim comparisons.
- The three identical 128-byte nibble blocks at `0804`, `0884`, `0904` remain
  unexplained. Direct monotonic interpretations failed the tested hypotheses;
  their hardware function is not established.

### Repository assertions to read with care

The solution narrows the colour problem; it does not make the entire firmware
format "fully understood." The four-mode table has a specific image/template
scope. It should not be treated as a checksum generator for arbitrary modified
firmware bodies. Similarly, profile byte 0's whole-byte zero/nonzero clock branch
is established, but the four colour-mode examples alone do not prove every bit
of that byte is a channel-count field.

The legacy AutoFlash generator also treats `1000..100f` as a mutable header
although it contains instructions, labels part of EDID's interface field as
VESA/JEIDA, and does not repair firmware integrity. It still points at the
renamed EDID-only dump. Those experiments should not be interpreted as
controlled colour-selector tests. This PR does not run the flashing harness.
