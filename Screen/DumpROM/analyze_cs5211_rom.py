#!/usr/bin/env python3
"""Summarize the layout of a text-format CS5211 serial-ROM dump."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

EDID_SIZE = 128
ROM_SIZE = 8192
FIRMWARE_OFFSET = 0x1000
PROFILE_BASE = 0x1010
PROFILE_COUNT = 16
PROFILE_SIZE = 16


def load_hex_dump(path: Path) -> bytes:
    values: list[int] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        for token in line.split():
            try:
                value = int(token, 16)
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: invalid byte {token!r}") from exc
            if not 0 <= value <= 0xFF:
                raise ValueError(f"{path}:{line_number}: byte out of range {token!r}")
            values.append(value)
    return bytes(values)


def edid_pnp_id(edid: bytes) -> str:
    encoded = int.from_bytes(edid[8:10], "big")
    return "".join(chr(((encoded >> shift) & 0x1F) + 64) for shift in (10, 5, 0))


def monotonic_lut_lengths(data: bytes) -> list[int]:
    lengths = [16, 32, 64, 128, 256]
    found: list[int] = []
    for length in lengths:
        for offset in range(len(data) - length + 1):
            candidate = data[offset : offset + length]
            if len(set(candidate)) >= length // 2 and all(
                candidate[index] <= candidate[index + 1]
                for index in range(length - 1)
            ):
                found.append(length)
                break
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path, help="16-byte-per-line hexadecimal ROM dump")
    args = parser.parse_args()

    rom = load_hex_dump(args.dump)
    if len(rom) != ROM_SIZE:
        raise SystemExit(f"expected {ROM_SIZE} bytes, found {len(rom)}")

    edid = rom[:EDID_SIZE]
    copies = 0
    while rom[copies * EDID_SIZE : (copies + 1) * EDID_SIZE] == edid:
        copies += 1

    firmware = rom[FIRMWARE_OFFSET:]
    last_nonzero = max(index for index, value in enumerate(firmware) if value)
    firmware = firmware[: last_nonzero + 1]

    product_id = int.from_bytes(edid[10:12], "little")
    serial = int.from_bytes(edid[12:16], "little")
    print(f"ROM SHA-256: {hashlib.sha256(rom).hexdigest()}")
    print(f"EDID copies: {copies} ({copies * EDID_SIZE:#06x} bytes)")
    print(f"EDID checksum: {'valid' if sum(edid) % 256 == 0 else 'INVALID'}")
    print(
        "EDID identity: "
        f"PNP {edid_pnp_id(edid)!r}, product 0x{product_id:04X}, "
        f"serial {serial}, week {edid[16]} of {1990 + edid[17]}"
    )
    print(
        f"8051 firmware: ROM {FIRMWARE_OFFSET:#06x}–"
        f"{FIRMWARE_OFFSET + last_nonzero:#06x} ({len(firmware)} bytes)"
    )
    print(f"8051 reset vector: {firmware[:3].hex(' ')}")
    print("panel constants: firmware 0x0110–0x0122 (ROM 0x1110–0x1122)")
    profiles = [
        rom[PROFILE_BASE + profile * PROFILE_SIZE : PROFILE_BASE + (profile + 1) * PROFILE_SIZE]
        for profile in range(PROFILE_COUNT)
    ]
    print(f"GPIO profile records: {PROFILE_COUNT}; unique records: {len(set(profiles))}")
    print("profile[0]: " + profiles[0].hex(" "))
    luts = monotonic_lut_lengths(firmware)
    print("monotonic LUT candidates: " + (str(luts) if luts else "none"))

    hashes = Counter(
        hashlib.sha256(rom[offset : offset + EDID_SIZE]).hexdigest()
        for offset in range(0, len(rom), EDID_SIZE)
    )
    print(f"unique 128-byte pages: {len(hashes)}")


if __name__ == "__main__":
    main()
