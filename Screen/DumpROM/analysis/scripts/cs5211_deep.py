#!/usr/bin/env python3
"""Coverage-guided CS5211 experiments; all peripheral inputs are synthetic."""
import json
import random
import re
from pathlib import Path
from cs5211_blackbox import ROOT,CPU,setup_inputs

OUT=ROOT/'artifacts/cs5211-deep'
ROM=bytes.fromhex((ROOT/'binaries/dump_CS5211.txt').read_text())
LISTING=(ROOT/'artifacts/cs5211-review-2026-09-28/ghidra-listing.txt').read_text()
INS={int(m[1],16):dict(bytes=m[2].split(),asm=m[3]) for m in
     re.finditer(r'^CODE:([0-9a-f]+)\s+((?:[0-9a-f]{2} )+)\s*(.+)$',LISTING,re.M)}
BRANCH={p:d for p,d in INS.items() if d['asm'].split()[0] in
        ('JBC','JB','JNB','JC','JNC','JZ','JNZ','CJNE','DJNZ')}


def save(name,data):
    OUT.mkdir(exist_ok=True,parents=True)
    (OUT/name).write_text(json.dumps(data,indent=2)+'\n')


class Coverage:
    def __init__(self):
        self.pcs=set();self.edges=set();self.cases=[];self.movc=set()

    def capture(self,cpu,name,scope='reset',inputs=None):
        pcs={p for p in INS if cpu.get(4,p)}
        edges={(p,bit) for p in BRANCH for bit in (1,2) if cpu.get(11,p)&bit}
        movc={p for p in range(0x1000) if cpu.get(5,p)}
        self.cases.append(dict(name=name,scope=scope,inputs=inputs,
                              new_pcs=[f'{p:04x}' for p in sorted(pcs-self.pcs)],
                              new_edges=[(f'{p:04x}',e) for p,e in sorted(edges-self.edges)],
                              pc=f'{cpu.get(10,0):04x}',instructions=cpu.get(10,1)))
        self.pcs|=pcs;self.edges|=edges;self.movc|=movc

    def export(self,name):
        result=dict(instruction_denominator=len(INS),branch_edge_denominator=2*len(BRANCH),
                    covered_instructions=len(self.pcs),covered_branch_edges=len(self.edges),
                    pcs=[f'{p:04x}' for p in sorted(self.pcs)],
                    edges=[(f'{p:04x}',e) for p,e in sorted(self.edges)],
                    uncovered={f'{p:04x}':INS[p]['asm'] for p in INS if p not in self.pcs},
                    missing_edges={f'{p:04x}':dict(asm=BRANCH[p]['asm'],missing=[e for e in (1,2) if (p,e) not in self.edges])
                                   for p in BRANCH if any((p,e) not in self.edges for e in (1,2))},
                    movc_reads=[f'{p:04x}' for p in sorted(self.movc)],cases=self.cases)
        save(name,result)
        print(name,len(self.cases),'cases;',len(self.pcs),'/',len(INS),'instructions;',len(self.edges),'/',2*len(BRANCH),'branch edges',flush=True)
        return result


def execute(cov,name,patch=None,inputs=None,runtime=True):
    rom=bytearray(ROM)
    for k,v in (patch or {}).items():rom[k]=v
    with CPU(rom) as cpu:
        setup_inputs(cpu)
        cpu.seed(0xb0,0x60);cpu.seed(0xb1,0x20)
        for k,v in (inputs or {}).items():cpu.seed(k,v)
        cpu.log_mask(2)
        reached=cpu.run(stop=0x056a,ticks=3_000_000)
        if reached and runtime:
            cpu.run(stop=0x056a,ticks=3_000_000)
        cov.capture(cpu,name,inputs=dict(patch={f'{k:04x}':v for k,v in (patch or {}).items()},
                                       xdata={f'{k:04x}':v for k,v in (inputs or {}).items()}))


def coverage_campaign():
    cov=Coverage()
    execute(cov,'baseline')
    for mode in range(256):
        execute(cov,f'mode-{mode:02x}',{0x1112:mode,0x111b:5},
                {0xb0:(0,0x20,0x40,0x60)[mode%4],0xb1:0})
    for addr in (0x6,0x1f,0xaa,0xe1,0x554,0x613):
        for value in (1,2,4,8,16,32,64,128,255):
            execute(cov,f'unknown-{addr:04x}-{value:02x}',inputs={addr:value})
    for selector in (0,1):
        for marker in (0,0xaa,0xff):
            execute(cov,f'global-branch-{selector}-{marker}',
                    {0x111e:selector,0x111f:0x5a,0x1120:0xa5,0x1121:marker})
    for level in (0,1,9,10,11,128,255):
        for limits in ((0,10),(5,5),(10,0),(0,255)):
            execute(cov,f'level-{level}-{limits}',
                    {0x1112:1,0x111b:level,0x111c:limits[0],0x111d:limits[1]},
                    {0xb0:0})
    # Full CPU runs reaching both wait-timeout reset paths and link recovery.
    for ready in (0,1,0x20,0x21):
        for status in (0,7,0x77,0xff):
            execute(cov,f'link-{ready:02x}-{status:02x}',inputs={0xc:ready,0x611:status})
    for lanes in (1,2,0x81,0x82):
        execute(cov,f'lanes-{lanes}',inputs={0x60b:lanes,0x611:7 if lanes&31==1 else 0x77})
    for ready in (1,0x20):
        with CPU(ROM) as cpu:
            setup_inputs(cpu);cpu.seed(0xc,ready);cpu.log_mask(2)
            assert cpu.run(stop=0x0494,ticks=8_000_000)
            cpu.run(stop=0x03a6)
            cov.capture(cpu,f'timeout-{ready:02x}')
    for fault in (0xc,0x611,0x1b4):
        with CPU(ROM) as cpu:
            setup_inputs(cpu);cpu.log_mask(2)
            assert cpu.run(stop=0x056a)
            cpu.seed(fault,0)
            assert cpu.run(stop=0x03a6)
            setup_inputs(cpu,m=1,n=5)
            assert cpu.run(stop=0x056a)
            cov.capture(cpu,f'recovery-{fault:04x}')
    # Firmware-written 01d7 can be changed by hardware after init: inject at
    # a documented execution boundary, rather than pretending it survived reset.
    with CPU(ROM) as cpu:
        setup_inputs(cpu);cpu.log_mask(2)
        assert cpu.run(stop=0x0536)
        cpu.seed(0x1d7,1)
        assert cpu.run(stop=0x056a)
        cpu.seed(0xc,1)
        assert cpu.run(stop=0x03a6)
        cov.capture(cpu,'hardware-sequence-override')
    # Same ROM instruction paths, arbitrary valid 24-bit ratio inputs.
    rng=random.Random(0x5211)
    for i in range(128):
        values={0x60a:rng.choice((0,6,10,255))}
        for base in (0x549,0x54c):
            value=rng.choice((0,1,0xffffff,rng.randrange(1,0x1000000)))
            values.update({base+j:v for j,v in enumerate(value.to_bytes(3,'big'))})
        execute(cov,f'ratio-{i}',{0x1010:rng.choice((0,1))},values,runtime=False)
    for mhz in (12,25,26,49,50,99,100,148):
        for port in (0,1):
            values={}
            for base,value in ((0x549,mhz),(0x54c,270)):
                values.update({base+j:v for j,v in enumerate(value.to_bytes(3,'big'))})
            execute(cov,f'clock-boundary-{mhz}-{port}',{0x1010:port},values,runtime=False)
    # Inputs change between polls: exercise edges impossible under fixed seeds.
    transitions=[(0x03ab,{0x60b:1,0x611:0},0x03e8),
                 (0x03e8,{0x1b4:0},0x03a6),
                 (0x0407,{0xc:1,0x60b:1,0x611:7},0x0443),
                 (0x041b,{0x611:0},0x03a6),
                 (0x042b,{0x611:0},0x03a6),
                 (0x0443,{0x1b4:0},0x03a6),
                 (0x0481,{0x1b4:0},0x03a6),
                 (0x05a7,{0x611:0},0x03a6)]
    for pc,values,stop in transitions:
        rom=bytearray(ROM);rom[0x1112]=0x10
        with CPU(rom) as cpu:
            setup_inputs(cpu);cpu.log_mask(2)
            if pc in (0x041b,0x0443):cpu.seed(0xc,1);cpu.seed(0x60b,1);cpu.seed(0x611,7)
            if pc==0x042b:cpu.seed(0xc,1)
            if pc==0x0481:cpu.seed(0xc,0x20)
            if pc==0x03e8:cpu.seed(0x611,0)
            if pc==0x05a7:cpu.seed(0x60b,1);cpu.seed(0x611,7)
            if pc==0x0407:cpu.seed(0x60b,1);cpu.seed(0x611,7)
            assert cpu.run(stop=pc)
            for addr,v in values.items():cpu.seed(addr,v)
            assert cpu.run(stop=stop)
            cov.capture(cpu,f'transition-{pc:04x}',scope='reset with boundary input changes',
                        inputs={f'{k:04x}':v for k,v in values.items()})
    with CPU(bytearray(ROM[:0x1112])+bytes([0x10])+ROM[0x1113:]) as cpu:
        setup_inputs(cpu);cpu.log_mask(2)
        assert cpu.run(stop=0x056a)
        for b in (0x20,0,0,0x20,0):
            cpu.seed(0xb1,b);assert cpu.run(stop=0x056a)
        cov.capture(cpu,'power-button-edges')
    with CPU(ROM) as cpu:
        setup_inputs(cpu);cpu.log_mask(2)
        assert cpu.run(stop=0x056a)
        cpu.direct(0xa8,0x81);cpu.direct(0x88,0x03)
        assert cpu.run(stop=0x0003)
        # emu8051 does not auto-clear external edge flags on entry; explicitly
        # deassert the synthetic request to test one interrupt, not retriggering.
        cpu.direct(0x88,0x01)
        assert cpu.run(stop=0x056a)
        cov.capture(cpu,'external-interrupt-0',scope='reset then synthetic SFR interrupt request')
    rom=bytearray(ROM);rom[0x1112]=1;rom[0x111b]=5
    with CPU(rom) as cpu:
        setup_inputs(cpu);cpu.seed(0xb0,0);cpu.log_mask(2)
        assert cpu.run(stop=0x056a)
        for _ in range(4):assert cpu.run(stop=0x056a)
        cov.capture(cpu,'timer-counter-carry')
    cov.export('coverage.json')
    return cov


if __name__=='__main__':coverage_campaign()
