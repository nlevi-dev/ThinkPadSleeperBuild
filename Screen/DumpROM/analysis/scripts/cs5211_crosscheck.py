#!/usr/bin/env python3
"""Compare independent uCsim 0.9.9 and emu8051 CPU cores on the same ROM."""
import json
import re
import subprocess
from cs5211_blackbox import ROOT,OUT,run_boot,run_clock


def ihex(rom):
    lines=[]
    firmware=rom[0x1000:]
    for addr in range(0,len(firmware),16):
        data=firmware[addr:addr+16]
        rec=bytes((len(data),addr>>8,addr&255,0))+data
        lines.append(':'+rec.hex()+f'{(-sum(rec))&255:02x}')
    path=OUT/'firmware.ihx'
    path.write_text('\n'.join(lines)+'\n:00000001ff\n')
    return path


def run_ucsim(rom,inputs,boot=False,port=1):
    commands=['fill xram 0 65535 0','fill iram 0 255 0']
    commands += [f'set memory xram 0x{k} {v}' for k,v in inputs.items()]
    if boot:
        commands += ['run 0 0x56a']
    else:
        commands += ['set memory sfr 0x81 0x3c',
                     'set memory iram 0x3b 0xff 0xff',f'set memory iram 7 {port}',
                     'run 0xa20 0xffff']
    commands += ['echo FINAL_MEMORY','dx 0 0x7ff','quit']
    result=subprocess.run(['s51','-q','-c','-',str(ihex(rom))],
                          input='\n'.join(commands)+'\n',text=True,
                          capture_output=True,timeout=30,check=True)
    out=result.stdout.split('FINAL_MEMORY')[-1]
    registers={}
    for line in out.splitlines():
        match=re.match(r'^0x([0-9a-f]+)\s+((?:[0-9a-f]{2} )+)',line)
        if match:
            addr=int(match[1],16)
            for off,value in enumerate(bytes.fromhex(match[2])):
                registers[f'{addr+off:04x}']=value
    assert len(registers)==2048, f'Incomplete memory dump: {len(registers)}'
    return registers,result.stdout


def main():
    rom=bytes.fromhex((ROOT/'binaries/dump_CS5211.txt').read_text())
    baseline=run_boot(rom)
    cases=[dict(kind='boot',inputs=baseline['inputs'],expected=baseline['registers'])]
    fuzz=json.loads((OUT/'clock-fuzz.json').read_text())
    # All discrepancies against host float32 arithmetic, plus a control sample.
    sample=[x for x in fuzz if not x['matches']]+fuzz[:5]
    for x in sample:
        inputs={0x60a:x['rate']}
        for base,value in ((0x549,x['m']),(0x54c,x['n'])):
            inputs.update({base+i:b for i,b in enumerate(value.to_bytes(3,'big'))})
        expected=run_clock(rom,**{k:x[k] for k in ('port','m','n','rate')})['registers']
        cases.append(dict(kind='clock',inputs={f'{k:04x}':v for k,v in inputs.items()},
                          port=x['port'],expected=expected))
    results=[]
    for i,case in enumerate(cases):
        actual,trace=run_ucsim(rom,case['inputs'],boot=case['kind']=='boot',port=case.get('port',1))
        mismatch={k:[v,actual[k]] for k,v in case['expected'].items() if v!=actual[k]}
        results.append(dict(**case,mismatch=mismatch))
        (OUT/f'ucsim-{i:02d}.txt').write_text(trace)
    (OUT/'crosscheck.json').write_text(json.dumps(results,indent=2)+'\n')
    print('Independent CPU comparison:',len(results),'cases;',sum(bool(x['mismatch']) for x in results),'mismatches')
    assert all(not x['mismatch'] for x in results)


if __name__=='__main__':
    main()
