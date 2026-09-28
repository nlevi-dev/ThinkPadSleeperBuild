# CS5211 firmware investigation archive

**Start with [the solution retrospective](SOLUTION.md).** It compares Levi's
working commit `93c5c9f` with the earlier firmware-only investigation and gives
the shortest evidence-based route from the instructions to the solution.

## Current conclusion

For the published image, profile byte 3 changes `01 → 05` in all 16 profiles,
selecting JEIDA through **XDATA `01e1.bit2`**. The integrity field at
`0ffa..0ffd` changes `1b6caac2 → da960552`. The existing upstream patcher
reproduces the committed solution exactly. Its four mode labels also identify
`01e1.bit1` as 6-versus-8 bits per component in those configurations.

Our earlier `candidate-p03-bit2` made the correct profile edit, but omitted the
checksum change. The CPU emulator starts after image loading and therefore
could not distinguish it from the working image. Historical "boot passed"
results must be read as CPU execution under synthetic inputs, not image
acceptance or display tests.

## Findings and chronology

The reports below are historical snapshots, including hypotheses later corrected.
The retrospective takes precedence for current conclusions.

| Report | Contents |
|---|---|
| [Initial ROM analysis](notes/cs5211-rom.md) | Layout, EDID copies, code discovery. |
| [Firmware map](notes/cs5211-firmware-map.md) | GPIO-selected profiles, destination registers and instruction addresses. |
| [Independent reassessment](notes/cs5211-reassessment-2026-09-28.md) | Corrections to earlier assumptions, diagnostic patterns, opaque-block layout. |
| [CPU black-box experiments](notes/cs5211-blackbox-2026-09-28.md) | 2,267 synthetic-input experiments, clock/PWM/initialization mapping and 21 independent CPU comparisons. |
| [Five-stage investigation](notes/cs5211-deep-investigation-2026-09-28.md) | Coverage, configuration dependencies, opaque-block tests, readable model, 93 single-bit candidates. |
| [Register-structure follow-up](notes/cs5211-register-structure-2026-09-28.md) | 56 coupled/literal candidates, 352 literal mutations, link recovery and 8 independent comparisons. |
| [Solution retrospective](SOLUTION.md) | Exact solved-ROM diff, selector provenance, acceptance blind spot, checksum-difference model, better investigation sequence. |

Retained results include 1,190/1,191 executed application instructions with an
explicit infeasibility analysis of the remaining instruction, 33,354 matched
foreground register events, 2,048 wide-domain clock cases and 44 ISR cases.
These measure the reconstructed application, not silicon/peripheral fidelity.

## Reproduce the solution comparison

Requirements: Python 3.10+, clang. The minimal MIT-licensed emu8051 CPU core is
vendored under `tools/emu8051` at commit
`5dc681275151c4a5d7b85ec9ff4ceb1b25abd5a8`, unchanged. The harness uses a dynamic
library and was exercised on macOS ARM; `.so` naming is also provided for Linux,
which has not been tested here.

From the repository root:

```sh
cd Screen/DumpROM/analysis
python3 scripts/cs5211_solution.py
python3 scripts/cs5211_checksum_probe.py
```

The first command builds the core adapter, reproduces the solved ROM with the
upstream patcher, compares all 16 straps, verifies the exact disassembly bytes,
checks the old candidate hash, and tests all four reported checksums against the
CRC-difference hypothesis. It does not flash or access hardware.

## Reproduce earlier CPU campaigns

The original and EDID-only images are pinned in `binaries/` so comparisons do not
silently use the newly solved ROM. The old generator paths have been adapted to
these snapshots. Ghidra listings are included; running Ghidra is unnecessary for
these tests. Ghidra annotation/export Java scripts are provided for further work.

After the build performed above:

```sh
python3 scripts/cs5211_campaign.py
python3 scripts/cs5211_crosscheck.py
python3 scripts/cs5211_deep.py
python3 scripts/cs5211_dependencies.py
python3 scripts/cs5211_opaque.py
python3 scripts/cs5211_verify_model.py
python3 scripts/cs5211_validate_deep.py
```

The crosscheck and validation scripts additionally need `s51` (uCsim); archived
results were obtained with uCsim 0.9.9 / SDCC 4.6.0. The emulator core and readable
model implement no real CS5211 serializer, boot validation or autonomous
peripheral reset behavior. Some supplied status transitions are synthetic and
not demonstrated on hardware.

Optional historical candidate reproduction:

```sh
python3 scripts/cs5211_candidates.py
python3 scripts/cs5211_register_structure.py
```

**Those images retain the old firmware checksum. They are for CPU experiments.**
They are not the output of the working `../patch_cs5211.py`, and are not included
as flash binaries in this PR. Candidate manifests preserve their hashes and
patches. Likewise, `scripts/patch_cs5211_profile.py` is an older profile-only
experiment helper, not a replacement for the upstream solved-image patcher.

To regenerate diagnostic PNGs, install Pillow and run
`python3 scripts/cs5211_diagnostic_pattern.py artifacts/diagnostics`.
The existing PNGs are included under `artifacts/cs5211-review-2026-09-28/`.
There are no recorded physical results from those patterns.

## Evidence layout

- `artifacts/cs5211-review-2026-09-28/`: disassembly, static audit, datasheet text,
  diagnostic patterns and reference utility screenshots.
- `artifacts/cs5211-blackbox/`: first CPU campaign and independent uCsim outputs.
- `artifacts/cs5211-deep/`: application coverage, dependency catalogue, model
  comparisons, opaque-data tests and the 93-candidate manifest.
- `artifacts/cs5211-register-structure/`: paired/literal experiment manifest,
  fixed-immediate audit, baseline/recovery traces and independent checks.
- `artifacts/cs5211-solution/`: freshly reproduced comparison with Levi's solution.
- `MANIFEST.json`: hashes of the packaged files. Historical tool outputs can
  contain paths from the original workspace; they are evidence, not setup paths.

Generated libraries, caches, candidate binaries/ZIPs and Ghidra project databases
are excluded. Existing repository PDFs are not duplicated. No flashing harness,
credentials or network/device-control code is included in this analysis package.

The small documentation edits in [lvds.md](../../lvds.md) correct
EDID/profile range arithmetic and distinguish this solution from a complete
hardware register map. The solved firmware and production patcher are unchanged.
