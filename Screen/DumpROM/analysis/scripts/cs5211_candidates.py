#!/usr/bin/env python3
"""Generate trace-checked hypotheses, never label an unmeasured image a fix."""
import hashlib
from cs5211_blackbox import ROOT,run_boot
from cs5211_deep import ROM,OUT,save


def main():
    print("CPU EXPERIMENTS ONLY: firmware checksum is not updated; do not use as flash images.", flush=True)
    base_path=ROOT/'binaries/dump_CS5211_edid_only.txt'
    base=bytes.fromhex(base_path.read_text())
    assert len(base)==8192 and base[0x800:]==ROM[0x800:]
    assert all(sum(base[i:i+128])%256==0 for i in range(0,0x800,128))
    output=OUT/'candidates';output.mkdir(exist_ok=True,parents=True)
    baseline=run_boot(base);assert baseline['reached_link_loop']
    original_trace=[(e[2],e[3]) for e in baseline['writes']]
    candidates=[]
    for p in range(12):
        for bit in range(8):
            if (p,bit) in ((0,0),(3,3),(4,3)):continue
            image=bytearray(base)
            offsets=[0x1010+16*i+p for i in range(16)]
            for addr in offsets:image[addr]^=1<<bit
            changed=[i for i,(a,b) in enumerate(zip(base,image)) if a!=b]
            assert changed==offsets
            result=run_boot(image);assert result['reached_link_loop']
            trace=[(e[2],e[3]) for e in result['writes']]
            assert len(trace)==len(original_trace)
            delta=[(a,b) for a,b in zip(original_trace,trace) if a!=b]
            assert len(delta)==1 and delta[0][0][0]==delta[0][1][0]
            assert result['coverage']==baseline['coverage']
            name=f'candidate-p{p:02d}-bit{bit}.bin'
            (output/name).write_bytes(image)
            candidates.append(dict(file=name,tier=2 if p==0 else 1,profile_byte=p,bit=bit,
                physical_offsets=[f'{a:04x}' for a in changed],
                before=base[offsets[0]],after=image[offsets[0]],
                register=f'{delta[0][0][0]:04x}',register_before=delta[0][0][1],register_after=delta[0][1][1],
                sha256=hashlib.sha256(image).hexdigest(),
                status='untested on silicon; no identified JEIDA/18-bit semantics',
                rationale='one opaque profile-register bit; no changed firmware branch or clock calculation in the verified baseline' if p else
                          'upper bit of profile[0]; zero/nonzero clock branch unchanged, hardware field validity unknown'))
    assert len(candidates)==93
    save('candidate-manifest.json',dict(base=str(base_path.relative_to(ROOT)),
        base_sha256=hashlib.sha256(base).hexdigest(),
        ranking='Tier 1: 86 fields outside profile[0]. Tier 2: 7 upper bits of profile[0]. No evidence-based ordering within a tier.',
        excluded='profile[0].bit0 changes clock branch; profile[3].bit3 and profile[4].bit3 are forced; profile[12:16] not read by mapped application',
        scope='single-bit profile hypotheses only; does not exhaust multi-bit fields, fixed instruction constants, global controls, or autonomous pre-code data use',
        candidates=candidates))
    # Construct two different serializer interpretations consistent with all
    # available CPU traces and the assumed baseline low-six-bit symptom.
    def decoded(regs,component,selector):
        return component>>2 if regs[selector]&1 else component&63
    scenarios={'baseline':{0x1dc:0,0x1de:0},'candidate-p01-bit0':{0x1dc:1,0x1de:0},
               'candidate-p02-bit0':{0x1dc:0,0x1de:1}}
    witness=[]
    for name,regs in scenarios.items():
        a=[decoded(regs,v,0x1dc) for v in range(256)]
        b=[decoded(regs,v,0x1de) for v in range(256)]
        witness.append(dict(scenario=name,model_A_matches_ideal=a==[v>>2 for v in range(256)],
                            model_B_matches_ideal=b==[v>>2 for v in range(256)],
                            models_agree=a==b))
    assert witness[0]['models_agree'] and witness[1]['model_A_matches_ideal'] and not witness[1]['model_B_matches_ideal']
    assert witness[2]['model_B_matches_ideal'] and not witness[2]['model_A_matches_ideal']
    save('identifiability-witness.json',dict(
        description='Counterexample to unique selector inference, not a hardware simulation or claim about either candidate.',
        assumptions='Both hypothetical chips retain identical register readback/CPU behaviour and differ only in which undocumented bit selects serializer mapping.',
        model_A='01dc bit0 selects compatible mapping',model_B='01de bit0 selects compatible mapping',
        conclusion='Existing firmware traces and baseline symptom cannot choose between these assignments.',scenarios=witness))
    print('Candidates:',len(candidates),'trace-checked binary images, preserving EDID; selector non-identifiability witness passed',flush=True)


if __name__=='__main__':main()
