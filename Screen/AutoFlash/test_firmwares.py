#!/usr/bin/env python3
import os, time, glob, serial, subprocess, logging
import cv2, requests
from tqdm import tqdm

DIR        = os.path.dirname(__file__)
CREDS_DIR  = os.path.join(DIR, "credentials")
PIKVM_CRED = open(os.path.join(CREDS_DIR, "pikvm.txt")).read().strip()
SSH_KEY    = os.path.join(CREDS_DIR, "ssh.pem")
PIKVM_HOST = "https://192.168.33.2"
TARGET_IP  = "192.168.33.4"
PAGE_SIZE  = 16

logging.basicConfig(
    filename=os.path.join(DIR, "results.log"),
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)
IMAGES_DIR = os.path.join(DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

def load_rom(path):
    rom = bytearray()
    with open(path) as f:
        for line in f:
            for b in line.strip().split():
                rom.append(int(b, 16))
    return rom

def open_serial():
    ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    if not ports:
        raise RuntimeError("No serial port found")
    s = serial.Serial(ports[0], 9600, timeout=5)
    # wait for "ready"
    while True:
        line = s.readline().decode(errors="ignore").strip()
        if line == "ready":
            break
    return s

def cmd(ser, line):
    ser.write((line + "\n").encode())
    return ser.readline().decode(errors="ignore").strip()

def dump_rom(ser, size):
    pages = (size + PAGE_SIZE - 1) // PAGE_SIZE
    ser.write(f"DUMP {pages}\n".encode())
    rom = bytearray()
    for _ in range(pages):
        line = ser.readline().decode(errors="ignore").strip()
        for b in line.split():
            rom.append(int(b, 16))
    ser.readline()  # consume "ok"
    return rom

def flash_pages(ser, rom, pages):
    """Flash the given page indices."""
    for page in pages:
        addr = page * PAGE_SIZE
        chunk = rom[addr:addr + PAGE_SIZE]
        hex_bytes = " ".join(f"{b:02X}" for b in chunk)
        resp = cmd(ser, f"FLASH {addr:04X} {hex_bytes}")
        if not resp.startswith("ok"):
            raise RuntimeError(f"Flash failed at 0x{addr:04X}: {resp}")

def diff_pages(rom_a, rom_b):
    """Return page indices where rom_a and rom_b differ."""
    n = max(len(rom_a), len(rom_b))
    pages = set()
    for i in range(0, n, PAGE_SIZE):
        if rom_a[i:i+PAGE_SIZE] != rom_b[i:i+PAGE_SIZE]:
            pages.add(i // PAGE_SIZE)
    return sorted(pages)

def pikvm_get(path):
    user, pw = PIKVM_CRED.split(":", 1)
    r = requests.get(f"{PIKVM_HOST}{path}", auth=(user, pw), verify=False, timeout=10)
    r.raise_for_status()
    return r.json()

def pikvm_post(path):
    user, pw = PIKVM_CRED.split(":", 1)
    r = requests.post(f"{PIKVM_HOST}{path}", auth=(user, pw), verify=False, timeout=10)
    r.raise_for_status()

def wait_power_off():
    for _ in range(120):
        try:
            state = pikvm_get("/api/atx")
            if not state["result"]["leds"]["power"]:
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Timed out waiting for power LED to go off")

def ssh_root_poweroff():
    subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
         f"root@{TARGET_IP}", "poweroff"],
        timeout=10, check=False, capture_output=True
    )

def probe_display():
    """Try SSH until it succeeds, return True if DP-2 connected."""
    for _ in range(60):
        try:
            r = subprocess.run(
                ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=3",
                 f"levente@{TARGET_IP}",
                 r"DISPLAY=$(ls /tmp/.X11-unix/ | head -1 | sed 's/X/:/') "
                 r"xrandr | grep DP-2"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                return "connected" in r.stdout and "disconnected" not in r.stdout.split("DP-2")[1].split("\n")[0]
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Timed out waiting for SSH")

def main():
    import urllib3
    urllib3.disable_warnings()

    firmware_files = sorted(glob.glob(os.path.join(DIR, "firmwares", "*.txt")))
    if not firmware_files:
        raise RuntimeError("No firmware files found")

    ser = open_serial()

    # Dump current EEPROM state once to seed the diff
    cmd(ser, "POWER_ON")
    current_rom = dump_rom(ser, len(load_rom(firmware_files[0])))
    cmd(ser, "POWER_OFF")

    for i, fw_path in enumerate(tqdm(firmware_files, desc="Firmwares")):
        label = os.path.splitext(os.path.basename(fw_path))[0]
        next_rom = load_rom(fw_path)

        cmd(ser, "POWER_ON")
        pages = diff_pages(current_rom, next_rom)
        if pages:
            flash_pages(ser, next_rom, pages)
        current_rom = next_rom
        cmd(ser, "POWER_OFF")

        ssh_root_poweroff()
        wait_power_off()
        time.sleep(5)
        pikvm_post("/api/atx/click?button=power")

        connected = False
        try:
            connected = probe_display()
            result = "CONNECTED" if connected else "DISCONNECTED"
        except RuntimeError as e:
            result = f"ERROR: {e}"

        if connected:
            time.sleep(3)
            cap = cv2.VideoCapture(2)
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            cap.set(cv2.CAP_PROP_EXPOSURE, 10000)
            cap.set(cv2.CAP_PROP_GAIN, 255)
            cap.set(cv2.CAP_PROP_BRIGHTNESS, 255)
            cap.set(cv2.CAP_PROP_CONTRAST, 255)
            for _ in range(5): cap.read()  # let settings settle
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(os.path.join(IMAGES_DIR, f"{label}.png"), frame)

        logging.info(f"{label}  {result}")

    ser.close()

if __name__ == "__main__":
    main()
