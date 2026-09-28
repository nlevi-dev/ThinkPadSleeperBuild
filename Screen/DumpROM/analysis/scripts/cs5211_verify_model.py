#!/usr/bin/env python3
"""Differentially verify the readable model against original CPU execution."""
import random
from cs5211_blackbox import CPU,setup_inputs
from cs5211_deep import ROM,save
from cs5211_model import Firmware,ReplayIO,MemoryIO,clock_numbers


def foreground(cpu):
    return [(e[4],e[2],e[3]) for e in cpu.events() if e[4]<2 and not 0xc48<=e[1]<=0xcbb]


def replay(rom,trace):
    io=ReplayIO(trace);model=Firmware(rom,io)
    steps=0
    while io.index<len(trace):
        model.step();steps+=1
        assert steps<10000
    assert io.index==len(trace)
    return model,steps


def main():
    rng=random.Random(5211004);results=[]
    for i in range(256):
        rom=bytearray(ROM)
        # All mode bytes; randomized independent profile fields, GPIO, levels,
        # global flags and low delay bytes. No executable instructions patched.
        rom[0x1010:0x1110]=bytes(rng.randrange(256) for _ in range(256))
        for j in (0,1,3,5,6,8,10,11,12,13,14,15,16,17,18):rom[0x1110+j]=rng.randrange(256)
        rom[0x1112]=i
        if i%4==0:rom[0x111b]=5
        if i%5==0:rom[0x111e]=0;rom[0x1121]=0xaa
        with CPU(rom) as cpu:
            setup_inputs(cpu,profile=rng.randrange(256),m=rng.randrange(1,1000),n=2000,
                         lanes=1 if i%2 else 2)
            for a in (6,0x1f,0xaa,0xe1,0x554,0x613):cpu.seed(a,rng.randrange(256))
            cpu.seed(0xb0,(0,0x20,0x40,0x60)[i%4]);cpu.seed(0xb1,0x20)
            cpu.log_mask(3)
            assert cpu.run(stop=0x056a)
            for b in (0x20,0,0x20,0):
                cpu.seed(0xb1,b);assert cpu.run(stop=0x056a)
            cpu.seed(0xc,1);assert cpu.run(stop=0x03a6)
            trace=foreground(cpu)
            model,steps=replay(rom,trace)
            assert model.ram[0x13]==cpu.get(2,0x13)
            results.append(dict(case=i,events=len(trace),model_steps=steps,matched=True))
    for ready in (1,0x20):
        with CPU(ROM) as cpu:
            setup_inputs(cpu);cpu.seed(0xc,ready);cpu.log_mask(3)
            assert cpu.run(stop=0x0494,ticks=8_000_000);assert cpu.run(stop=0x03a6)
            model,steps=replay(ROM,foreground(cpu))
            results.append(dict(case=f'timeout-{ready}',events=len(foreground(cpu)),model_steps=steps,matched=True))
    for where in (0x03e8,0x0443,0x0481,0x056a):
        with CPU(ROM) as cpu:
            setup_inputs(cpu);cpu.log_mask(3)
            if where==0x03e8:cpu.seed(0x611,0)
            if where==0x0443:cpu.seed(0xc,1)
            if where==0x0481:cpu.seed(0xc,0x20)
            assert cpu.run(stop=where);cpu.seed(0x1b4,0)
            assert cpu.run(stop=0x03a6)
            model,steps=replay(ROM,foreground(cpu))
            results.append(dict(case=f'recovery-{where:04x}',events=len(foreground(cpu)),model_steps=steps,matched=True))
    save('model-traces.json',results)
    print('Application model:',len(results),'traces;',sum(r['events'] for r in results),'ordered XDATA events matched',flush=True)

    clocks=[]
    for i in range(2048):
        m=rng.randrange(0x1000000);n=rng.randrange(0x1000000);rate=rng.randrange(256);port=rng.randrange(256)
        if i<4:m,n,rate=((0,1,10),(1,0,10),(0,0,10),(0xffffff,0xffffff,10))[i]
        with CPU(ROM) as cpu:
            setup_inputs(cpu,m=m,n=n,rate=rate);cpu.log_mask(0)
            cpu.pc(0xa20);cpu.direct(0x81,0x3c);cpu.direct(0x3b,255);cpu.direct(0x3c,255);cpu.direct(7,port)
            assert cpu.run()
            actual=(sum(cpu.get(1,0x564+j)<<(16-8*j) for j in range(3)),cpu.get(1,0xe7),cpu.get(1,0xe1))
            expected=clock_numbers(m,n,rate,port)
            assert actual==expected,(i,m,n,rate,actual,expected)
            clocks.append(dict(m=m,n=n,rate=rate,port=port,q=actual[0],matched=True))
    save('model-clock-wide.json',clocks)
    print('Clock model:',len(clocks),'wide-domain cases matched',flush=True)

    isrs=[]
    for level in range(11):
        for phase in (0,1):
            for count in (0,255):
                io=MemoryIO();model=Firmware(ROM,io)
                model.ram[0x13]=level;model.ram[0x15]=phase;model.ram[0xa]=count
                with CPU(ROM) as cpu:
                    cpu.log_mask(3)
                    for a in range(0x80):cpu.direct(a,model.ram[a])
                    cpu.direct(0x81,0x60);cpu.direct(0x5f,255);cpu.direct(0x60,255)
                    cpu.pc(0xc48);assert cpu.run()
                    model.timer_isr()
                    trace=[(e[4],e[2],e[3]) for e in cpu.events() if e[4]<2]
                    assert trace==io.trace
                    for a in (9,10,0x15):assert model.ram[a]==cpu.get(2,a)
                    if level!=10:
                        assert model.timer_high==cpu.get(3,0x8c) and model.timer_low==cpu.get(3,0x8a)
                    isrs.append(dict(level=level,phase=phase,counter=count,matched=True))
    save('model-isr.json',isrs)
    print('Timer model:',len(isrs),'cases matched',flush=True)


if __name__=='__main__':main()
