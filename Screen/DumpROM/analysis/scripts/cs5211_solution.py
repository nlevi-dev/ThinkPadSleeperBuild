#!/usr/bin/env python3
"""Reconcile pre-solution candidates with Levi's committed solution, without flashing."""
import hashlib
import importlib.util
import json
import zlib
from cs5211_blackbox import ROOT, CPU, setup_inputs, build


def main():
    build()
    original=bytes.fromhex((ROOT/'binaries/dump_CS5211.txt').read_text())
    prior=bytes.fromhex((ROOT/'binaries/dump_CS5211_edid_only.txt').read_text())
    solved=bytes.fromhex((ROOT.parent/'dump_CS5211_patched_8bit_jeida.txt').read_text())
    assert len(original)==len(prior)==len(solved)==8192
    assert prior[0x800:]==original[0x800:]
    offsets=[0x1013+16*i for i in range(16)]
    changed=[i for i,(a,b) in enumerate(zip(prior,solved)) if a!=b]
    assert changed==list(range(0xffa,0xffe))+offsets
    assert solved[0xffa:0xffe]==bytes.fromhex('da960552')
    assert all(prior[i]==1 and solved[i]==5 for i in offsets)
    assert all(sum(solved[i:i+128])%256==0 for i in range(0,0x800,128))
    candidate=bytearray(prior)
    for i in offsets:candidate[i]^=4
    old_manifest=json.loads((ROOT/'artifacts/cs5211-deep/candidate-manifest.json').read_text())
    recorded=next(x for x in old_manifest['candidates'] if x['file']=='candidate-p03-bit2.bin')
    assert hashlib.sha256(candidate).hexdigest()==recorded['sha256']
    # Verify the complete disassembled instruction sequence, not just destination bytes.
    assert prior[0x14bd:0x14c9]==bytes.fromhex('e5089000139354f79001e1f0')
    spec=importlib.util.spec_from_file_location('levi_patcher',ROOT.parent/'patch_cs5211.py')
    patcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(patcher)
    patched=bytearray(original);edid=patcher.load_edid_csv(ROOT.parent/'edid_dump_LTN141P4.csv')
    assert patcher.patch(patched,edid)==16
    assert bytes(patched)==solved
    checks=[]
    for profile in range(16):
        states=[]
        for image in (prior,candidate,solved):
            with CPU(image) as cpu:
                setup_inputs(cpu,profile=profile);cpu.log_mask(2)
                assert cpu.run(stop=0x56a)
                states.append((list(cpu.events(1)),[cpu.get(1,i) for i in range(2048)]))
        assert states[1]==states[2] # This exposes the emulator's missing validation boundary.
        delta=[i for i,(a,b) in enumerate(zip(states[0][1],states[2][1])) if a!=b]
        assert delta==[0x1e1] and states[2][1][0x1e1]==5
        assert len(states[0][0])==len(states[2][0])
        events=[(a,b) for a,b in zip(states[0][0],states[2][0]) if a!=b]
        assert len(events)==1 and events[0][0][1:4]==(0x4c8,0x1e1,1)
        assert events[0][1][1:4]==(0x4c8,0x1e1,5)
        checks.append(dict(profile=profile,only_changed_register='01e1',before=1,after=5,
                           checksum_stale_candidate_and_solution_identical_CPU_trace=True))
    mode_checks=[]
    for (eight,vesa),(mode,checksum) in patcher._SLOT_MODES.items():
        rom=bytearray(original)
        for i in offsets:rom[i]=mode
        rom[0xffa:0xffe]=checksum.to_bytes(4,'big')
        with CPU(rom) as cpu:
            setup_inputs(cpu);assert cpu.run(stop=0x56a)
            assert cpu.get(1,0x1e1)==mode
        delta=zlib.crc32(original[0x1000:0x1e84])^zlib.crc32(rom[0x1000:0x1e84])
        predicted=int.from_bytes(original[0xffa:0xffe],'big')^int(f'{delta:032b}'[::-1],2)
        assert predicted==checksum
        mode_checks.append(dict(predicted_checksum=f'{predicted:08x}',crc_difference_matches=True,
                               bits_per_component=8 if eight else 6,mapping='VESA' if vesa else 'JEIDA',
                               mode=f'{mode:02x}',reported_checksum=f'{checksum:08x}',
                               provenance='Levi patcher table; not independent hardware measurement'))
    out=ROOT/'artifacts/cs5211-solution';out.mkdir(exist_ok=True)
    result=dict(solution_commit='93c5c9f2e0772ec6089b54aa51863dafe25a8505',
        hashes={k:hashlib.sha256(v).hexdigest() for k,v in [('original',original),('edid_only',prior),('candidate',candidate),('solution',solved)]},
        changed_offsets=[f'{i:04x}' for i in changed],profiles=checks,modes=mode_checks,
        patcher_reproduces_solution_exactly=True,
        checksum_hypothesis='stored_old XOR reverse32(crc32(old[1000:1e84]) XOR crc32(new[1000:1e84])); fits all 4 table entries, not an identified general loader algorithm',
        crc32_checks={k:dict(stored=x[0xffa:0xffe].hex(),full_tail=f'{zlib.crc32(x[0x1000:]):08x}',
            length_0e86=f'{zlib.crc32(x[0x1000:0x1e86]):08x}') for k,x in [('original',original),('solution',solved)]})
    (out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Solution reproduced exactly; 16 profile comparisons and 4 declared modes passed.')
    print('Stale-checksum candidate and solved image are indistinguishable to the CPU harness.')

if __name__=='__main__':main()
