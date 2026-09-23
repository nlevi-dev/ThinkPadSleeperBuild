# Manual observations from the CSV:
# - 0x19 Red/green low bits: 'ASCII or Data' says 10000111 but 0x43 = 01000011 — wrong in Samsung CSV
# - 0x1A Blue/white low bits: 'ASCII or Data' says 11111110 but 0xDE = 11011110 — wrong in Samsung CSV
# - 0x36/0x37 pixel clock: 0x2A30 little-endian = 10800 * 10kHz = 108 MHz — note is correct
# - 0x66/0x7D: 0x0A is newline, represented as [^] in the CSV — intentional shorthand, ignored
# - 0x3E/0x3F: H sync offset/width in notes are half the raw byte value (raw = note * 2)
# - 0x42/0x43: H/V image size in mm uses upper bits from 0x44 (bits 7-4 and 3-0)
# - 0x1B-0x22: chromaticity floats in Data = full 10-bit value / 1024,
#              low 2 bits packed in 0x19 (red/green) and 0x1A (blue/white)

import csv
import os
import re
import sys

if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} <edid.csv>")
    sys.exit(1)
path = sys.argv[1]

rows = []
with open(path) as f:
    for row in csv.DictReader(f):
        rows.append(row)

errors   = []
warnings = []

def err(addr, msg):
    errors.append(f"  0x{addr}: {msg}")

def warn(addr, msg):
    warnings.append(f"  0x{addr}: {msg}")

def get(addr_hex):
    return next((r for r in rows if r["Address (HEX)"].strip().upper() == addr_hex.upper()), None)

def val(addr_hex):
    r = get(addr_hex)
    return int(r["Value (HEX)"].strip(), 16) if r else None

def note(addr_hex):
    r = get(addr_hex)
    return r["Notes"].strip() if r else ""

def data(addr_hex):
    r = get(addr_hex)
    return r["ASCII or Data"].strip() if r else ""

bytes_ = []
for row in rows:
    addr       = row["Address (HEX)"].strip()
    hex_val    = row["Value (HEX)"].strip()
    bin_val    = row["BIN"].strip()
    dec_val    = row["DEC"].strip()
    ascii_data = row["ASCII or Data"].strip()

    try:
        v = int(hex_val, 16)
    except ValueError:
        err(addr, f"[Value] invalid hex value '{hex_val}'")
        bytes_.append(0)
        continue

    bytes_.append(v)

    # BIN check
    expected_bin = format(v, "08b")
    if bin_val != expected_bin:
        err(addr, f"[BIN] value 0x{hex_val} = {expected_bin}, got {bin_val}")

    # DEC check
    try:
        if int(dec_val) != v:
            err(addr, f"[DEC] value 0x{hex_val} = {v}, got {dec_val}")
    except ValueError:
        pass

    # ASCII check: bracketed single char like [A], skip [^] shorthand for control chars
    if len(ascii_data) == 3 and ascii_data[0] == "[" and ascii_data[2] == "]":
        expected_char = ascii_data[1]
        if expected_char != "^" and chr(v) != expected_char:
            err(addr, f"[ASCII] 0x{hex_val} = '{chr(v)}', got '{expected_char}'")

# --- Header ---
for i, expected in enumerate([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00]):
    if bytes_[i] != expected:
        err(format(i, "02X"), f"[Value] header byte {i} should be 0x{expected:02X}, got 0x{bytes_[i]:02X}")

# --- Manufacturer ID (0x08/0x09) ---
combined = (bytes_[0x08] << 8) | bytes_[0x09]
mfr = (
    chr(((combined >> 10) & 0x1F) + 0x40) +
    chr(((combined >>  5) & 0x1F) + 0x40) +
    chr(((combined >>  0) & 0x1F) + 0x40)
)
for addr in ("08", "09"):
    d = data(addr)
    if d and d != mfr:
        warn(addr, f"[Data] manufacturer ID: decoded {mfr}, got {d}")

# --- Year of manufacture (0x11) ---
decoded_year = 1990 + bytes_[0x11]
d = data("11")
if d:
    try:
        if int(d) != decoded_year:
            warn("11", f"[Data] year: 1990 + {bytes_[0x11]} = {decoded_year}, got {d}")
    except ValueError:
        pass

# --- EDID version (0x12): Data and Notes ---
d = data("12")
if d:
    try:
        if int(d) != bytes_[0x12]:
            warn("12", f"[Data] EDID version: value {bytes_[0x12]}, got {d}")
    except ValueError:
        pass
m = re.search(r"EDID Ver\.\s*([\d.]+)", note("12"))
if m and bytes_[0x12] != int(float(m.group(1))):
    warn("12", f"[Notes] EDID version: note says {m.group(1)}, value is {bytes_[0x12]}")

# --- EDID revision (0x13): Data and Notes ---
d = data("13")
if d:
    try:
        if int(d) != bytes_[0x13]:
            warn("13", f"[Data] EDID revision: value {bytes_[0x13]}, got {d}")
    except ValueError:
        pass
m = re.search(r"EDID Rev\.\s*(\d+)", note("13"))
if m and int(m.group(1)) != bytes_[0x13]:
    warn("13", f"[Notes] EDID revision: note says {m.group(1)}, value is {bytes_[0x13]}")

# --- Max H image size (0x15): Data and Notes ---
d = data("15")
if d:
    try:
        if int(d) != bytes_[0x15]:
            warn("15", f"[Data] H image size: value {bytes_[0x15]} cm, got {d}")
    except ValueError:
        pass
m = re.search(r"(\d+)\s*cm", note("15"))
if m and int(m.group(1)) != bytes_[0x15]:
    warn("15", f"[Notes] H image size: note says {m.group(1)} cm, value is {bytes_[0x15]}")

# --- Max V image size (0x16): Data and Notes ---
d = data("16")
if d:
    try:
        if int(d) != bytes_[0x16]:
            warn("16", f"[Data] V image size: value {bytes_[0x16]} cm, got {d}")
    except ValueError:
        pass
m = re.search(r"(\d+)\s*cm", note("16"))
if m and int(m.group(1)) != bytes_[0x16]:
    warn("16", f"[Notes] V image size: note says {m.group(1)} cm, value is {bytes_[0x16]}")

# --- Gamma (0x17): Data and Notes ---
decoded_gamma = (bytes_[0x17] + 100) / 100
d = data("17")
if d:
    try:
        if abs(float(d) - decoded_gamma) > 0.01:
            warn("17", f"[Data] gamma: decoded {decoded_gamma:.2f}, got {d}")
    except ValueError:
        pass
m = re.search(r"Gamma\s*([\d.]+)", note("17"))
if m and abs(float(m.group(1)) - decoded_gamma) > 0.01:
    warn("17", f"[Notes] gamma: decoded {decoded_gamma:.2f}, note says {m.group(1)}")

# --- Chromaticity low bits (0x19/0x1A): Data column contains 8-bit binary string ---
for addr in ("19", "1A"):
    d = data(addr)
    if re.fullmatch(r"[01]{8}", d):
        expected_bin = format(val(addr), "08b")
        if d != expected_bin:
            warn(addr, f"[Data] chromaticity low bits: data says {d}, value encodes {expected_bin}")

# --- Chromaticity high bytes (0x1B–0x22) ---
# Low 2 bits for each channel packed in 0x19/0x1A:
#   0x19 bits 7-6: red x low, bits 5-4: red y low, bits 3-2: green x low, bits 1-0: green y low
#   0x1A bits 7-6: blue x low, bits 5-4: blue y low, bits 3-2: white x low, bits 1-0: white y low
low_bits_map = {
    "1B": (bytes_[0x19] >> 6) & 0x03,  # red x
    "1C": (bytes_[0x19] >> 4) & 0x03,  # red y
    "1D": (bytes_[0x19] >> 2) & 0x03,  # green x
    "1E": (bytes_[0x19] >> 0) & 0x03,  # green y
    "1F": (bytes_[0x1A] >> 6) & 0x03,  # blue x
    "20": (bytes_[0x1A] >> 4) & 0x03,  # blue y
    "21": (bytes_[0x1A] >> 2) & 0x03,  # white x
    "22": (bytes_[0x1A] >> 0) & 0x03,  # white y
}
for addr, low2 in low_bits_map.items():
    high8 = val(addr)
    full10 = (high8 << 2) | low2
    decoded_coord = full10 / 1024

    # Data float check
    d = data(addr)
    if d:
        try:
            if abs(float(d) - decoded_coord) > 0.005:
                warn(addr, f"[Data] chromaticity: decoded {decoded_coord:.3f}, got {d}")
        except ValueError:
            pass

    # Notes: check high 8 bits against 10-bit binary
    n = note(addr)
    m = re.search(r"=\s*([01]{10})", n)
    if m:
        bits10 = m.group(1)
        expected_high8 = int(bits10[:8], 2)
        if high8 != expected_high8:
            warn(addr, f"[Notes] chromaticity: note binary {bits10} → high 8 bits = 0x{expected_high8:02X}, value is 0x{high8:02X}")

# --- Standard timings (0x26–0x35): 0x01 when "not used" ---
for i in range(0x26, 0x36):
    addr = format(i, "02X")
    if "not used" in note(addr).lower() and bytes_[i] != 0x01:
        warn(addr, f"[Notes] standard timing marked 'not used' should be 0x01, got 0x{bytes_[i]:02X}")

# --- Pixel clock (0x36/0x37): Data and Notes ---
pixel_clock_mhz = (bytes_[0x37] << 8 | bytes_[0x36]) * 10 / 1000
for addr in ("36", "37"):
    d = data(addr)
    if d:
        try:
            if abs(float(d) - pixel_clock_mhz) > 0.5:
                warn(addr, f"[Data] pixel clock: decoded {pixel_clock_mhz:.2f} MHz, got {d}")
        except ValueError:
            pass
m = re.search(r"([\d.]+)\s*MHz", note("36"))
if m and abs(float(m.group(1)) - pixel_clock_mhz) > 0.5:
    warn("36/37", f"[Notes] pixel clock: {pixel_clock_mhz:.2f} MHz, note says {m.group(1)} MHz")

# --- Horizontal active/blanking (0x38/0x39 low bytes, 0x3A upper nibbles) ---
h_active = bytes_[0x38] | ((bytes_[0x3A] >> 4) << 8)
h_blank  = bytes_[0x39] | ((bytes_[0x3A] & 0x0F) << 8)
d = data("38")
if d:
    try:
        if int(d) != h_active:
            warn("38/3A", f"[Data] H active: decoded {h_active}, got {d}")
    except ValueError:
        pass
m = re.search(r"([\d*]+)\s*pixels", note("38"))
if m:
    try:
        if eval(m.group(1)) != h_active:
            warn("38/3A", f"[Notes] H active: decoded {h_active}, note says {m.group(1)} = {eval(m.group(1))}")
    except Exception:
        pass
d = data("39")
if d:
    try:
        if int(d) != h_blank:
            warn("39/3A", f"[Data] H blanking: decoded {h_blank}, got {d}")
    except ValueError:
        pass
m = re.search(r"(\d+)\s*pixels", note("39"))
if m and int(m.group(1)) != h_blank:
    warn("39/3A", f"[Notes] H blanking: decoded {h_blank}, note says {m.group(1)}")

# --- Vertical active/blanking (0x3B/0x3C low bytes, 0x3D upper nibbles) ---
v_active = bytes_[0x3B] | ((bytes_[0x3D] >> 4) << 8)
v_blank  = bytes_[0x3C] | ((bytes_[0x3D] & 0x0F) << 8)
d = data("3B")
if d:
    try:
        if int(d) != v_active:
            warn("3B/3D", f"[Data] V active: decoded {v_active}, got {d}")
    except ValueError:
        pass
m = re.search(r"(\d+)\s*lines", note("3B"))
if m and int(m.group(1)) != v_active:
    warn("3B/3D", f"[Notes] V active: decoded {v_active}, note says {m.group(1)}")
d = data("3C")
if d:
    try:
        if int(d) != v_blank:
            warn("3C/3D", f"[Data] V blanking: decoded {v_blank}, got {d}")
    except ValueError:
        pass
m = re.search(r"Vertical blanking=(\d+)", note("3C"))
if m and int(m.group(1)) != v_blank:
    warn("3C/3D", f"[Notes] V blanking: decoded {v_blank}, note says {m.group(1)}")

# --- H sync offset (0x3E): raw byte = note * 2, Data = raw byte ---
d = data("3E")
if d:
    try:
        if int(d) != bytes_[0x3E]:
            warn("3E", f"[Data] H sync offset: value {bytes_[0x3E]}, got {d}")
    except ValueError:
        pass
m = re.search(r"Offset=(\d+)\s*pixels", note("3E"))
if m and bytes_[0x3E] != int(m.group(1)) * 2:
    warn("3E", f"[Notes] H sync offset: value {bytes_[0x3E]}, note says {m.group(1)} (expected raw {int(m.group(1)) * 2})")

# --- H sync width (0x3F): raw byte = note * 2, Data = raw byte ---
d = data("3F")
if d:
    try:
        if int(d) != bytes_[0x3F]:
            warn("3F", f"[Data] H sync width: value {bytes_[0x3F]}, got {d}")
    except ValueError:
        pass
m = re.search(r"Width=(\d+)", note("3F"))
if m and bytes_[0x3F] != int(m.group(1)) * 2:
    warn("3F", f"[Notes] H sync width: value {bytes_[0x3F]}, note says {m.group(1)} (expected raw {int(m.group(1)) * 2})")

# --- V sync offset + width (0x40 upper/lower nibble): Data = "offset width" ---
v_sync_offset = (bytes_[0x40] >> 4) & 0x0F
v_sync_width  =  bytes_[0x40] & 0x0F
d = data("40")
if d:
    parts = d.split()
    if len(parts) == 2:
        try:
            if int(parts[0]) != v_sync_offset:
                warn("40", f"[Data] V sync offset: decoded {v_sync_offset}, got {parts[0]}")
            if int(parts[1]) != v_sync_width:
                warn("40", f"[Data] V sync width: decoded {v_sync_width}, got {parts[1]}")
        except ValueError:
            pass
n40 = note("40")
m_off = re.search(r"Offset=(\d+)\s*lines", n40)
m_wid = re.search(r"Width=(\d+)\s*lines", n40)
if m_off and int(m_off.group(1)) != v_sync_offset:
    warn("40", f"[Notes] V sync offset: decoded {v_sync_offset}, note says {m_off.group(1)}")
if m_wid and int(m_wid.group(1)) != v_sync_width:
    warn("40", f"[Notes] V sync width: decoded {v_sync_width}, note says {m_wid.group(1)}")

# --- H/V image size in mm (0x42/0x43 low bytes, 0x44 upper nibbles) ---
h_size_mm = bytes_[0x42] | ((bytes_[0x44] >> 4) << 8)
v_size_mm = bytes_[0x43] | ((bytes_[0x44] & 0x0F) << 8)
d = data("42")
if d:
    try:
        if int(d) != h_size_mm:
            warn("42/44", f"[Data] H image size: decoded {h_size_mm} mm, got {d}")
    except ValueError:
        pass
m = re.search(r"(\d+)\s*mm", note("42"))
if m and int(m.group(1)) != h_size_mm:
    warn("42/44", f"[Notes] H image size: decoded {h_size_mm} mm, note says {m.group(1)} mm")
d = data("43")
if d:
    try:
        if int(d) != v_size_mm:
            warn("43/44", f"[Data] V image size: decoded {v_size_mm} mm, got {d}")
    except ValueError:
        pass
m = re.search(r"(\d+)\s*mm", note("43"))
if m and int(m.group(1)) != v_size_mm:
    warn("43/44", f"[Notes] V image size: decoded {v_size_mm} mm, note says {m.group(1)} mm")

# --- Border bytes (0x45/0x46) ---
if "No Horizontal Border" in note("45") and bytes_[0x45] != 0x00:
    warn("45", f"[Notes] horizontal border should be 0, got {bytes_[0x45]}")
if "No Vertical Border" in note("46") and bytes_[0x46] != 0x00:
    warn("46", f"[Notes] vertical border should be 0, got {bytes_[0x46]}")

# --- Descriptor #3 ASCII string tag (0x5D must be 0xFE) ---
if "ASCII Data String Tag" in note("5D") and bytes_[0x5D] != 0xFE:
    warn("5D", f"[Notes] ASCII string tag should be 0xFE, got 0x{bytes_[0x5D]:02X}")

# --- Descriptor #4 monitor name tag (0x6F must be 0xFE) ---
if "Monitor Name Tag" in note("6F") and bytes_[0x6F] != 0xFE:
    warn("6F", f"[Notes] monitor name tag should be 0xFE, got 0x{bytes_[0x6F]:02X}")

# --- Extension flag (0x7E) ---
if bytes_[0x7E] != 0x00:
    warn("7E", f"[Value] extension flag should be 0x00, got 0x{bytes_[0x7E]:02X}")

# --- Checksum (0x7F) ---
total = sum(bytes_) & 0xFF
if total != 0:
    err("7F", f"[Checksum] sum mod 256 = {total}, expected 0")
else:
    print("checksum OK")

if errors:
    print(f"\n{len(errors)} error(s):")
    for e in errors:
        print(e)

if warnings:
    print(f"\n{len(warnings)} warning(s):")
    for w in warnings:
        print(w)

if not errors and not warnings:
    print("no issues found")
