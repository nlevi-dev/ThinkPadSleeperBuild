#!/usr/bin/env python3
"""Create controlled CS5211 LVDS-profile test images.

The CS5211 firmware copies 12 profile bytes from each 16-byte record at serial
ROM 0x1010 + profile*0x10 into the bridge's output-configuration XDATA block.
This tool changes selected profile bytes in every profile record so the active
GPIO strap cannot affect a test result. It never changes EDID or code outside
those records.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROM_SIZE = 8192
PROFILE_BASE = 0x1010
PROFILE_STRIDE = 0x10
PROFILE_COUNT = 16
WRITABLE_BYTES = range(12)


def parse_assignment(text: str) -> tuple[int, int]:
    try:
        raw_offset, raw_value = text.split("=", 1)
        offset = int(raw_offset, 0)
        value = int(raw_value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError("use OFFSET=VALUE, e.g. 0x0a=0x45") from error
    if offset not in WRITABLE_BYTES:
        raise argparse.ArgumentTypeError("profile offset must be in 0x00..0x0b")
    if not 0 <= value <= 0xFF:
        raise argparse.ArgumentTypeError("profile value must be in 0x00..0xff")
    return offset, value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="8 KiB binary serial-ROM image")
    parser.add_argument("output", type=Path, help="new binary or --text hex-dump image")
    parser.add_argument(
        "--set",
        action="append",
        type=parse_assignment,
        required=True,
        metavar="OFFSET=VALUE",
        help="set a profile byte in every profile; repeat as needed",
    )
    parser.add_argument("--text", action="store_true", help="write 16-byte-per-line hexadecimal text")
    args = parser.parse_args()
    print("CPU EXPERIMENT ONLY: this helper does not repair the firmware checksum.")

    rom = bytearray(args.input.read_bytes())
    if len(rom) != ROM_SIZE:
        parser.error(f"expected an {ROM_SIZE}-byte image, found {len(rom)} bytes")

    assignments = dict(args.set)
    for profile in range(PROFILE_COUNT):
        record = PROFILE_BASE + profile * PROFILE_STRIDE
        for offset, value in assignments.items():
            rom[record + offset] = value

    if args.text:
        args.output.write_text("".join(
            " ".join(f"{byte:02X}" for byte in rom[offset : offset + 16]) + "\n"
            for offset in range(0, ROM_SIZE, 16)
        ))
    else:
        args.output.write_bytes(rom)

    changed = ", ".join(f"+{offset:#04x}={value:#04x}" for offset, value in assignments.items())
    print(f"wrote {args.output}: {changed} in all {PROFILE_COUNT} profile records")


if __name__ == "__main__":
    main()
