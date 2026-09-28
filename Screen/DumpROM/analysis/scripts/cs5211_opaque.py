#!/usr/bin/env python3
"""Bounded, explicit interpretation tests for the opaque pre-code ROM blocks."""
import hashlib
import math
import random
import zlib
from collections import Counter
from cs5211_deep import ROM,save,OUT


def bm(sequence):
    """Berlekamp-Massey over GF(2), return shortest linear recurrence."""
    c=b=1;length=0;shift=1
    for n in range(len(sequence)):
        discrepancy=sequence[n]
        for i in range(1,length+1):discrepancy^=((c>>i)&1)&sequence[n-i]
        if discrepancy:
            previous=c;c^=b<<shift
            if 2*length<=n:length=n+1-length;b=previous;shift=1
            else:shift+=1
        else:shift+=1
    return length,c


def monotonic(values):
    return all(a<=b for a,b in zip(values,values[1:])) or all(a>=b for a,b in zip(values,values[1:]))


def main():
    header=ROM[0x800:0x804];block=ROM[0x804:0x884]
    assert block==ROM[0x884:0x904]==ROM[0x904:0x984]
    counts=Counter(block)
    result=dict(header=header.hex(),block_sha256=hashlib.sha256(block).hexdigest(),
                identical_blocks=3,histogram=dict(sorted(counts.items())),
                entropy_bits_per_nibble=-sum(n/128*math.log2(n/128) for n in counts.values()),
                unsigned_delta_sum=sum(block),signed_delta_sum=sum(v if v<8 else v-16 for v in block))
    interpretations={'raw_nibbles':list(block)}
    for n in (2,4):
        for reverse in (False,True):
            values=[]
            for i in range(0,128,n):
                digits=block[i:i+n][::-1] if reverse else block[i:i+n]
                value=0
                for digit in digits:value=value*16+digit
                values.append(value)
            interpretations[f'packed_{n}_nibbles_reverse_{reverse}']=values
    result['direct_curve_tests']={k:dict(values=v,monotonic=monotonic(v),
                                         descending_steps=sum(a>b for a,b in zip(v,v[1:])))
                                  for k,v in interpretations.items()}
    result['alphabet_relabeling_obstruction']={'positions':[0,1,3],
        'values':[block[0],block[1],block[3]],
        'reason':'A,B,A with A != B cannot be monotonic under any bijective value relabeling.'}
    # Raw linear recurrence tests include each bit plane and both serial orders.
    streams={f'bit_{bit}':[v>>bit&1 for v in block] for bit in range(4)}
    streams.update({f'serial_{order}':[v>>bit&1 for v in block for bit in bits]
                    for order,bits in [('lsb',range(4)),('msb',range(3,-1,-1))]})
    result['linear_complexity']={k:dict(bits=len(v),degree=bm(v)[0],polynomial=hex(bm(v)[1])) for k,v in streams.items()}
    result['bayer_tile_tests']={str(n):[len(set(block[i:i+n])) for i in range(0,128,n)] for n in (4,16)}
    packed=bytes((block[i]<<4)|block[i+1] for i in range(0,128,2))
    checksum=[]
    for name,data in [('one_block',block),('three_blocks',block*3),('packed',packed),('packed_three',packed*3)]:
        values={'crc32':zlib.crc32(data),'adler32':zlib.adler32(data),
                'md5_prefix':int.from_bytes(hashlib.md5(data).digest()[:4],'big'),
                'sha256_prefix':int.from_bytes(hashlib.sha256(data).digest()[:4],'big')}
        checksum += [dict(data=name,algorithm=k,value=f'{v:08x}',
                          matches=v in (int.from_bytes(header,'big'),int.from_bytes(header,'little')))
                     for k,v in values.items()]
    result['header_checks']=checksum
    # Predetermined common 32-bit generators; no fitted arbitrary key stream.
    generators={name:(lambda s,a=a,c=c:(a*s+c)&0xffffffff) for name,a,c in
                [('ansi_lcg',1103515245,12345),('msvc_lcg',214013,2531011),
                 ('numerical_recipes_lcg',1664525,1013904223),('borland_lcg',22695477,1)]}
    def xorshift(s):
        s^=(s<<13)&0xffffffff;s^=s>>17;s^=(s<<5)&0xffffffff;return s&0xffffffff
    generators['xorshift_13_17_5']=xorshift
    best=[];tested=0
    for endian in ('big','little'):
        seed=int.from_bytes(header,endian)
        for name,step in generators.items():
            states=[];s=seed
            for _ in range(160):states.append(s);s=step(s)
            for skip in range(33):
                for shift in range(29):
                    candidate=[(s>>shift)&15 for s in states[skip:skip+128]]
                    prefix=0
                    for a,b in zip(candidate,block):
                        if a!=b:break
                        prefix+=1
                    best.append(dict(endian=endian,generator=name,skip=skip,shift=shift,prefix=prefix,
                                     matching_positions=sum(a==b for a,b in zip(candidate,block))))
                    tested+=1
    result['prng_tests']=dict(tested=tested,exact_matches=[x for x in best if x['prefix']==128],
                              best_prefix=sorted(best,key=lambda x:x['prefix'],reverse=True)[:5])
    # An unsigned-delta interpretation is monotonic by construction. Compare its
    # closeness to a straight line with a seeded shuffled-order null model.
    def linear_error(values):
        running=0;total=sum(values)
        return max(abs((running:=running+v)/total-(i+1)/len(values)) for i,v in enumerate(values))
    observed=linear_error(block);rng=random.Random(521103)
    errors=[]
    for _ in range(10000):
        candidate=list(block);rng.shuffle(candidate);errors.append(linear_error(candidate))
    result['unsigned_delta_linear_shape']=dict(max_normalized_error=observed,
        permutation_null_trials=len(errors),fraction_at_least_as_linear=sum(e<=observed for e in errors)/len(errors),
        caveat='Cannot reject an arbitrary delta-encoded calibration table; normalization removes the unknown endpoint.')
    save('opaque-tests.json',result)
    print('Opaque tests:',len(checksum),'header checks;',tested,'fixed PRNG hypotheses;',
          len(errors),'permutation controls; direct monotonic encodings',
          [k for k,v in result['direct_curve_tests'].items() if v['monotonic']],flush=True)
    print('Linear complexities:',{k:v['degree'] for k,v in result['linear_complexity'].items()},flush=True)


if __name__=='__main__':main()
