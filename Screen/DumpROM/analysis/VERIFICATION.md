# Verification when preparing this PR

2026-09-28, against solution commit `93c5c9f2e0772ec6089b54aa51863dafe25a8505`.
Commands run from `Screen/DumpROM/analysis` unless noted otherwise.

| Command/check | Result |
|---|---|
| `python3 scripts/cs5211_solution.py` | Rebuilt the vendored emulator; upstream patcher reproduced solved ROM exactly; all 16 profile straps matched expectations; old candidate hash matched the historical manifest; all four table checksums matched the differential hypothesis. |
| `python3 scripts/cs5211_verify_model.py` | 262 foreground traces / 33,354 ordered events; 2,048 clock cases; 44 timer cases passed. |
| `python3 scripts/cs5211_validate_deep.py` | Coverage classification assertions passed; 8 configurations matched model/emu8051/uCsim over all 2,048 XDATA bytes. |
| `python3 scripts/cs5211_checksum_probe.py` | No absolute checksum match within its enumerated hypotheses; differential matches saved in `artifacts/cs5211-solution/checksum-probe.txt`. |
| Python compilation | All packaged Python scripts compiled. |
| Markdown relative-link check | No broken relative links in the analysis package. |
| `git diff --cached --check` excluding `artifacts/` and `tools/` | Passed for authored content. Raw tool outputs and unchanged vendored code retain upstream trailing whitespace. |

Other historical results were collected during the earlier investigation and
are included with their scripts. They were not all rerun just to package this
PR. Candidate binaries, ZIPs, runtime caches and compiled libraries are excluded.

No physical display, ROM flashing, remote power control or upstream merge was
performed. No general checksum algorithm or universal register map is claimed.
