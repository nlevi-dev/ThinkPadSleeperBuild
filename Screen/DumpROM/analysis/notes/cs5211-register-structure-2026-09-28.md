> **Historical investigation:** written before reviewing Levi’s solution. See the
> [solution retrospective](../SOLUTION.md) for corrections, the identified selector,
> and the missing firmware-integrity check. Candidate images are CPU experiments,
> not validated flash images. Paths below refer to this analysis directory.

# CS5211: paired fields and fixed initialization constants

## Result

The firmware exposes more configuration than the previous 93 single-profile-bit
images covered. We generated **56 additional images** and checked their actual
8051 execution through boot and a synthetic link loss/recovery, using profile
straps 0 and 15. These are experiments, not identified colour-format settings.

The strongest new structural finding is that **one instruction literal drives
two registers**: EEPROM `1210 = 1f`, operand of `MOV A,#1f` at CODE `020f`,
is written to XDATA `01ec` at `0211` and `01f1` at `0215`. No second load occurs
between them. A one-byte instruction patch therefore changes both together.
Their following registers `01ed` and `01f2` independently receive profile bytes
8 and 9, both initially `03`. This establishes repeated software organization
with a five-register stride. It does **not** establish that the groups represent
the two LVDS ports or that any bit selects JEIDA.

## Generated families

| Family | Images | What execution establishes |
|---|---:|---|
| Matched bits in profile 3/4 → `01e1/01e2` | 8 | Seven mutable bit positions; bit 0 starts unequal, so both-zero and both-one are distinct tests. Forced bit 3 is excluded. |
| Matched bits in profile 8/9 → `01ed/01f2` | 8 | Simultaneous changes reach both registers and recur after recovery. |
| Matched bits in the two nibbles of profile 10 → `01f3` | 4 | Baseline `44` can be changed symmetrically; the nibble interpretation remains speculative. |
| Matched high-bit sources: profile 11 and global `1122` → `01f4` | 4 | Both sources OR together. This is one output field with two sources, not proof of separate port controls. |
| Fixed instruction operands | 32 | Eight bit flips each at physical `1210`, `121a`, `1286`, `12bb`. |

Baseline-identical assignments were discarded. “Additional images” does not
mean 56 additional independent selector bits: some effects overlap the previous
single-bit experiments, and both-zero/both-one tests can change only one member
of an initially asymmetric pair.

| EEPROM operand | Original | Destination(s) | Boot write CODE address(es) |
|---|---|---|---|
| `1210` | `1f` | `01ec`, `01f1` | `0211`, `0215` |
| `121a` | `ff` | `01f5` | `021b` |
| `1286` | `30` | `01bc` | `0287` |
| `12bb` | `58` | `01da` | `02bc` |

Selection of these four literals is a bounded search around opaque register
configuration, not evidence that their hardware functions are colour related.

## Literal audit and verification

The audit flips every bit of every `MOV A,#immediate` in CODE `01c0..02c1`
that is reached under the normal or alternate global-`111e` branch:
**24 distinct instruction operands, 352 executions**, including repeated
checks of common instructions under both branches. All retain their respective
control-flow coverage. Exact changed write PCs, registers and values are saved.
This audit is limited to that opcode and region; it excludes `CLR A`, immediate
masks, SFR initialization, later recovery constants and other code regions.

All 56 generated images:

- Preserve EEPROM `0000..0fff`, including the patched EDIDs and opaque blocks.
- Reach the link loop under synthetic readiness inputs, with unchanged boot coverage.
- Keep the ordered write destinations and PCs unchanged; changed values are recorded.
- Are checked with profile straps 0 and 15, with all 16 profile records patched consistently.
- Execute a video-ready loss, shutdown and return to the link loop.

Fixed initialization writes do not recur during this recovery path. The emulator
retains their values because its XDATA memory has no autonomous peripheral reset.
Profile writes recur. This distinction matters when interpreting real recovery
behaviour, which remains unmeasured.

Eight representative images additionally match **all 2,048 XDATA bytes** after
boot in the independent uCsim CPU emulator. Both tools use synthetic peripherals;
agreement verifies CPU interpretation, not the electrical effects of the writes.

## What this changes about the selector search

1. Treat the `01ec/01ed` and `01f1/01f2` groups as a concrete paired-configuration
   hypothesis. A profile-only search never changes their shared `1f` literal.
2. For `01e1/01e2`, test equal assignments separately from swapping the original
   asymmetry. Bit 3 is explicitly forced opposite by instructions, so changing
   it requires a separate mask/instruction experiment. The present images leave
   that forced relationship intact.
3. Do not interpret profile 11/global `1122` as independently selectable controls:
   either source can hold a high bit set. Clearing only one source can be ineffective.
4. Do not rank a bit as JEIDA merely because changing it leaves firmware execution
   intact. The candidate registers are opaque to the CPU; this outcome is expected
   for many unrelated peripheral functions.

**No colour-format selector has been identified.** These tests expand and make
precise the firmware-accessible hypotheses. They cannot assign serializer
semantics to an unread hardware bit. The next firmware-only discrimination would
require another labelled initialization/configuration, a utility/register map,
or additional code that interprets these fields. Arbitrary extra bit combinations
in the same memory-only peripheral model will not supply that missing evidence.

## Reproduce / artifacts

Run from the workspace root:

```sh
python3 scripts/cs5211_register_structure.py
```

- `artifacts/cs5211-register-structure/candidates.json`: patches, hashes, boot/recovery deltas.
- `artifacts/cs5211-register-structure/candidates/`: generated 8 KiB images.
- `artifacts/cs5211-register-structure/literal-audit.json`: complete literal bit audit.
- `artifacts/cs5211-register-structure/baseline.json`: baseline traces and register memory.
- `artifacts/cs5211-register-structure/independent-checks.json`: independent comparison results.
- `artifacts/cs5211-register-structure/independent/`: uCsim output.

No images were flashed and no repository changes were published.
