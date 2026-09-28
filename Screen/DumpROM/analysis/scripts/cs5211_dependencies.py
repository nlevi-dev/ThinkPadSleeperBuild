#!/usr/bin/env python3
"""Configuration dependency catalogue plus interaction experiments."""
from cs5211_blackbox import CPU,setup_inputs
from cs5211_deep import ROM,save


def catalogue():
    fields=[]
    targets=(0x9f,0x1dc,0x1de,0x1e1,0x1e2,0x1e3,0x1e4,0x1e7,0x1ed,0x1f2,0x1f3,0x1f4)
    for p in range(16):
        for bit in range(8):
            used=p<12 and (p,bit) not in ((3,3),(4,3))
            row=dict(region='profile',byte=p,bit=bit,
                     physical_formula=f'0x1010 + 16 * profile_index + {p}',
                     selection='profile_index = XDATA[00ca] & 15, latched at reset',
                     firmware_effective=used,
                     target=f'{targets[p]:04x}' if p<12 else None,
                     application='initial link setup and every subsequent successful recovery')
            if p>=12:row['effect']='no MOVC use in mapped application'
            elif not used:row['effect']='forced clear' if p==3 else 'forced set'
            elif p==11 and bit>=4:
                row['effect']=f'OR with ROM[1122].bit{bit-4}; cannot clear output if global bit is set'
            elif p==0:row['effect']='direct bit; changing whole byte zero/nonzero also changes clock branch'
            else:row['effect']='direct output bit; silicon semantics unknown'
            fields.append(row)
    global_targets={0:'0602',1:'0603',3:'01d1',4:'01f7',5:'01d0',6:'01d3',7:'01f8',8:'01d4',9:'01f9',10:'01d6'}
    for g in range(19):
        for bit in range(8):
            row=dict(region='global',physical=f'{0x1110+g:04x}',bit=bit)
            if g in global_targets:
                row.update(firmware_effective=not(g==1 and bit==7),target=global_targets[g],
                           effect='direct bit at initialization')
                if g==1:row['effect']='OR with 0x80 retained from firmware write of 0x82; bit 7 forced set'
                if 3<=g<=10:row['effect']+='; also participates in 16-bit wrapping busy-wait argument'
            elif g==2:
                row.update(firmware_effective=bit in (0,1,4,5),
                    effect={0:'low two bits jointly select brightness mode',1:'low two bits jointly select brightness mode',
                            4:'enable power-button routine and clear its state on link loss',
                            5:'swap brightness button directions, effective only if low two bits == 1'}.get(bit,'not used by mapped application'))
            elif g==11:
                row.update(firmware_effective=True,effect='initial level if whole byte <= 10; otherwise level=10, lower=0, upper=10')
            elif g in (12,13):
                row.update(firmware_effective=True,effect=('lower' if g==12 else 'upper')+' raw level bound',
                           condition='ROM[111b] <= 10; affects later output through buttons when (ROM[1112] & 3) == 1')
            elif g==14:
                row.update(firmware_effective=bit==0,effect='bit 0 selects 01bb/00e3 setup and gates 111f..1121 copy' if bit==0 else 'not used by mapped application')
            elif g in (15,16,17):
                row.update(firmware_effective=True,target=f'{0xe4+g-15:04x}',
                           condition='(ROM[111e] & 1) == 0 AND ROM[1121] != 0xaa',
                           effect='full byte copy; 1121 also serves as whole-byte sentinel')
            elif g==18:
                row.update(firmware_effective=bit<4,target='01f4' if bit<4 else None,
                           effect=f'OR into output bit {bit+4} with profile[11]; cannot clear profile-set bit' if bit<4 else 'not used by mapped application')
            fields.append(row)
    save('configuration-bits.json',dict(scope='firmware reads/writes only; no claim about autonomous hardware ROM loading',
                                       fields=fields))


def main():
    catalogue();interactions=[]
    for profile in range(256):
        for global_low in range(16):
            rom=bytearray(ROM);rom[0x101b]=profile;rom[0x1122]=global_low
            with CPU(rom) as cpu:
                cpu.log_mask(0);cpu.pc(0x0511)
                assert cpu.run(stop=0x0525,ticks=1000)
                actual=cpu.get(1,0x1f4)
                assert actual==profile|(global_low<<4)
                interactions.append(dict(profile=profile,global_low=global_low,output=actual))
    save('profile-global-or.json',interactions)
    gates=[]
    for flag in range(256):
        for sentinel in (0,0xaa,0xff):
            rom=bytearray(ROM);rom[0x111e]=flag;rom[0x111f:0x1122]=bytes((0x5a,0xa5,sentinel))
            with CPU(rom) as cpu:
                setup_inputs(cpu);cpu.log_mask(0)
                assert cpu.run(stop=0x03a6)
                copied=bool(cpu.get(8,0xe4))
                assert copied== (not flag&1 and sentinel!=0xaa)
                gates.append(dict(flag=flag,sentinel=sentinel,copied=copied))
    save('conditional-global-copy.json',gates)
    levels=[]
    for level in range(256):
        rom=bytearray(ROM);rom[0x111b:0x111e]=bytes((level,3,8))
        with CPU(rom) as cpu:
            setup_inputs(cpu);cpu.log_mask(0);assert cpu.run(stop=0x03a6)
            actual=[cpu.get(2,a) for a in (0x13,0xf,0x10)]
            assert actual==([level,3,8] if level<=10 else [10,0,10])
            levels.append(dict(input=level,level_lower_upper=actual))
    save('initial-level-gate.json',levels)
    # A configuration interaction that the original one-bit boot tests miss:
    # accepted initial level 10 + upper bound 11 + enabled up button => level 11.
    rom=bytearray(ROM);rom[0x1112]=1;rom[0x111d]=11
    with CPU(rom) as cpu:
        setup_inputs(cpu);cpu.seed(0xb0,0x20);cpu.log_mask(0)
        assert cpu.run(stop=0x056a);assert cpu.run(stop=0x056a)
        assert cpu.get(2,0x13)==11
        assert cpu.run(stop=0x0c76,ticks=300000)
        index=cpu.get(2,0)
        assert index==0x21
        save('brightness-out-of-table.json',dict(patches={'1112':1,'111d':11},
             input={'00b0':0x20},level=11,isr_index=f'{index:02x}',
             intended_table='16..20',pc='0c76',
             conclusion='Button limits can drive the timer lookup outside its 11-byte table; not a colour-mapping discovery.'))
    print('Dependencies: 280 bit records; 4096 OR combinations; 768 gated-copy cases; 256 level cases; out-of-table case reproduced',flush=True)


if __name__=='__main__':main()
