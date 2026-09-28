#!/usr/bin/env python3
import sys
import csv

MODE_8BIT = True
MODE_VESA = False

# Slot layout per 16-byte slot: [01, 00, b2, b3, ...]
#   slot[0]: always 0x01 (dual-channel)
#   slot[1]: always 0x00
#   slot[2] b2: always 0x00 (dual active flag)
#   slot[3] b3: 0x07=6bit JEIDA, 0x03=6bit VESA, 0x05=8bit JEIDA, 0x01=8bit VESA
# CS values derived from all-slots-uniform config tool dumps.
_SLOT_MODES = {
    # (8bit, vesa): (b3,   CS)
    (False, False): (0x07, 0x5DA247C5),  # 6bit JEIDA
    (False, True):  (0x03, 0x9C58E855),  # 6bit VESA
    (True,  False): (0x05, 0xDA960552),  # 8bit JEIDA
    (True,  True):  (0x01, 0x1B6CAAC2),  # 8bit VESA
}

SLOT_B3, FIRMWARE_CS = _SLOT_MODES[(MODE_8BIT, MODE_VESA)]

SLOT_REGION_OFFSET = 0x1010
SLOT_SIZE          = 16
NUM_SLOTS          = 16
CS_OFFSET          = 0x0FFA


def load_rom(path):
    rom = []
    with open(path) as f:
        for line in f:
            for b in line.strip().split():
                rom.append(int(b, 16))
    return bytearray(rom)


def load_edid_csv(path):
    edid = [None] * 128
    with open(path, newline='') as f:
        for row in csv.reader(f):
            try:
                addr = int(row[0], 16)
                val  = int(row[2], 16)
            except (ValueError, IndexError):
                continue
            if 0 <= addr <= 0x7F:
                edid[addr] = val
    if any(b is None for b in edid):
        missing = [i for i, b in enumerate(edid) if b is None]
        raise ValueError("EDID CSV missing bytes: " + ", ".join(f"0x{i:02X}" for i in missing))
    return bytearray(edid)


def fix_edid_checksum(edid):
    edid[0x7F] = (256 - sum(edid[:0x7F]) % 256) % 256


def detect_edid_copies(rom, edid_size=128):
    first = rom[:edid_size]
    count = 0
    while count * edid_size < len(rom) and rom[count*edid_size:(count+1)*edid_size] == first:
        count += 1
    return count


def patch_slots(rom):
    for i in range(NUM_SLOTS):
        base = SLOT_REGION_OFFSET + i * SLOT_SIZE
        rom[base + 0] = 0x01
        rom[base + 1] = 0x00
        rom[base + 2] = 0x00
        rom[base + 3] = SLOT_B3


def patch_firmware_checksum(rom):
    cs = FIRMWARE_CS
    rom[CS_OFFSET + 0] = (cs >> 24) & 0xFF
    rom[CS_OFFSET + 1] = (cs >> 16) & 0xFF
    rom[CS_OFFSET + 2] = (cs >>  8) & 0xFF
    rom[CS_OFFSET + 3] =  cs        & 0xFF


def patch(rom, edid, edid_size=128):
    fix_edid_checksum(edid)
    copies = detect_edid_copies(rom, edid_size)
    if copies == 0:
        raise ValueError("No EDID copies detected at start of ROM")
    for i in range(copies):
        rom[i*edid_size:(i+1)*edid_size] = edid
    patch_slots(rom)
    patch_firmware_checksum(rom)
    return copies


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <firmware.txt> <edid.csv>")
        sys.exit(1)

    fw_path, csv_path = sys.argv[1], sys.argv[2]
    mode_str = ("8bit" if MODE_8BIT else "6bit") + "_" + ("vesa" if MODE_VESA else "jeida")
    out_path = fw_path.rsplit(".", 1)[0] + "_patched_" + mode_str + ".txt"

    rom  = load_rom(fw_path)
    edid = load_edid_csv(csv_path)
    copies = patch(rom, edid)

    with open(out_path, "w") as f:
        for i in range(0, len(rom), 16):
            f.write(" ".join(f"{b:02X}" for b in rom[i:i+16]) + "\n")

    print(f"Patched {copies} EDID copies, all {NUM_SLOTS} slots -> {out_path}")
    print(f"Mode: {mode_str}  (b3=0x{SLOT_B3:02X}  CS=0x{FIRMWARE_CS:08X})")
    print(f"EDID checksum: 0x{edid[0x7F]:02X}")
