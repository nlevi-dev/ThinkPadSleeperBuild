#!/usr/bin/env python3
"""Bounded coupled-field and instruction-literal experiments; no silicon model."""
import hashlib
import json
from cs5211_blackbox import ROOT, CPU, setup_inputs
from cs5211_deep import INS
import cs5211_crosscheck as cross

OUT=ROOT/'artifacts/cs5211-register-structure'
BASE=bytes.fromhex((ROOT/'binaries/dump_CS5211_edid_only.txt').read_text())

def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2)+'\n')

def execute(rom,profile=0):
    with CPU(rom) as c:
        inputs=setup_inputs(c,profile=profile);c.log_mask(3)
        assert c.run(stop=0x56a)
        boot=list(c.events(1)); memory={f'{i:04x}':c.get(1,i) for i in range(2048)}
        coverage=c.summary()['coverage']
        c.clear_events();c.seed(0xc,1);assert c.run(stop=0x3a6)
        c.seed(0xc,0x21);assert c.run(stop=0x56a)
        recovery=list(c.events(1))
        return dict(boot=boot,recovery=recovery,memory=memory,
                    recovery_memory={f'{i:04x}':c.get(1,i) for i in range(2048)},coverage=coverage,
                    inputs={f'{k:04x}':v for k,v in inputs.items()})

def diff(a,b):
    aa=[(e[1],e[2],e[3]) for e in a];bb=[(e[1],e[2],e[3]) for e in b]
    assert len(aa)==len(bb)
    assert [(p,r) for p,r,v in aa]==[(p,r) for p,r,v in bb]
    return [dict(pc=f'{p:04x}',register=f'{r:04x}',before=v,after=w)
            for (p,r,v),(_,_,w) in zip(aa,bb) if v!=w]

def main():
    print("CPU EXPERIMENTS ONLY: firmware checksum is not updated; do not use as flash images.", flush=True)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'candidates').mkdir(exist_ok=True)
    baseline=execute(BASE);save('baseline.json',baseline)
    variants=[]
    def add(name,family,assign):
        rom=bytearray(BASE)
        for a,v in assign.items():rom[a]=v
        if rom!=BASE:variants.append((name,family,bytes(rom)))
    def paired(p,q,bit,value):
        return {0x1010+16*i+j:(BASE[0x1010+16*i+j]&~(1<<bit))|(value<<bit)
                for i in range(16) for j in (p,q)}
    # Matched assignments, not merely XOR: p3/p4 bit0 start unequal.
    for p,q in ((3,4),(8,9)):
        for bit in range(8):
            if (p,q,bit)==(3,4,3):continue
            for value in (0,1):
                add(f'pair-p{p}-p{q}-bit{bit}-v{value}','paired-profile',paired(p,q,bit,value))
    # Equal nibbles in 01f3 are a weaker structural hypothesis.
    for bit in range(4):
        add(f'p10-matched-nibbles-bit{bit}','matched-nibbles',
            {0x1010+16*i+10:BASE[0x1010+16*i+10]^(0x11<<bit) for i in range(16)})
    # A zero result requires clearing BOTH possible sources of each high bit.
    for bit in range(4):
        for value in (0,1):
            patch={0x1010+16*i+11:(BASE[0x1010+16*i+11]&~(1<<(bit+4)))|(value<<(bit+4)) for i in range(16)}
            patch[0x1122]=(BASE[0x1122]&~(1<<bit))|(value<<bit)
            add(f'p11-global-matched-bit{bit}-v{value}','overlapping-or-sources',patch)
    # Targeted opaque bank constants, including the shared source for EC/F1.
    for pc in (0x20f,0x219,0x285,0x2ba):
        assert BASE[0x1000+pc]==0x74
        for bit in range(8):
            a=0x1000+pc+1
            add(f'literal-{a:04x}-bit{bit}','fixed-instruction-literal',{a:BASE[a]^(1<<bit)})
    manifest=[];seen=set()
    for name,family,rom in variants:
        digest=hashlib.sha256(rom).hexdigest()
        if digest in seen:continue
        seen.add(digest);result=execute(rom)
        assert result['coverage']==baseline['coverage']
        boot=diff(baseline['boot'],result['boot']);recovery=diff(baseline['recovery'],result['recovery'])
        assert boot
        # Confirm strap-selected record 15 is patched as consistently as record 0.
        other=execute(rom,15);assert other['memory']==result['memory']|{'00ca':15}
        assert rom[:0x1000]==BASE[:0x1000]
        filename=name+'.bin';(OUT/'candidates'/filename).write_bytes(rom)
        manifest.append(dict(file=filename,family=family,sha256=digest,
            patches=[dict(offset=f'{i:04x}',before=a,after=b) for i,(a,b) in enumerate(zip(BASE,rom)) if a!=b],
            boot_delta=boot,recovery_delta=recovery,
            retained_after_recovery={d['register']:result['recovery_memory'][d['register']] for d in boot},
            same_coverage=True,profiles_checked=[0,15]))
    save('candidates.json',dict(base_sha256=hashlib.sha256(BASE).hexdigest(),
         boundary='Actual CPU execution with synthetic peripheral readiness; no serializer, reserved-bit, or hardware validity inference.',candidates=manifest))
    print('Coupled/literal candidates:',len(manifest),flush=True)
    # Audit every MOV A,#imm in the straight-line initialization region.
    audit=[]
    for pc,ins in sorted(INS.items()):
        if not 0x1c0<=pc<0x2c2 or ins['bytes'][0]!='74':continue
        for alternate in (False,True):
            base=bytearray(BASE)
            if alternate:base[0x111e]=0
            control=execute(base)
            if f'{pc:04x}' not in control['coverage']:continue
            rows=[]
            for bit in range(8):
                rom=bytearray(base);rom[0x1000+pc+1]^=1<<bit
                result=execute(rom)
                rows.append(dict(bit=bit,boot_delta=diff(control['boot'],result['boot']),
                                 recovery_delta=diff(control['recovery'],result['recovery']),
                                 same_coverage=result['coverage']==control['coverage']))
            audit.append(dict(pc=f'{pc:04x}',operand=f'{0x1001+pc:04x}',original=BASE[0x1001+pc],
                              alternate_global111e=alternate,bits=rows))
    save('literal-audit.json',audit);print('Literal audit:',sum(len(x['bits']) for x in audit),'executions',flush=True)
    cross.OUT=OUT/'independent';cross.OUT.mkdir(exist_ok=True)
    checks=[]
    names=[manifest[0]['file']]+[next(x['file'] for x in manifest if x['file'].startswith(prefix)) for prefix in
        ('pair-p8','p10-','p11-global','literal-1210','literal-121a','literal-1286','literal-12bb')]
    for i,name in enumerate(names):
        rom=(OUT/'candidates'/name).read_bytes();expected=execute(rom)
        actual,log=cross.run_ucsim(rom,expected['inputs'],boot=True)
        assert actual==expected['memory'],name
        (cross.OUT/f'case-{i}.txt').write_text(log)
        checks.append(dict(file=name,all_2048_xdata_bytes_match=True))
    save('independent-checks.json',checks)
    print('Independent uCsim:',len(checks),'complete XDATA matches',flush=True)

if __name__=='__main__':main()
