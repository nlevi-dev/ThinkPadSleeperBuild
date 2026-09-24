#!/usr/bin/env python3
import sys
import csv

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

def fix_checksum(edid):
    edid[0x7F] = (256 - sum(edid[:0x7F]) % 256) % 256

def detect_edid_copies(rom, edid_size=128):
    first = rom[:edid_size]
    count = 0
    while count * edid_size < len(rom) and rom[count*edid_size:(count+1)*edid_size] == first:
        count += 1
    return count

def patch(rom, edid, edid_size=128):
    fix_checksum(edid)
    copies = detect_edid_copies(rom, edid_size)
    if copies == 0:
        raise ValueError("No EDID copies detected at start of ROM")
    for i in range(copies):
        rom[i*edid_size:(i+1)*edid_size] = edid
    return copies

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <firmware.txt> <edid.csv>")
        sys.exit(1)

    fw_path, csv_path = sys.argv[1], sys.argv[2]
    out_path = fw_path.rsplit(".", 1)[0] + "_patched.txt"

    rom  = load_rom(fw_path)
    edid = load_edid_csv(csv_path)
    copies = patch(rom, edid)

    with open(out_path, "w") as f:
        for i in range(0, len(rom), 16):
            f.write(" ".join(f"{b:02X}" for b in rom[i:i+16]) + "\n")

    print(f"Patched {copies} EDID copies -> {out_path}")
    print(f"Checksum: 0x{edid[0x7F]:02X}")
