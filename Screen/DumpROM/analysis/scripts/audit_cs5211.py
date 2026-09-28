#!/usr/bin/env python3
"""Execute bounded 8051 instruction slices from the ROM to audit prior claims.

This is deliberately NOT a CS5211 hardware emulator. It models only the
instructions used by selected slices, fails on unsupported instructions, and
records opaque XDATA writes without assigning hardware register semantics.
Run: python3 scripts/audit_cs5211.py binaries/dump_CS5211.txt
"""
import argparse
import hashlib
import json
from pathlib import Path


class Slice8051:
    def __init__(self, rom):
        self.code = rom[0x1000:]
        self.mem = bytearray(256)
        self.mem[0x81] = 0x60
        self.xdata = {}
        self.writes = []
        self.reads = []
        self.carry = 0

    @property
    def a(self):
        return self.mem[0xe0]

    @a.setter
    def a(self, value):
        self.mem[0xe0] = value & 255

    @property
    def dptr(self):
        return self.mem[0x82] | (self.mem[0x83] << 8)

    def run(self, start, stop=None):
        pc = start
        for _ in range(10000):
            if pc == stop:
                return self
            here = pc
            op = self.code[pc]
            pc += 1

            def byte():
                nonlocal pc
                value = self.code[pc]
                pc += 1
                return value

            def relative(taken):
                nonlocal pc
                offset = byte()
                if taken:
                    pc += offset if offset < 128 else offset - 256

            if op == 0x90:  # MOV DPTR,#imm16
                self.mem[0x83], self.mem[0x82] = byte(), byte()
            elif op == 0x93:  # MOVC A,@A+DPTR
                addr = (self.a + self.dptr) & 0xffff
                self.reads.append((here, addr))
                self.a = self.code[addr]
            elif op == 0xf0:  # MOVX @DPTR,A
                self.xdata[self.dptr] = self.a
                self.writes.append((here, self.dptr, self.a))
            elif op == 0xe0:
                if self.dptr not in self.xdata:
                    raise ValueError(f"Unmodelled XDATA read at {here:04x}: {self.dptr:04x}")
                self.a = self.xdata[self.dptr]
            elif op == 0xe4:
                self.a = 0
            elif op == 0x74:
                self.a = byte()
            elif op == 0xe5:
                self.a = self.mem[byte()]
            elif op == 0xf5:
                self.mem[byte()] = self.a
            elif op == 0x75:
                dst, value = byte(), byte()
                self.mem[dst] = value
            elif op == 0x85:
                src, dst = byte(), byte()
                self.mem[dst] = self.mem[src]
            elif 0x78 <= op <= 0x7f:
                self.mem[op - 0x78] = byte()
            elif 0xa8 <= op <= 0xaf:
                self.mem[op - 0xa8] = self.mem[byte()]
            elif 0xe8 <= op <= 0xef:
                self.a = self.mem[op - 0xe8]
            elif 0xf8 <= op <= 0xff:
                self.mem[op - 0xf8] = self.a
            elif op in (0xe6, 0xe7):
                self.a = self.mem[self.mem[op - 0xe6]]
            elif op == 0x54:
                self.a &= byte()
            elif op == 0x44:
                self.a |= byte()
            elif op == 0x45:
                self.a |= self.mem[byte()]
            elif 0x48 <= op <= 0x4f:
                self.a |= self.mem[op - 0x48]
            elif op == 0x64:
                self.a ^= byte()
            elif op == 0x53:
                dst, mask = byte(), byte()
                self.mem[dst] &= mask
            elif op == 0x43:
                dst, mask = byte(), byte()
                self.mem[dst] |= mask
            elif op == 0xc4:
                self.a = (self.a << 4) | (self.a >> 4)
            elif op in (0x24, 0x25):
                operand = byte()
                value = operand if op == 0x24 else self.mem[operand]
                result = self.a + value
                self.carry = int(result > 255)
                self.a = result
            elif op == 0x95:
                result = self.a - self.mem[byte()] - self.carry
                self.carry = int(result < 0)
                self.a = result
            elif op == 0xc3:
                self.carry = 0
            elif op == 0x05:
                dst = byte()
                self.mem[dst] = (self.mem[dst] + 1) & 255
            elif op == 0xa3:
                value = (self.dptr + 1) & 0xffff
                self.mem[0x82], self.mem[0x83] = value & 255, value >> 8
            elif op == 0x60:
                relative(self.a == 0)
            elif op == 0x70:
                relative(self.a != 0)
            elif op == 0x80:
                relative(True)
            elif op == 0xc0:
                value = self.mem[byte()]
                self.mem[0x81] += 1
                self.mem[self.mem[0x81]] = value
            elif op == 0xd0:
                dst = byte()
                self.mem[dst] = self.mem[self.mem[0x81]]
                self.mem[0x81] -= 1
            elif op == 0x32:  # RETI: boundary of the isolated ISR
                return self
            else:
                raise ValueError(f"Unsupported opcode {op:02x} at {here:04x}")
        raise ValueError("Instruction budget exhausted")


def profile(rom, index=0):
    cpu = Slice8051(rom)
    cpu.xdata[0xca] = index
    cpu.run(0x266, 0x271)
    return cpu.run(0x49f, 0x525)


def audit(rom):
    assert len(rom) == 8192
    assert rom[0x1000:0x1003] == bytes.fromhex("02 01 30")
    assert rom[0x100b:0x100e] == bytes.fromhex("02 0c 48")
    baseline = profile(rom)
    for i in range(16):
        cpu = profile(rom, i)
        assert cpu.writes == baseline.writes
        assert cpu.mem[8] == i * 16
    # Exhaustively test both operands independently, including nonzero high bits.
    for p in range(256):
        for g in (0, 1, 0x0f, 0x10, 0xa5, 0xff):
            trial = bytearray(rom)
            trial[0x101b], trial[0x1122] = p, g
            assert profile(trial).xdata[0x1f4] == (p | ((g & 15) << 4))
    effectless = []
    for offset in range(16):
        for bit in range(8):
            trial = bytearray(rom)
            trial[0x1010 + offset] ^= 1 << bit
            if profile(trial).writes == baseline.writes:
                effectless.append(f"+{offset:02x}.bit{bit}")
    # Global flag changes, isolated before unrelated hardware polling.
    modes = {}
    for v in (0, 1):
        trial = bytearray(rom)
        trial[0x111e] = v
        cpu = Slice8051(trial).run(0x1c0, 0x20c)
        modes[str(v)] = {f"0x{k:04x}": f"0x{v:02x}" for k, v in cpu.xdata.items()}
    # The alleged gamma curve is explicitly used as timer reload values.
    assert rom[0x1e3b:0x1e3d] == bytes((11, 0x16))
    curve = rom[0x1e3d:0x1e48]
    timer = []
    for level in range(11):
        phases = []
        for phase in (0, 1):
            cpu = Slice8051(rom)
            cpu.mem[0x13], cpu.mem[0x15] = level, phase
            cpu.mem[0x16:0x21] = curve
            cpu.run(0xc48)
            if level < 10:
                assert cpu.mem[0x8c] == curve[level if phase == 0 else 10 - level]
                assert cpu.mem[0x8a] == 0
            phases.append({"TH0": cpu.mem[0x8c], "XDATA_00b3": cpu.xdata.get(0xb3)})
        timer.append({"level": level, "phases": phases})
    payloads = [rom[0x804+i*128:0x884+i*128] for i in range(3)]
    assert payloads[0] == payloads[1] == payloads[2]
    return {
        "sha256": hashlib.sha256(rom).hexdigest(),
        "profile_writes": [{"pc": f"0x{pc:04x}", "xdata": f"0x{addr:04x}", "value": f"0x{v:02x}"} for pc, addr, v in baseline.writes],
        "profile_byte_11_formula": "profile[11] | ((ROM[0x1122] & 0x0f) << 4)",
        "no_effect_in_profile_copy_slice": effectless,
        "global_111e_bit0_paths": modes,
        "timer_reload_table": timer,
        "opaque_region": "4 bytes at 0x0800, then three identical 128-byte blocks at 0x0804, 0x0884, 0x0904; role unknown",
        "scope": "Isolated instruction slices; not full firmware or CS5211 hardware emulation",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(bytes.fromhex(args.rom.read_text())), indent=2))
