#!/usr/bin/env python3
"""Decode the internal-RAM initialization stream used by CS5211 reset code."""

from __future__ import annotations

from pathlib import Path

FIRMWARE = Path(__file__).resolve().parents[1] / "binaries" / "cs5211-8051-firmware.bin"
TABLE_START = 0x0E1F


def main() -> None:
    firmware = FIRMWARE.read_bytes()
    cursor = TABLE_START
    ram: dict[int, int] = {}
    while True:
        header = firmware[cursor]
        cursor += 1
        if header == 0:
            break
        if header & 0xC0:
            raise ValueError(f"unsupported record class {header:#04x} at {cursor - 1:#06x}")
        length = header & 0x3F
        address = firmware[cursor]
        cursor += 1
        values = firmware[cursor : cursor + length]
        cursor += length
        for offset, value in enumerate(values):
            ram[address + offset] = value
        print(
            f"firmware {cursor - length - 2:#06x}: RAM {address:#04x}–"
            f"{address + length - 1:#04x} = {values.hex(' ')}"
        )
    print(f"terminator: firmware {cursor - 1:#06x}")
    print("final initialized RAM:")
    print(" ".join(f"{address:02x}={value:02x}" for address, value in sorted(ram.items())))


if __name__ == "__main__":
    main()
