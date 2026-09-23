import csv
import os
import sys

if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} <dump.txt>")
    sys.exit(1)
dump_path = sys.argv[1]
out_path  = os.path.join(os.path.dirname(dump_path), "edid_" + os.path.splitext(os.path.basename(dump_path))[0] + ".csv")

raw = []
with open(dump_path) as f:
    for line in f:
        for token in line.strip().split():
            raw.append(int(token, 16))

e = raw[:128]

def bin8(v):
    return format(v, "08b")

def ascii_field(v):
    if 0x20 <= v <= 0x7E:
        return f"[{chr(v)}]"
    if v == 0x0A:
        return "[^]"
    return ""

FUNCTIONS = {
    0x00: "Header", 0x01: "Header", 0x02: "Header", 0x03: "Header",
    0x04: "Header", 0x05: "Header", 0x06: "Header", 0x07: "Header",
    0x08: "ID Manufacturer Name", 0x09: "ID Manufacturer Name",
    0x0A: "ID Product Code",      0x0B: "ID Product Code",
    0x0C: "32-bit serial no.",    0x0D: "32-bit serial no.",
    0x0E: "32-bit serial no.",    0x0F: "32-bit serial no.",
    0x10: "Week of manufacture",  0x11: "Year of manufacture",
    0x12: "EDID Structure Ver.",  0x13: "EDID revision #",
    0x14: "Video input definition",
    0x15: "Max H image size",     0x16: "Max V image size",
    0x17: "Display Gamma",        0x18: "Feature support",
    0x19: "Red/green low bits",   0x1A: "Blue/white low bits",
    0x1B: "Red x/ high bits",     0x1C: "Red y",
    0x1D: "Green x",              0x1E: "Green y",
    0x1F: "Blue x",               0x20: "Blue y",
    0x21: "White x",              0x22: "White y",
    0x23: "Established timing 1", 0x24: "Established timing 2",
    0x25: "Established timing 3",
    **{a: f"Standard timing #{(a - 0x26) // 2 + 1}" for a in range(0x26, 0x36)},
    **{a: "Detailed timing/monitor descriptor #1" for a in range(0x36, 0x48)},
    **{a: "Detailed timing/monitor descriptor #2" for a in range(0x48, 0x5A)},
    **{a: "Detailed timing/monitor descriptor #3" for a in range(0x5A, 0x6C)},
    **{a: "Detailed timing/monitor descriptor #4" for a in range(0x6C, 0x7E)},
    0x7E: "Extension Flag",
    0x7F: "Checksum",
}

# Pre-decode multi-byte fields
combined = (e[0x08] << 8) | e[0x09]
mfr = (
    chr(((combined >> 10) & 0x1F) + 0x40) +
    chr(((combined >>  5) & 0x1F) + 0x40) +
    chr(((combined >>  0) & 0x1F) + 0x40)
)
pixel_clock_mhz = ((e[0x37] << 8) | e[0x36]) * 10 / 1000
h_active  = e[0x38] | ((e[0x3A] >> 4) << 8)
h_blank   = e[0x39] | ((e[0x3A] & 0x0F) << 8)
v_active  = e[0x3B] | ((e[0x3D] >> 4) << 8)
v_blank   = e[0x3C] | ((e[0x3D] & 0x0F) << 8)
h_size_mm = e[0x42] | ((e[0x44] >> 4) << 8)
v_size_mm = e[0x43] | ((e[0x44] & 0x0F) << 8)
v_sync_offset = (e[0x40] >> 4) & 0x0F
v_sync_width  =  e[0x40] & 0x0F

# Chromaticity low bits
low2 = {
    0x1B: (e[0x19] >> 6) & 0x03,
    0x1C: (e[0x19] >> 4) & 0x03,
    0x1D: (e[0x19] >> 2) & 0x03,
    0x1E: (e[0x19] >> 0) & 0x03,
    0x1F: (e[0x1A] >> 6) & 0x03,
    0x20: (e[0x1A] >> 4) & 0x03,
    0x21: (e[0x1A] >> 2) & 0x03,
    0x22: (e[0x1A] >> 0) & 0x03,
}
chroma_names = {
    0x1B: "Red x",   0x1C: "Red y",
    0x1D: "Green x", 0x1E: "Green y",
    0x1F: "Blue x",  0x20: "Blue y",
    0x21: "White x", 0x22: "White y",
}

rows = []
for i, v in enumerate(e):
    addr    = format(i, "02X")
    func    = FUNCTIONS.get(i, "")
    hex_val = format(v, "02X")
    bin_val = bin8(v)
    dec_val = str(v)
    data    = ""
    notes   = ""

    if i in (0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
        notes = "EDID Header"
    elif i in (0x08, 0x09):
        data  = mfr
        notes = "3 character ID"
    elif i in (0x0A, 0x0B):
        notes = ""
    elif i in (0x0C, 0x0D, 0x0E, 0x0F):
        notes = ""
    elif i == 0x11:
        data = str(1990 + v)
    elif i == 0x12:
        data  = str(v)
        notes = f"EDID Ver. {v}.0"
    elif i == 0x13:
        data  = str(v)
        notes = f"EDID Rev. {v}"
    elif i == 0x15:
        data  = str(v)
        notes = f"{v} cm(approx)"
    elif i == 0x16:
        data  = str(v)
        notes = f"{v} cm(approx)"
    elif i == 0x17:
        gamma = (v + 100) / 100
        data  = f"{gamma:.1f}"
        notes = f"Gamma {gamma:.1f}"
    elif i == 0x19:
        data = bin8(v)
    elif i == 0x1A:
        data = bin8(v)
    elif i in low2:
        full10 = (v << 2) | low2[i]
        coord  = full10 / 1024
        name   = chroma_names[i]
        data   = f"{coord:.3f}"
        notes  = f"{name} {coord:.3f} = {format(full10, '010b')}"
    elif i in (0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D,
               0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35):
        notes = "not used" if v == 0x01 else ""
    elif i == 0x36:
        data  = f"{pixel_clock_mhz:.2f}"
        notes = f"Main clock = {pixel_clock_mhz:.2f} MHz"
    elif i == 0x37:
        data  = f"{pixel_clock_mhz:.2f}"
        notes = f"Main clock = {pixel_clock_mhz:.2f} MHz"
    elif i == 0x38:
        data  = str(h_active)
        notes = f"Hor active = {h_active} pixels"
    elif i == 0x39:
        data  = str(h_blank)
        notes = f"Hor blanking = {h_blank} pixels"
    elif i == 0x3A:
        notes = "4bit : 4bit"
    elif i == 0x3B:
        data  = str(v_active)
        notes = f"Vertical active = {v_active} lines"
    elif i == 0x3C:
        data  = str(v_blank)
        notes = f"Vertical blanking={v_blank} lines"
    elif i == 0x3D:
        notes = "4bit : 4bit"
    elif i == 0x3E:
        data  = str(v)
        notes = f"Hor sync. Offset={v // 2} pixels"
    elif i == 0x3F:
        data  = str(v)
        notes = f"H sync. Width={v // 2} pixels"
    elif i == 0x40:
        data  = f"{v_sync_offset} {v_sync_width}"
        notes = f"V sync. Offset={v_sync_offset} lines & V sync. Width={v_sync_width} lines"
    elif i == 0x41:
        notes = "2bit : 2bit :2bit :2bit"
    elif i == 0x42:
        data  = str(h_size_mm)
        notes = f"H image size= {h_size_mm} mm(approx)"
    elif i == 0x43:
        data  = str(v_size_mm)
        notes = f"V image size = {v_size_mm} mm(approx)"
    elif i == 0x45:
        notes = "No Horizontal Border" if v == 0 else f"Horizontal Border = {v}"
    elif i == 0x46:
        notes = "No Vertical Border" if v == 0 else f"Vertical Border = {v}"
    elif i in range(0x48, 0x5A):
        notes = "Manufacturer Specified (Timing)"
    elif i in (0x5A, 0x5B, 0x5C, 0x5D, 0x5E):
        notes = "ASCII Data String Tag"
    elif 0x5F <= i <= 0x6B:
        data = ascii_field(v)
    elif i in (0x6C, 0x6D, 0x6E, 0x6F, 0x70):
        notes = "Monitor Name Tag (ASCII)"
    elif 0x71 <= i <= 0x7D:
        data = ascii_field(v)
    elif i == 0x7F:
        checksum_ok = sum(e) & 0xFF == 0
        notes = "OK" if checksum_ok else f"INVALID (sum mod 256 = {sum(e) & 0xFF})"

    rows.append([addr, func, hex_val, bin_val, dec_val, data, notes])

with open(out_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Address (HEX)", "FUNCTION", "Value (HEX)", "BIN", "DEC", "ASCII or Data", "Notes"])
    w.writerows(rows)

print(f"written to {out_path}")
