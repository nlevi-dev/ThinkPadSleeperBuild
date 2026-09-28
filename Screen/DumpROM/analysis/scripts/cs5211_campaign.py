#!/usr/bin/env python3
"""Repeatable experiments; synthetic peripheral inputs, real ROM instructions."""
import hashlib
import json
import random
import struct
from collections import Counter
from cs5211_blackbox import CPU, ROOT, OUT, setup_inputs, run_boot, run_clock

ROM = bytes.fromhex((ROOT / 'binaries/dump_CS5211.txt').read_text())


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')


def diff(old, new):
    return {k: [old.get(k), new.get(k)] for k in sorted(old.keys() | new.keys())
            if old.get(k) != new.get(k)}


def mutation_campaign():
    baseline = run_boot(ROM)
    assert baseline['reached_link_loop']
    cases = []
    for address in [*range(0x1010, 0x1020), *range(0x1110, 0x1123)]:
        for bit in range(8):
            rom = bytearray(ROM)
            rom[address] ^= 1 << bit
            result = run_boot(rom)
            extended_budget = not result['reached_link_loop']
            if extended_budget:
                result = run_boot(rom,budget=100_000_000)
            cases.append(dict(address=f'{address:04x}', bit=bit,
                              before=ROM[address], after=rom[address],
                              reached=result['reached_link_loop'], pc=result['pc'],
                              extended_budget=extended_budget,
                              instruction_delta=result['instructions']-baseline['instructions'],
                              registers=diff(baseline['registers'], result['registers']),
                              added_coverage=sorted(set(result['coverage'])-set(baseline['coverage'])),
                              removed_coverage=sorted(set(baseline['coverage'])-set(result['coverage'])),
                              unseeded_reads=result['unseeded_reads']))
    save('mutations.json', dict(rom_sha256=hashlib.sha256(ROM).hexdigest(),
                                baseline=baseline, cases=cases))
    print('Mutation campaign:',len(cases),Counter(x['reached'] for x in cases), flush=True)


def clock_campaign():
    cases = []
    # Exact rational rates near all divider boundaries; two DP symbol rates.
    for port in (0, 1, 2, 255):
        for rate in (6, 10):
            for mhz1000 in (12000, 24999, 25000, 25001, 49999, 50000, 50001,
                            99999, 100000, 100001, 108000, 148500, 162000):
                result = run_clock(ROM,port=port,m=mhz1000,n=27000*rate,rate=rate)
                assert result['returned']
                regs = result['registers']
                q = sum(regs[f'{0x564+i:04x}'] << (16-8*i) for i in range(3))
                cases.append(dict(port=port,rate=rate,m=mhz1000,n=27000*rate,
                                  inferred_mhz=mhz1000/1000, q=q,
                                  q_ideal=mhz1000*458752/27000,
                                  e1=regs['00e1'],e7=regs['00e7']))
    save('clock-boundaries.json', cases)
    print('Clock campaign:',len(cases),'max fixed-point error',
          max(abs(x['q']-x['q_ideal']) for x in cases),flush=True)


def selection_campaign():
    cases=[]
    # Give every selector a unique marker in a directly copied profile byte.
    rom=bytearray(ROM)
    for i in range(16):
        rom[0x1011+16*i]=0x40+i
    for gpio in range(256):
        with CPU(rom) as cpu:
            setup_inputs(cpu,profile=gpio)
            assert cpu.run(stop=0x056a)
            actual=cpu.get(1,0x1dc)
            assert actual == 0x40+(gpio&15)
            cases.append(dict(gpio=gpio,value=actual))
    save('profile-selection.json',cases)
    print('Profile selection:',len(cases),'passed',flush=True)


def runtime_campaign():
    cases=[]
    for mode in (0,1,2,3,0x11,0x21):
        for level in (0,5,10):
            for buttons in (0x60,0x20,0x40,0):
                rom=bytearray(ROM)
                rom[0x1112]=mode
                rom[0x111b]=level
                with CPU(rom) as cpu:
                    setup_inputs(cpu)
                    cpu.seed(0xb0,buttons)
                    cpu.seed(0xb1,0x20)
                    assert cpu.run(stop=0x056a)
                    start=cpu.get(10,3)
                    ticks0=cpu.get(10,2)
                    levels=[]
                    for _ in range(3):
                        hits=cpu.get(4,0x056a)
                        assert cpu.run(stop=0x056a,ticks=5_000_000)
                        assert cpu.get(4,0x056a)>hits
                        levels.append(cpu.get(2,0x13))
                    writes=[e for i,e in enumerate(cpu.events()) if i>=start and e[4]==1]
                    pwm=[e for e in writes if e[2]==0xb3]
                    cases.append(dict(mode=mode,initial_level=level,buttons=buttons,
                                      levels=levels,ticks=cpu.get(10,2)-ticks0,
                                      timer_isr_count=cpu.get(4,0xc48),
                                      pwm_writes=len(pwm),pwm_values=sorted(set(e[3] for e in pwm)),
                                      first_pwm_edges=pwm[:8],
                                      other_writes=[e for e in writes if e[2]!=0xb3]))
    save('runtime-buttons.json',cases)
    print('Runtime/button campaign:',len(cases),'passed',flush=True)

    # Two status-loss paths, and an M/N change without status loss.
    cases=[]
    for fault in ('video-ready','lane-status','recovery-marker','mn-without-retrain'):
        with CPU(ROM) as cpu:
            setup_inputs(cpu)
            assert cpu.run(stop=0x056a)
            start=cpu.get(10,3)
            before=cpu.get(1,0x564)
            if fault=='video-ready': cpu.seed(0xc,1)
            elif fault=='lane-status': cpu.seed(0x611,0)
            elif fault=='recovery-marker': cpu.seed(0x1b4,0)
            else: cpu.seed(0x54b,1)
            stop=0x056a if fault=='mn-without-retrain' else 0x03a6
            reached=cpu.run(stop=stop,ticks=5_000_000)
            first=[e for i,e in enumerate(cpu.events()) if i>=start and e[4]==1]
            start=cpu.get(10,3)
            setup_inputs(cpu,m=1,n=5,profile=15)
            restored=cpu.run(stop=0x056a,ticks=5_000_000)
            cases.append(dict(fault=fault,reached=reached,restored=restored,
                              latched_profile=cpu.get(2,8),clock_before=before,
                              clock_after=cpu.get(1,0x564),fault_writes=first,
                              restore_writes=[e for i,e in enumerate(cpu.events()) if i>=start and e[4]==1]))
    save('link-recovery.json',cases)
    print('Link recovery:',len(cases),'cases',flush=True)


def clock_fuzz_campaign():
    rng=random.Random(5211)
    f32=lambda x: struct.unpack('>f',struct.pack('>f',x))[0]
    cases=[]
    for _ in range(512):
        rate=rng.choice((6,10))
        n=rng.randrange(1000,0x1000000)
        m=int(rng.uniform(12,160)*n/(27*rate))
        port=rng.randrange(256)
        with CPU(ROM) as cpu:
            setup_inputs(cpu,m=m,n=n,rate=rate)
            cpu.pc(0xa20)
            cpu.direct(0x81,0x3c)
            cpu.direct(0x3b,0xff)
            cpu.direct(0x3c,0xff)
            cpu.direct(7,port)
            assert cpu.run()
            q=sum(cpu.get(1,0x564+i) << (16-8*i) for i in range(3))
            # Independent native IEEE754 single-precision reference.
            expected_q=int(f32(f32(f32(rate*m)*458752)/f32(n))) & 0xffffff
            pclk=(27*rate*m)//n
            band=0 if pclk>=100 else 1 if pclk>=50 else 2 if pclk>=25 else 3
            expected_e7=(0,2,4,8)[band]
            expected_e1=min(3,band+(port!=0))*16
            case=dict(m=m,n=n,rate=rate,port=port,q=q,expected_q=expected_q,
                      e1=cpu.get(1,0xe1),e7=cpu.get(1,0xe7),
                      expected_e1=expected_e1,expected_e7=expected_e7)
            case['matches']=q==expected_q and case['e1']==expected_e1 and case['e7']==expected_e7
            cases.append(case)
    save('clock-fuzz.json',cases)
    print('Clock independent reference:',Counter(x['matches'] for x in cases),flush=True)


def status_campaign():
    cases=[]
    for lanes in (1,2,0x81,0x82):
        for status in range(256):
            with CPU(ROM) as cpu:
                cpu.seed(0x60b,lanes)
                cpu.seed(0x611,status)
                cpu.pc(0x03ab)
                assert cpu.run(stop=0x03d5,ticks=1000)
                accepted=bool(cpu.get(2,7))
                assert accepted == (status == (7 if lanes&31==1 else 0x77))
                cases.append(dict(lanes=lanes,status=status,accepted=accepted))
    save('status-predicate.json',cases)
    print('Lane status predicate:',len(cases),'passed',flush=True)


def fault_and_power_campaign():
    cases=[]
    for values in ({'m':0,'n':5,'rate':10},{'m':2,'n':0,'rate':10},
                   {'m':0,'n':0,'rate':10},{'m':2,'n':5,'rate':0},
                   {'m':0xffffff,'n':0xffffff,'rate':10}):
        clock=run_clock(ROM,**values)
        boot=run_boot(ROM,**values)
        cases.append(dict(inputs=values,returned=clock['returned'],
                          clock_registers=clock['registers'],
                          reached_link_loop=boot['reached_link_loop']))
    save('invalid-clock-inputs.json',cases)

    cases=[]
    for address in (None,*range(0x1113,0x111b)):
        rom=bytearray(ROM)
        if address is not None: rom[address]+=1
        with CPU(rom) as cpu:
            setup_inputs(cpu)
            assert cpu.run(stop=0x056a)
            boot_ticks=cpu.get(10,2)
            cpu.seed(0xc,1)
            assert cpu.run(stop=0x03a6)
            cases.append(dict(incremented=None if address is None else f'{address:04x}',
                              boot_ticks=boot_ticks,shutdown_ticks=cpu.get(10,2)-boot_ticks,
                              power_writes=[e for e in cpu.events(1) if e[2] in (0xe1,0x1d8)]))
    save('power-delays.json',cases)

    rom=bytearray(ROM)
    rom[0x1112]=0x10
    with CPU(rom) as cpu:
        setup_inputs(cpu)
        assert cpu.run(stop=0x056a)
        start=cpu.get(10,3)
        states=[]
        for button in (0x20,0,0,0x20,0):
            cpu.seed(0xb1,button)
            assert cpu.run(stop=0x056a)
            states.append(dict(button=button,power_register=cpu.get(1,0x1d8)))
        save('power-button.json',dict(states=states,
            writes=[e for i,e in enumerate(cpu.events()) if i>=start and e[4]==1]))
    print('Fault/power campaign: 5 invalid clock cases, 9 delay cases, 1 button sequence',flush=True)


if __name__ == '__main__':
    mutation_campaign()
    clock_campaign()
    selection_campaign()
    runtime_campaign()
    clock_fuzz_campaign()
    status_campaign()
    fault_and_power_campaign()
