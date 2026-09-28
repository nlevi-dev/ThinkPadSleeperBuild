> **Historical investigation:** written before reviewing Levi’s solution. See the
> [solution retrospective](../SOLUTION.md) for corrections, the identified selector,
> and the missing firmware-integrity check. Candidate images are CPU experiments,
> not validated flash images. Paths below refer to this analysis directory.

# CS5211: five-stage investigation

2026-09-28. Scope: recover as much as possible from the existing assets, without
Levi's solution, physical measurements, or a manufacturer register map.

## Results at a glance

| Goal | Outcome |
| --- | --- |
| 1. Find untested execution paths | 526 scenarios; all feasible application branch outcomes covered under the stated model. Remaining whole-program gaps are in generic startup/arithmetic library paths. |
| 2. Map configuration dependencies | 280 bit records; 4,096 profile/global combinations, 768 gated-copy cases, and 256 initial-level cases verified. A malformed-limit interaction reads outside the brightness table. |
| 3. Investigate opaque blocks | Direct monotonic encodings, specified header checks, and specified seed-generator models rejected. Delta encoding and autonomous hardware use remain possible. |
| 4. Reconstruct executable firmware | Readable application model matches 33,354 foreground register events, 2,048 wide-range clock cases, and 44 ISR cases. Eight configurations also match uCsim across all 2,048 compared XDATA bytes. |
| 5. Produce justified candidates | 93 candidate images generated from the EDID-patched baseline and checked against the CPU emulator. No evidence identifies a unique JEIDA/SPWG selector; an explicit counterexample demonstrates that limit. |

This is not a recovered hardware colour fix. It is a substantially more complete
firmware reconstruction and a constrained, reviewable candidate set.

## 1. Coverage: execution counts versus actual paths

The previous campaign counted tests but did not aggregate conditional branch
outcomes. The emulator adapter now records both fallthrough and taken outcomes
at each conditional instruction. Neither core instruction implementations nor
ROM instructions were modified for this instrumentation.

The static denominator comes from the complete 8051 listing:

| Scope | Instructions executed / listed | Branch outcomes exercised / listed |
| --- | ---: | ---: |
| Whole decoded program | 1,766 / 2,013 | 222 / 280 |
| Application, reset/vector glue, application helpers and ISR | 1,190 / 1,191 | 125 / 128 |

Application scope excludes the generic C initialization parser at `013f–01bf`
and arithmetic library at `0647–0a1f`. Those exclusions are explicit, not silently
removed from the whole-program denominator.

Three missing application outcomes are infeasible under the firmware's own
state invariants:

1. **PC `03e6`, JNZ fallthrough:** the preceding instruction ORs the byte with
   1. No byte can produce zero.
2. **PC `0c9d`, level-equals-10 branch:** the ISR already returned for level 10.
   No enabled firmware handler changes the level during this ISR.
3. **PC `0e67`, low counter byte wraps to zero:** both application wait loops
   initialize the counter to zero and exit after 201. They never reach 256.
   Consequently the only unexecuted application instruction, `0e69` (increment
   high counter byte), is also unreachable through those calls.

The new scenarios include all 256 global mode bytes, variations of all six
previously unseeded baseline registers, timeout paths, power-button edges,
recovery-marker changes, lane/status changes between polls, clock boundaries,
and Timer 0 counter carry. External interrupt 0 was explicitly injected to
exercise its otherwise unused vector; ordinary ROM initialization enables Timer 0.

Two tooling issues were caught:

- The latest annotated Ghidra project still had an incomplete ISR function and
  omitted vector/ISR instructions from its export. Disassembly and function-body
  creation were repaired. Coverage uses the complete listing.
- emu8051 does not clear the external-interrupt edge flag on entry. The synthetic
  one-shot interrupt test explicitly deasserts it at the vector, rather than
  mistaking continuous retriggering for a firmware defect.

**Limits:** this is firmware control-flow coverage with scripted external inputs.
It does not establish that every scripted transition can occur on silicon.
There is no claim of complete generic library coverage, cycle-accurate CS5211
peripheral modelling, or coverage under arbitrary executable-code corruption.

Evidence: `coverage.json`, `coverage-classification.json`, `cs5211_deep.py`.

## 2. Dependencies and interactions

`configuration-bits.json` catalogues all 128 bits of a profile record and all
152 bits in the global configuration block. Each record specifies its target,
conditions, masks, and application phase. The other 15 profiles use the same
logic, selected by the latched low four GPIO bits.

### Confirmed interactions

- **Shared `01f4` bits:** all 4,096 combinations satisfy
  `profile[11] | ((ROM[1122] & 15) << 4)`. A set bit in either source prevents
  the other source from clearing it.
- **Conditional three-byte copy:** `111f–1121` reaches `00e4–00e6` only when
  `111e.bit0 == 0` and the whole byte at `1121` is not `aa`. Tested all 256 flag
  values against three sentinel cases. A boot-only test with stock `111e=1`
  would incorrectly classify these fields as ineffective.
- **Level/limits gate:** all 256 initial levels confirm that values above 10
  replace both limits with 0 and 10. Otherwise `111c/111d` remain raw limits.
- **Mode gate:** brightness-button direction matters only when the low two mode
  bits equal 1. Power-button polling has its own bit-4 enable.
- **Forced capability bit:** global `1111.bit7` cannot change the eventual
  `0603.bit7`: the preceding firmware write `0603=82` makes the retained bit 1.

### Newly reproduced out-of-table brightness access

Patch `1112=01` (button mode) and `111d=0b` (upper limit 11), leaving the initial
level at 10. A synthetic up-button press (`00b0=20`) raises the level to 11.
Actual execution subsequently reaches PC `0c76` with R0=`21`.

The intended reload table is IRAM `16–20`, so this reads unrelated RAM. It is a
real configuration interaction in the firmware. It does not identify a colour
format setting or establish an explanation for the reported colour issue.

Evidence: `profile-global-or.json`, `conditional-global-copy.json`,
`initial-level-gate.json`, `brightness-out-of-table.json`.

## 3. Opaque data: what was tested and what survived

Physical `0800–0803` contains `2c 8b 31 de`. Physical `0804`, `0884`, and `0904`
start three identical 128-byte blocks. Every payload byte is a nibble, 0–15.

| Interpretation tested | Observation |
| --- | --- |
| Raw monotonic curve | Rejected. The first four values are `a,4,4,a`; the A/B/A subsequence prevents monotonicity under any bijective value relabeling. |
| Adjacent nibbles packed into 8- or 16-bit samples, both orders | All tested sequences nonmonotonic. |
| Small ordinary ordered-dither rank tiles | The tested 4-/16-entry blocks do not have the required distinct ranks. This says nothing about stochastic dithering. |
| CRC32, Adler32, leading MD5/SHA256 word, over specified raw/packed payloads | No match to either byte order of the four-byte header; 16 checks. Other checksum/framing schemes remain possible. |
| Header-seeded ANSI, MSVC, Numerical Recipes, Borland LCGs or xorshift32 | No exact match across 9,570 specified seed-order, offset, and output-bit choices. Best matching prefix is only three nibbles. |
| At-most-32-stage linear recurrence of the raw sequence/bit planes | Inconsistent with measured GF(2) linear complexity: 64–65 per bit plane and 255–256 for the serial bit streams. |
| Unsigned four-bit deltas | Still possible: cumulative output is monotonic and spans 935 counts. No target endpoint, gain, or format is known. |

Empirical entropy is 3.946 bits per nibble. Interpreting values as signed
four-bit deltas gives a total of -89. These statistics describe the data; they
do not identify its consumer.

The unsigned cumulative curve stays within 2.43% of a normalized straight line.
Only 2.49% of 10,000 seeded permutations of the same values were at least as
close. This is an exploratory observation after testing multiple interpretations,
not corrected statistical evidence that the block is a gamma table. Normalizing
also hides the unknown endpoint. The delta interpretation remains a lead.

**Crucial boundary:** the emulated CPU starts from physical ROM `1000`. It does
not model the chip's loader or consumers of the preceding EEPROM bytes. Neither
execution coverage nor unchanged CPU output can establish that the opaque blocks
are unused by hardware. Encryption, index permutations, and other packing schemes
remain unresolved.

Evidence: `opaque-tests.json`, `cs5211_opaque.py`. Its tested generator families
and parameters are explicit and reproducible; no arbitrary fitted decoder was
presented as a discovery.

## 4. Readable executable reconstruction

`scripts/cs5211_model.py` reconstructs:

- The actual IRAM initialization records and global initialization writes.
- GPIO selection and profile application.
- Training, video-ready, and clock-ready waits, timeout resets, and recovery.
- Clock arithmetic and register programming.
- Brightness buttons, power-button edge handling, and shutdown sequencing.
- The Timer 0 ISR as a separately invoked event.

Its state transitions are:

```text
initialize -> train -> train_poll -> wait_video -> wait_clock -> steady
                ^          |              |            |          |
                +-- recovery / timeout ---+------------+-- link loss
```

The model retains busy-wait arguments but does not predict physical time. It
does not reproduce instruction-by-instruction SFR writes or cycle scheduling.
Foreground XDATA events and ISR events are verified separately, so agreement
must not be described as a cycle-exact replacement for the chip.

### The floating-point discrepancy is explained

The ROM's integer conversion **chops discarded mantissa bits**. Floating-point
multiplication and division **round nearest, halfway upward**. Native host
float32 normally rounds integer conversions and uses a different halfway rule.

The reconstruction uses exact rational arithmetic to apply these rules at each
stage. It explains all 15 earlier discrepancies and matches all 512 saved cases.
Another 2,048 cases sample 24-bit M/N inputs and the full 8-bit rate/port domains,
including zero-denominator cases and integer overflow/saturation.
Every resulting Q value and divider register agrees with CPU execution.

### Differential verification

- **262 application traces:** 33,354 ordered foreground register reads/writes
  match. These include all 256 mode bytes with randomized configuration fields,
  power-button edges, shutdown, both timeout paths, and recovery at four points.
- **44 ISR cases:** all levels 0–10, both phases, and both normal/carry counters
  match register writes, timer reloads, and relevant RAM changes.
- **Eight three-way checks:** the readable model, emu8051, and independent uCsim
  agree on all 2,048 XDATA bytes after startup across distinct configurations.

The trace replay supplies observed external reads and independently predicts
ordered writes. The eight three-way checks instead run the model from seeded
memory, providing an additional check on the replay setup.

Evidence: `model-traces.json`, `model-clock-wide.json`, `model-isr.json`,
`independent-model-check.json`, and `independent/case-*.txt` / `.ihx`.

## 5. Candidate images and the identifiability limit

### A correction to the earlier recommendation

Discarding all of profile byte 0 was too aggressive. Only its bit 0 flips the
stock value 1 to zero and changes the clock branch. Flipping any of bits 1–7
keeps the byte nonzero, so the clock calculation is unchanged. Those bits still
reach `009f`; the firmware does not establish that they are reserved.

The candidate set therefore has **93** images:

| Priority | Candidates | Basis |
| --- | ---: | --- |
| Tier 1 | 86 | Effective bits in profile bytes 1–11; one opaque register bit changes, without clock calculation or firmware branch changes. |
| Tier 2 | 7 | Upper bits of profile byte 0; likewise preserve the observed clock branch, but share the byte whose zero/nonzero value controls clock division. Hardware field validity is unknown. |

There is **no evidence-based ordering within either tier**. The tiers rank
experimental isolation, not measured probability of selecting JEIDA.

Images are generated from the existing EDID-patched dump, SHA-256
`0bc171d52bf83b89698ba3d899d6e993790ffe528d2bf871efa61d6130a9c4b2`.
Each changes the same single bit in all 16 profile slots, preventing an unknown
GPIO selection from silently selecting an unpatched copy. EDID, opaque data,
global settings, and executable instructions are unchanged.

Each image was run through the CPU emulator. Every image reaches the link loop,
has the same executed-PC set as its baseline, and differs in exactly one ordered
register write. The manifest contains addresses, before/after values, affected
register, and SHA-256 for each binary. They have not been flashed or confirmed
to work on the panel.

This set does not exhaust multi-bit encodings, hardcoded register literals,
global settings, or autonomous hardware use of pre-code data.

### Why the evidence cannot select a unique patch

`identifiability-witness.json` constructs two explicitly hypothetical hardware
interpretations:

- Model A assigns compatible mapping to `01dc.bit0`.
- Model B assigns compatible mapping to `01de.bit0`.

Both retain identical register readback and CPU behaviour. With both baseline
bits zero, both reproduce the assumed low-six-bit colour fault. Patching
profile byte 1 bit 0 fixes A but not B; patching byte 2 bit 0 fixes B but not A.
This is checked over all 256 component input values.

These are counterexamples, **not claims about either real register**. They show
why a unique selector assignment does not follow from the available CPU traces
and baseline symptom. A semantic anchor—another labelled configuration, the tool,
a register specification, or a hardware observation—would distinguish them.

We have reached a defined limit for this evidence while still leaving explicit
research leads: delta/encoded opaque tables, compiler-library paths outside the
application domain, and undocumented fixed-register semantics.

## Artifacts and reproduction

All new outputs are in `artifacts/cs5211-deep/`. Candidate binaries are in its
`candidates/` directory, indexed by `candidate-manifest.json`.

```sh
python3 scripts/cs5211_blackbox.py --build
python3 scripts/cs5211_deep.py
python3 scripts/cs5211_dependencies.py
python3 scripts/cs5211_opaque.py
python3 scripts/cs5211_verify_model.py
python3 scripts/cs5211_validate_deep.py
python3 scripts/cs5211_candidates.py
```

Requirements: Python 3, clang, the pinned local emu8051 checkout, and `s51` from
SDCC. No additional Python packages are required. Ghidra annotations and the
complete listing are updated separately by `AnnotateCS5211Blackbox.java`.

No firmware was flashed, no physical output was measured, and no candidate has
been represented as Levi's recovered solution.
