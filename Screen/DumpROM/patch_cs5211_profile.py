#!/usr/bin/env python3
"""Create controlled CS5211 LVDS-profile test dumps.

The firmware copies 12 bytes from each profile at ROM 0x1010 + profile*0x10
into its output-configuration XDATA registers. This changes selected bytes in
all 16 records while leaving EDID and the rest of the ROM untouched.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROM_SIZE = 8192
PROFILE_BASE = 0x1010
PROFILE_STRIDE = 0x10
PROFILE_COUNT = 16


def load_dump(path: Path) -> bytearray:
    return bytearray(int(token, 16) for line in path.read_text().splitlines() for token in line.split())


def parse_assignment(text: str) -> tuple[int, int]:
    try:
        raw_offset, raw_value = text.split("=", 1)
        offset, value = int(raw_offset, 0), int(raw_value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError("use OFFSET=VALUE, e.g. 0x0a=0x45") from error
    if not 0 <= offset < 12 or not 0 <= value <= 0xFF:
        raise argparse.ArgumentTypeError("offset must be 0x00..0x0b and value 0x00..0xff")
    return offset, value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--set", action="append", type=parse_assignment, required=True, metavar="OFFSET=VALUE")
    args = parser.parse_args()

    rom = load_dump(args.input)
    if len(rom) != ROM_SIZE:
        parser.error(f"expected {ROM_SIZE} bytes, found {len(rom)}")
    assignments = dict(args.set)
    for profile in range(PROFILE_COUNT):
        base = PROFILE_BASE + profile * PROFILE_STRIDE
        for offset, value in assignments.items():
            rom[base + offset] = value
    args.output.write_text("".join(
        " ".join(f"{value:02X}" for value in rom[offset : offset + 16]) + "\n"
        for offset in range(0, ROM_SIZE, 16)
    ))
    print(f"wrote {args.output}; changed {len(assignments)} byte(s) in every profile")


if __name__ == "__main__":
    main()
