#!/usr/bin/env python3
"""Black-box instruction execution with independent emu8051 CPU/timer core.

The CS5211 peripheral registers are a scripted input/output boundary, not an
emulation of the chip. Unseeded XDATA reads return zero and are reported.
No firmware is flashed and no physical device is contacted.
"""
import argparse
import ctypes as C
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/cs5211-blackbox"
CORE = ROOT / "tools/emu8051"
LIB = OUT / ("cs5211_emulator.dylib" if sys.platform == "darwin" else "cs5211_emulator.so")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["clang", "-O2", "-shared", "-fPIC", "-I", str(CORE),
                    str(ROOT / "scripts/cs5211_emulator.c"),
                    *[str(CORE / p) for p in ("core.c", "opcodes.c", "disasm.c")],
                    "-o", str(LIB)], check=True)


def library():
    lib = C.CDLL(str(LIB))
    declarations = {
        "cs_new": ([C.c_char_p, C.c_uint], C.c_void_p),
        "cs_free": ([C.c_void_p], None),
        "cs_log_mask": ([C.c_void_p, C.c_uint], None),
        "cs_clear_events": ([C.c_void_p], None),
        "cs_seed": ([C.c_void_p, C.c_uint, C.c_uint], None),
        "cs_pc": ([C.c_void_p, C.c_uint], None),
        "cs_direct": ([C.c_void_p, C.c_uint, C.c_uint], None),
        "cs_run": ([C.c_void_p, C.c_uint, C.c_uint], C.c_int),
        "cs_get": ([C.c_void_p, C.c_uint, C.c_uint], C.c_uint),
        "cs_event": ([C.c_void_p, C.c_uint, C.POINTER(C.c_uint32)], None),
    }
    for name, (args, result) in declarations.items():
        getattr(lib, name).argtypes = args
        getattr(lib, name).restype = result
    return lib


class CPU:
    def __init__(self, rom):
        self.lib = library()
        self.ptr = self.lib.cs_new(bytes(rom), len(rom))
        if not self.ptr:
            raise ValueError("Unable to initialize CPU")

    def close(self):
        if self.ptr:
            self.lib.cs_free(self.ptr)
            self.ptr = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def seed(self, address, value):
        self.lib.cs_seed(self.ptr, address, value)

    def log_mask(self, mask):
        self.lib.cs_log_mask(self.ptr, mask)

    def clear_events(self):
        self.lib.cs_clear_events(self.ptr)

    def direct(self, address, value):
        self.lib.cs_direct(self.ptr, address, value)

    def pc(self, value):
        self.lib.cs_pc(self.ptr, value)

    def get(self, space, address):
        return self.lib.cs_get(self.ptr, space, address)

    def run(self, stop=0xffff, ticks=20_000_000):
        result = self.lib.cs_run(self.ptr, ticks, stop)
        if result == 2:
            raise RuntimeError(f"CPU exception at {self.get(10,0):04x}: "
                               f"{[self.get(9,i) for i in range(16)]}")
        return result == 1

    def events(self, kind=None):
        if self.get(10,4):
            raise RuntimeError("Event buffer overflow")
        row = (C.c_uint32 * 5)()
        for i in range(self.get(10,3)):
            self.lib.cs_event(self.ptr, i, row)
            if kind is None or row[4] == kind:
                yield tuple(row)

    def summary(self):
        return {
            "pc": self.get(10,0), "instructions": self.get(10,1), "ticks": self.get(10,2),
            "max_sp": self.get(10,5),
            "registers": {f"{i:04x}":self.get(1,i) for i in range(0x800) if self.get(8,i)},
            "unseeded_reads": [f"{i:04x}" for i in range(0x800) if self.get(7,i)],
            "code_reads": [f"{i:04x}" for i in range(0x1000) if self.get(5,i)],
            "coverage": [f"{i:04x}" for i in range(0x1000) if self.get(4,i)],
        }


def setup_inputs(cpu, m=2, n=5, rate=10, lanes=2, profile=0):
    # Synthetic status inputs chosen to reach the link-up branch, not measured
    # hardware values. The M/N meaning is the hypothesis under test.
    inputs = {0x00ca:profile, 0x000c:0x21, 0x0611:0x07 if lanes==1 else 0x77,
              0x060b:lanes, 0x060a:rate, 0x01b4:0x5c}
    for base, value in ((0x549,m),(0x54c,n)):
        for off, v in enumerate(value.to_bytes(3,"big")):
            inputs[base+off] = v
    for k,v in inputs.items():
        cpu.seed(k,v)
    return inputs


def run_boot(rom, budget=20_000_000, **inputs):
    with CPU(rom) as cpu:
        seeded = setup_inputs(cpu, **inputs)
        reached = cpu.run(stop=0x056a,ticks=budget)
        out = cpu.summary()
        out.update(reached_link_loop=reached, inputs={f"{k:04x}":v for k,v in seeded.items()})
        out["writes"] = list(cpu.events(1))
        return out


def run_clock(rom, port=1, **inputs):
    with CPU(rom) as cpu:
        setup_inputs(cpu, **inputs)
        cpu.pc(0x0a20)
        cpu.direct(0x81,0x3c)
        cpu.direct(0x3b,0xff)
        cpu.direct(0x3c,0xff)
        cpu.direct(7,port)
        reached = cpu.run()
        out = cpu.summary()
        out.update(returned=reached)
        out["writes"] = list(cpu.events(1))
        return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",action="store_true")
    parser.add_argument("--clock",action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
    rom = bytes.fromhex((ROOT / "binaries/dump_CS5211.txt").read_text())
    result = run_clock(rom) if args.clock else run_boot(rom)
    print(json.dumps(result,indent=2))
