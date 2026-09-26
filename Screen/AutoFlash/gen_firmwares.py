#!/usr/bin/env python3
"""
Generate all plausible firmware variants for the CS5211 VESA→JEIDA / color format fix.

The EEPROM layout:
  0x0000-0x07FF  16 x 128-byte EDID copies (all identical)
  0x0800-0x0FFF  Gamma/dither LUT (scrambled, not touched)
  0x0FFA-0x100F  Config header
  0x1010-0x110F  16 x 16-byte slot config table (all identical)
  0x1110-0x111F  Trailer
  0x1120+        8051 code

The firmware reads config from code memory (= EEPROM) at these key addresses:
  0x011E  Green y high bits  -> LSB = VESA(0) / JEIDA(1) select
  0x0122  White y high bits  -> used for color format / bit depth
  0x0112  EDID version byte  -> lane / format config (read 5x)
  0x011B  Red x high bits    -> resolution select
  0x011C  Red y high bits    -> timing
  0x011D  Green x high bits  -> timing
  0x011F  Blue x high bits   -> timing
  0x0120  Blue y high bits   -> timing
  0x0121  White x high bits  -> timing
  0x0114  Video input def    -> input config
  0x0117  Display gamma      -> gamma config
  0x0118  Feature support    -> feature flags
  0x0119  Red/green low bits -> color calibration
  0x011A  Blue/white low bits-> color calibration

  Slot table (0x1010, replicated x16):
    byte 10 (0x44)  -> primary format/depth config byte
    byte  8 (0x03)  -> LVDS port / lane config
    byte  9 (0x03)  -> LVDS format flags
    byte 11 (0x04)  -> backlight / PWM config
    bytes 0,3       -> enable / output flags
    bytes 4,7       -> link config

Variant groups generated:
  A  Single-bit flips of the 16-byte slot block (128 variants) - baseline
  B  EDID[0x1E] LSB flip - the confirmed VESA/JEIDA bit (1 variant)
  C  EDID[0x1E] all 8 single-bit flips (8 variants)
  D  EDID[0x22] all 8 single-bit flips - color format byte (8 variants)
  E  EDID[0x12] all 8 single-bit flips - heavily-used lane/format byte (8 variants)
  F  Slot byte 10 exhaustive sweep: all 256 values (256 variants)
  G  Slot byte 9 exhaustive sweep: all 256 values (256 variants)
  H  Slot byte 8 exhaustive sweep: all 256 values (256 variants)
  I  Slot byte 11 exhaustive sweep: all 256 values (256 variants)
  J  Slot bytes 8+9 combined: all 4-bit-range combos (16x16=256 variants)
  K  Slot bytes 10+9 combined: all 256 combos of the two format bytes (256 variants)
  L  EDID[0x1E]+slot_byte10 combined: 2x256 = 512 variants (JEIDA bit x all byte10)
  M  Header bytes single-bit flips (0x1000-0x100F, 16 bytes = 128 variants)
  N  Trailer bytes single-bit flips (0x1110-0x111F, 16 bytes = 128 variants)
  O  EDID[0x14] (video input def) all 8 bits (8 variants)
  P  EDID[0x18] (feature support) all 8 bits (8 variants)

Total: 128+1+8+8+8+256+256+256+256+256+256+512+128+128+8+8 = 2477 variants
"""
import os
import sys

FIRMWARE_PATCHED = os.path.join(os.path.dirname(__file__), "../DumpROM/dump_CS5211_patched.txt")
FIRMWARE_BROKEN  = os.path.join(os.path.dirname(__file__), "../DumpROM/dump_broken.txt")
FIRMWARE         = FIRMWARE_PATCHED  # base for all variants
OUT_DIR          = os.path.join(os.path.dirname(__file__), "firmwares")
SLOT_ADDR   = 0x1010
SLOT_LEN    = 16
SLOT_COPIES = 16
EDID_COPIES = 16
EDID_LEN    = 128

def load_rom(path):
    rom = bytearray()
    with open(path) as f:
        for line in f:
            for b in line.strip().split():
                rom.append(int(b, 16))
    return rom

def save_rom(rom, path):
    with open(path, "w") as f:
        for i in range(0, len(rom), 16):
            f.write(" ".join(f"{b:02X}" for b in rom[i:i+16]) + "\n")

def set_slot(rom, new_block):
    """Write new_block to all 16 slot copies."""
    rom = bytearray(rom)
    assert len(new_block) == SLOT_LEN
    for i in range(SLOT_COPIES):
        rom[SLOT_ADDR + i*SLOT_LEN : SLOT_ADDR + i*SLOT_LEN + SLOT_LEN] = new_block
    return rom

def set_edid_byte(rom, offset, value):
    """Write value to the given byte offset in all 16 EDID copies."""
    rom = bytearray(rom)
    for i in range(EDID_COPIES):
        rom[i*EDID_LEN + offset] = value
    return rom

def slot_byte(rom, idx):
    return rom[SLOT_ADDR + idx]

def edid_byte(rom, offset):
    return rom[offset]  # slot 0

def emit(variants, rom, label, description):
    variants.append((label, description, bytearray(rom)))

def generate(base_rom):
    variants = []
    slot = base_rom[SLOT_ADDR : SLOT_ADDR + SLOT_LEN]

    # ── A: single-bit flips of slot block ────────────────────────────────────
    for bit in range(SLOT_LEN * 8):
        new_slot = bytearray(slot)
        new_slot[bit // 8] ^= (1 << (bit % 8))
        rom = set_slot(base_rom, new_slot)
        emit(variants, rom, f"A{bit:03d}",
             f"slot_bit_flip bit={bit} byte={bit//8} mask={1<<(bit%8):#04x} "
             f"0x{slot[bit//8]:02X}->0x{new_slot[bit//8]:02X}")

    # ── B: confirmed VESA/JEIDA bit (EDID[0x1E] LSB) ─────────────────────────
    orig = edid_byte(base_rom, 0x1E)
    rom = set_edid_byte(base_rom, 0x1E, orig ^ 0x01)
    emit(variants, rom, "B000",
         f"JEIDA_bit EDID[0x1E] 0x{orig:02X}->0x{orig^1:02X} (LSB flip)")

    # ── C: all 8 bits of EDID[0x1E] (green y / VESA-JEIDA byte) ─────────────
    orig = edid_byte(base_rom, 0x1E)
    for bit in range(8):
        nv = orig ^ (1 << bit)
        rom = set_edid_byte(base_rom, 0x1E, nv)
        emit(variants, rom, f"C{bit:03d}",
             f"EDID[0x1E]_bit{bit} 0x{orig:02X}->0x{nv:02X}")

    # ── D: all 8 bits of EDID[0x22] (white y / color format byte) ────────────
    orig = edid_byte(base_rom, 0x22)
    for bit in range(8):
        nv = orig ^ (1 << bit)
        rom = set_edid_byte(base_rom, 0x22, nv)
        emit(variants, rom, f"D{bit:03d}",
             f"EDID[0x22]_bit{bit} 0x{orig:02X}->0x{nv:02X}")

    # ── E: all 8 bits of EDID[0x12] (version / lane-format byte, read 5x) ────
    orig = edid_byte(base_rom, 0x12)
    for bit in range(8):
        nv = orig ^ (1 << bit)
        rom = set_edid_byte(base_rom, 0x12, nv)
        emit(variants, rom, f"E{bit:03d}",
             f"EDID[0x12]_bit{bit} 0x{orig:02X}->0x{nv:02X}")

    # ── F: slot byte 10 exhaustive (0x00-0xFF) ────────────────────────────────
    for v in range(256):
        new_slot = bytearray(slot); new_slot[10] = v
        rom = set_slot(base_rom, new_slot)
        emit(variants, rom, f"F{v:03d}",
             f"slot[10]=0x{v:02X} (was 0x{slot[10]:02X})")

    # ── G: slot byte 9 exhaustive ─────────────────────────────────────────────
    for v in range(256):
        new_slot = bytearray(slot); new_slot[9] = v
        rom = set_slot(base_rom, new_slot)
        emit(variants, rom, f"G{v:03d}",
             f"slot[9]=0x{v:02X} (was 0x{slot[9]:02X})")

    # ── H: slot byte 8 exhaustive ─────────────────────────────────────────────
    for v in range(256):
        new_slot = bytearray(slot); new_slot[8] = v
        rom = set_slot(base_rom, new_slot)
        emit(variants, rom, f"H{v:03d}",
             f"slot[8]=0x{v:02X} (was 0x{slot[8]:02X})")

    # ── I: slot byte 11 exhaustive ────────────────────────────────────────────
    for v in range(256):
        new_slot = bytearray(slot); new_slot[11] = v
        rom = set_slot(base_rom, new_slot)
        emit(variants, rom, f"I{v:03d}",
             f"slot[11]=0x{v:02X} (was 0x{slot[11]:02X})")

    # ── J: slot bytes 8+9 combined (all 256 nibble-range combos) ─────────────
    # Both are currently 0x03; sweep all 16 values for each (4-bit meaningful range)
    for v8 in range(16):
        for v9 in range(16):
            new_slot = bytearray(slot); new_slot[8] = v8; new_slot[9] = v9
            rom = set_slot(base_rom, new_slot)
            emit(variants, rom, f"J{v8:02d}{v9:02d}",
                 f"slot[8]=0x{v8:02X} slot[9]=0x{v9:02X}")

    # ── K: slot bytes 10+9 combined (format byte pair) ───────────────────────
    for v10 in range(256):
        for v9 in range(16):
            new_slot = bytearray(slot); new_slot[10] = v10; new_slot[9] = v9
            rom = set_slot(base_rom, new_slot)
            emit(variants, rom, f"K{v10:03d}{v9:02d}",
                 f"slot[10]=0x{v10:02X} slot[9]=0x{v9:02X}")

    # ── L: EDID[0x1E] JEIDA bit x all slot byte 10 values ────────────────────
    orig_1e = edid_byte(base_rom, 0x1E)
    for jeida in range(2):
        new_1e = (orig_1e & 0xFE) | jeida
        for v10 in range(256):
            new_slot = bytearray(slot); new_slot[10] = v10
            rom = set_slot(base_rom, new_slot)
            rom = set_edid_byte(rom, 0x1E, new_1e)
            emit(variants, rom, f"L{jeida}{v10:03d}",
                 f"EDID[0x1E]=0x{new_1e:02X}(jeida={jeida}) slot[10]=0x{v10:02X}")

    # ── M: header bytes single-bit flips (0x1000-0x100F) ─────────────────────
    for byte_off in range(16):
        addr = 0x1000 + byte_off
        orig = base_rom[addr]
        for bit in range(8):
            nv = orig ^ (1 << bit)
            rom = bytearray(base_rom)
            rom[addr] = nv
            emit(variants, rom, f"M{byte_off:02d}{bit}",
                 f"header[0x{addr:04X}]_bit{bit} 0x{orig:02X}->0x{nv:02X}")

    # ── N: trailer bytes single-bit flips (0x1110-0x111F) ────────────────────
    for byte_off in range(16):
        addr = 0x1110 + byte_off
        orig = base_rom[addr]
        for bit in range(8):
            nv = orig ^ (1 << bit)
            rom = bytearray(base_rom)
            rom[addr] = nv
            emit(variants, rom, f"N{byte_off:02d}{bit}",
                 f"trailer[0x{addr:04X}]_bit{bit} 0x{orig:02X}->0x{nv:02X}")

    # ── O: EDID[0x14] all 8 bits (video input definition) ────────────────────
    orig = edid_byte(base_rom, 0x14)
    for bit in range(8):
        nv = orig ^ (1 << bit)
        rom = set_edid_byte(base_rom, 0x14, nv)
        emit(variants, rom, f"O{bit:03d}",
             f"EDID[0x14]_bit{bit} 0x{orig:02X}->0x{nv:02X}")

    # ── P: EDID[0x18] all 8 bits (feature support) ───────────────────────────
    orig = edid_byte(base_rom, 0x18)
    for bit in range(8):
        nv = orig ^ (1 << bit)
        rom = set_edid_byte(base_rom, 0x18, nv)
        emit(variants, rom, f"P{bit:03d}",
             f"EDID[0x18]_bit{bit} 0x{orig:02X}->0x{nv:02X}")

    return variants

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    base_rom   = load_rom(FIRMWARE_PATCHED)
    broken_rom = load_rom(FIRMWARE_BROKEN)

    # Sanity check entries: patched, broken, patched (indices 0, 1, 2)
    # These let you verify the flash+power-cycle loop works before the real run.
    # Expected: 0=correct geometry/wrong colors, 1=wrong geometry, 2=correct geometry/wrong colors
    sanity = [
        ("S000", "sanity_patched_1  expect: correct geometry, wrong colors", bytearray(base_rom)),
        ("S001", "sanity_broken     expect: wrong geometry (1920x1080 EDID)",  bytearray(broken_rom)),
        ("S002", "sanity_patched_2  expect: correct geometry, wrong colors", bytearray(base_rom)),
    ]

    print("Generating variants...", flush=True)
    variants = generate(base_rom)

    # Deduplicate variants: skip anything identical to base or already seen
    seen = {bytes(base_rom), bytes(broken_rom)}
    unique = []
    for label, desc, rom in variants:
        key = bytes(rom)
        if key not in seen:
            seen.add(key)
            unique.append((label, desc, rom))

    print(f"Total unique variants (excluding base): {len(unique)}")

    # Write: 000000=sanity_patched_1, 000001=sanity_broken, 000002=sanity_patched_2, then variants
    index_file = os.path.join(OUT_DIR, "index.txt")
    with open(index_file, "w") as idx:
        idx.write(f"{'#':>6}  {'label':<12}  description\n")
        all_entries = sanity + [(l, d, r) for l, d, r in unique]
        for i, (label, desc, rom) in enumerate(all_entries):
            save_rom(rom, os.path.join(OUT_DIR, f"{i:06d}.txt"))
            idx.write(f"{i:6d}  {label:<12}  {desc}\n")

    print(f"Written to {OUT_DIR}/")
    print(f"Index:     {index_file}")

if __name__ == "__main__":
    main()
