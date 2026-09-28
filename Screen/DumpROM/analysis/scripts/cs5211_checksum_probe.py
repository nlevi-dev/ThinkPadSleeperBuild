#!/usr/bin/env python3
"""Bounded checksum hypotheses; prints matches, never modifies an image."""
from pathlib import Path
import zlib
root=Path(__file__).resolve().parents[2]
roms=[bytes.fromhex((root/p).read_text()) for p in ('dump_CS5211.txt','dump_CS5211_patched_8bit_jeida.txt')]
def rev(v,n):return int(f'{v:0{n}b}'[::-1],2)
def table(poly,right):
 t=[]
 for i in range(256):
  c=i if right else i<<24
  for _ in range(8):c=((c>>1)^(poly if c&1 else 0)) if right else (((c<<1)&0xffffffff)^(poly if c&0x80000000 else 0))
  t.append(c)
 return t
def crc(data,t,right,init):
 c=init
 for b in data:c=(c>>8)^t[(c^b)&255] if right else ((c<<8)&0xffffffff)^t[(c>>24)^b]
 return c
for poly in (0x04c11db7,0x1edc6f41,0xa833982b,0x814141ab):
 for right in (False,True):
  t=table(rev(poly,32) if right else poly,right)
  for start in (0x1000,0x1010):
   for end in list(range(0x1e80,0x1e91))+[0x2000]:
    for unit in (1,2,4):
     data=roms[0][start:end];data=b''.join(data[i:i+unit][::-1] for i in range(0,len(data),unit))
     for init in (0,0xffffffff):
      result=crc(data,t,right,init)
      for finalreverse in (False,True):
       v=rev(result,32) if finalreverse else result
       for xor in (0,0xffffffff):
        value=v^xor
        for endian in ('big','little'):
         if value==int.from_bytes(roms[0][0xffa:0xffe],endian):
          print('MATCH',hex(poly),right,hex(start),hex(end),unit,hex(init),finalreverse,hex(xor),endian,flush=True)
# Differential search removes unknown init/final XOR and sweeps payload ends.
a,b=roms;want=int.from_bytes(a[0xffa:0xffe],'big')^int.from_bytes(b[0xffa:0xffe],'big')
for poly in (0x04c11db7,0x1edc6f41,0xa833982b,0x814141ab):
 for right in (False,True):
  t=table(rev(poly,32) if right else poly,right)
  for unit in (1,2,4):
   data=bytes(x^y for x,y in zip(a[0x1000:],b[0x1000:]));data=b''.join(data[i:i+unit][::-1] for i in range(0,len(data),unit))
   c=0
   for i,v in enumerate(data):
    c=(c>>8)^t[(c^v)&255] if right else ((c<<8)&0xffffffff)^t[(c>>24)^v]
    if c in (want,rev(want,32),int.from_bytes(want.to_bytes(4,'big'),'little')):
     print('DELTA MATCH',hex(poly),right,unit,hex(0x1001+i),hex(c),flush=True)
