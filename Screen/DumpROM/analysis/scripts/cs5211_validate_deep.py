#!/usr/bin/env python3
"""Independent checks and explicit classification of coverage limits."""
import hashlib
import json
import cs5211_crosscheck as cross
from cs5211_blackbox import CPU,setup_inputs
from cs5211_deep import ROM,OUT,INS,BRANCH,save
from cs5211_model import Firmware,MemoryIO


def main():
    coverage=json.loads((OUT/'coverage.json').read_text())
    def app(pc):return pc<0x13f or 0x1c0<=pc<0x647 or pc>=0xa20
    pcs={int(p,16) for p in coverage['pcs']}
    edges={(int(p,16),e) for p,e in coverage['edges']}
    impossible={(0x03e6,1),(0x0c9d,2),(0x0e67,1)}
    missing={(p,e) for p in BRANCH if app(p) for e in (1,2) if (p,e) not in edges}
    assert missing==impossible
    assert {p for p in INS if app(p) and p not in pcs}=={0x0e69}
    assert all((v|1)!=0 for v in range(256))
    count=0;visited=[]
    while True:
        count+=1;visited.append(count)
        if count>200:break
    assert max(visited)==201 and all(v&255 for v in visited)
    save('coverage-classification.json',dict(
        application_definition='Vectors/reset through 013e; main 01c0..0646; application helpers a20..e1e and e5c..e83. Generic C startup parser and arithmetic libraries counted separately.',
        application_instructions=sum(app(p) for p in INS),application_executed=sum(app(p) for p in pcs),
        application_branch_edges=2*sum(app(p) for p in BRANCH),application_executed_edges=sum(app(p) for p,e in edges),
        excluded_edges=[dict(pc='03e6',edge='fallthrough',reason='Every possible byte OR 1 is nonzero; JNZ always taken.'),
                        dict(pc='0c9d',edge='taken',reason='Level 10 already returned at 0c60/0c68; firmware cannot change the level while this ISR is running.'),
                        dict(pc='0e67',edge='fallthrough',reason='Wait counter starts at zero and exits after 201; its low byte never wraps to zero. Consequently 0e69 is unreachable in these application calls.')],
        caveats=['Synthetic inputs exercise branches, not silicon behaviour.',
                 'External interrupt 0 is deliberately injected; ordinary ROM initialization enables Timer0 only.',
                 'No claim of whole-library coverage: unused startup record formats, signed/exceptional float paths and generic helper inputs remain outside the application proof.',
                 'A global mutable peripheral model, asynchronous DMA into IRAM, executable-code patches, or corrupt CPU state would change the assumptions.']))
    cross.OUT=OUT/'independent';cross.OUT.mkdir(exist_ok=True)
    variants=[{}, {0x111e:0,0x111f:0x5a,0x1120:0xa5,0x1121:255},
              {0x111e:0,0x1121:0xaa}, {0x1112:2,0x1010:0},
              {0x1112:1,0x111b:5,0x111c:3,0x111d:8},
              {0x111b:11}, {0x1010:3,0x1013:9,0x1014:0,0x101b:0xab,0x1122:15},
              {0x1110:6,0x1111:0x81}]
    results=[]
    for i,patch in enumerate(variants):
        rom=bytearray(ROM)
        for a,v in patch.items():rom[a]=v
        with CPU(rom) as cpu:
            seeds=setup_inputs(cpu,rate=6 if i==7 else 10)
            assert cpu.run(stop=0x056a)
            expected={f'{a:04x}':cpu.get(1,a) for a in range(0x800)}
        io=MemoryIO(seeds);model=Firmware(rom,io)
        for _ in range(1000):
            model.step()
            if model.state=='steady':break
        assert model.state=='steady'
        model_memory={f'{a:04x}':io.memory.get(a,0) for a in range(0x800)}
        assert expected==model_memory
        actual,trace=cross.run_ucsim(rom,{f'{a:04x}':v for a,v in seeds.items()},boot=True)
        (cross.OUT/f'case-{i}.txt').write_text(trace)
        (cross.OUT/'firmware.ihx').rename(cross.OUT/f'case-{i}.ihx')
        mismatch={a:[expected[a],actual[a]] for a in expected if expected[a]!=actual[a]}
        assert not mismatch,(i,mismatch)
        results.append(dict(case=i,patch={f'{a:04x}':v for a,v in patch.items()},
                            rom_sha256=hashlib.sha256(rom).hexdigest(),
                            compared_xdata_bytes=2048,three_way_match=True))
    save('independent-model-check.json',results)
    print('Coverage classified; independent three-way comparison:',len(results),'ROM configurations, all 2048 XDATA bytes match',flush=True)


if __name__=='__main__':main()
