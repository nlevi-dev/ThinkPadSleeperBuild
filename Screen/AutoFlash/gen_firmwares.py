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

Categories:
  edid            - EDID byte 0x14 variants (6 variants)
                    v14: version bump only
                    v14_6bit: version + 6-bit depth
                    v14_6bit_VESA / v14_6bit_JEIDA
                    v14_8bit_VESA / v14_8bit_JEIDA
  slot_single     - Single-bit flips of the 16-byte slot block (128 variants)
  header          - Single-bit flips of config header 0x1000-0x100F (128 variants)
  slot_exhaustive - Exhaustive sweep of slot bytes 8, 9, 10, 11 (4x255 variants)

Filename format: {number:06d}_{category}_{description}.txt
"""
import os

FIRMWARE_PATCHED = os.path.join(os.path.dirname(__file__), "../DumpROM/dump_CS5211_patched.txt")
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

def edid_byte(rom, offset):
    return rom[offset]

def fix_edid_checksum(rom):
    rom = bytearray(rom)
    for i in range(EDID_COPIES):
        base = i * EDID_LEN
        rom[base + 0x7F] = (256 - sum(rom[base:base+0x7F]) % 256) % 256
    return rom

def emit(variants, rom, category, description):
    variants.append((category, description, bytearray(rom)))

def generate(base_rom):
    variants = []
    slot = base_rom[SLOT_ADDR : SLOT_ADDR + SLOT_LEN]

    # ── edid ─────────────────────────────────────────────────────────────────
    # byte 0x14 bits [6:4]: depth  001=6bit 010=8bit
    # byte 0x14 bits [3:0]: iface  0101=VESA 0110=JEIDA
    def edid_variant(byte14):
        rom = set_edid_byte(base_rom, 0x13, 0x04)
        rom = set_edid_byte(rom, 0x14, byte14)
        return fix_edid_checksum(rom)

    emit(variants, edid_variant(0x80), "edid", "v14")
    emit(variants, edid_variant(0x90), "edid", "v14_6bit")
    emit(variants, edid_variant(0x95), "edid", "v14_6bit_VESA")
    emit(variants, edid_variant(0x96), "edid", "v14_6bit_JEIDA")
    emit(variants, edid_variant(0xA5), "edid", "v14_8bit_VESA")
    emit(variants, edid_variant(0xA6), "edid", "v14_8bit_JEIDA")

    # ── slot_single ───────────────────────────────────────────────────────────
    for bit in range(SLOT_LEN * 8):
        new_slot = bytearray(slot)
        new_slot[bit // 8] ^= (1 << (bit % 8))
        rom = set_slot(base_rom, new_slot)
        emit(variants, rom, "slot_single",
             f"bit{bit:03d}_byte{bit//8}_0x{slot[bit//8]:02X}to0x{new_slot[bit//8]:02X}")

    # ── header ────────────────────────────────────────────────────────────────
    for byte_off in range(16):
        addr = 0x1000 + byte_off
        orig = base_rom[addr]
        for bit in range(8):
            nv = orig ^ (1 << bit)
            rom = bytearray(base_rom)
            rom[addr] = nv
            emit(variants, rom, "header",
                 f"addr0x{addr:04X}_bit{bit}_0x{orig:02X}to0x{nv:02X}")

    # ── slot_exhaustive ───────────────────────────────────────────────────────
    for byte_idx, byte_name in [(8, "byte8"), (9, "byte9"), (10, "byte10"), (11, "byte11")]:
        orig = slot[byte_idx]
        for v in range(256):
            if v == orig:
                continue
            new_slot = bytearray(slot)
            new_slot[byte_idx] = v
            rom = set_slot(base_rom, new_slot)
            emit(variants, rom, "slot_exhaustive", f"{byte_name}_0x{v:02X}")

    return variants

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    base_rom = load_rom(FIRMWARE_PATCHED)

    print("Generating variants...", flush=True)
    variants = generate(base_rom)

    seen = {bytes(base_rom)}
    unique = []
    for cat, desc, rom in variants:
        key = bytes(rom)
        if key not in seen:
            seen.add(key)
            unique.append((cat, desc, rom))

    print(f"Total unique variants: {len(unique)}")

    for i, (cat, desc, rom) in enumerate(unique):
        fname = f"{i:06d}_{cat}_{desc}.txt"
        save_rom(rom, os.path.join(OUT_DIR, fname))

    print(f"Written to {OUT_DIR}/")

if __name__ == "__main__":
    main()
