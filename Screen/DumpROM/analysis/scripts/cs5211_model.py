#!/usr/bin/env python3
"""Readable CS5211 application reconstruction, without a silicon model.

Models ordered XDATA access and firmware state transitions. Busy waits retain
their argument but are not wall-clock calibrated. Timer ISR is a separate
event; cycle scheduling and generic unused compiler-library cases are excluded.
"""
from fractions import Fraction


def float24(value, truncate=False):
    """Positive binary32 precision; integer conversions chop, arithmetic ties up."""
    value=Fraction(value)
    if not value:return value
    exponent=value.numerator.bit_length()-value.denominator.bit_length()
    if value<Fraction(2)**exponent:exponent-=1
    quantum=Fraction(2)**(exponent-23)
    scaled=value/quantum
    significand,remainder=divmod(scaled.numerator,scaled.denominator)
    if not truncate and 2*remainder>=scaled.denominator:significand+=1
    return significand*quantum


def clock_numbers(m,n,rate,port):
    p=(((27*rate*m)&0xffffffff)//n) if n else 0xffffffff
    if n:
        a=float24(rate*m,truncate=True)
        b=float24(a*458752)
        c=float24(b/float24(n,truncate=True))
        q=min(int(c),0xffffffff)&0xffffff
    else:q=0xffffff
    band=0 if p>=100 else 1 if p>=50 else 2 if p>=25 else 3
    return q,(0,2,4,8)[band],min(3,band+bool(port))<<4


class MemoryIO:
    def __init__(self,seed=None):
        self.memory=dict(seed or {});self.trace=[]
    def read(self,addr):
        value=self.memory.get(addr,0);self.trace.append((0,addr,value));return value
    def write(self,addr,value):
        value&=255;self.memory[addr]=value;self.trace.append((1,addr,value))


class ReplayIO:
    """Feed observed external reads; independently predict every ordered write."""
    def __init__(self,trace):self.trace=trace;self.index=0
    def read(self,addr):
        kind,expected,value=self.trace[self.index]
        assert (kind,expected)==(0,addr),(self.index,(kind,expected),(0,addr))
        self.index+=1;return value
    def write(self,addr,value):
        actual=(1,addr,value&255)
        assert self.trace[self.index]==actual,(self.index,self.trace[self.index],actual)
        self.index+=1


class Firmware:
    def __init__(self,rom,io):
        self.rom=rom;self.io=io;self.ram=bytearray(256);self.delays=[]
        self.state='initialize';self.profile_index=0;self.lanes=0;self.wait_count=0
        self.timer=False;self.interrupts=False;self.timer_high=0;self.timer_low=0
        # The actual ROM uses only short IRAM records in the startup stream.
        p=0x1e1f
        while rom[p]:
            n=rom[p];assert not n&0xc0 and n<32
            addr=rom[p+1];self.ram[addr:addr+n]=rom[p+2:p+2+n];p+=n+2

    def g(self,index):return self.rom[0x1110+index]
    def profile(self):return self.rom[0x1010+16*self.profile_index:0x1020+16*self.profile_index]
    def rd(self,addr):return self.io.read(addr)
    def wr(self,addr,value):self.io.write(addr,value)
    def delay(self,units):self.delays.append(units&65535)
    def writes(self,pairs):
        for addr,value in pairs:self.wr(addr,value)

    def initialize(self):
        g=self.g
        if g(14)&1:self.writes(((0x1bb,0x14),(0xe3,0x10)))
        else:
            self.writes(((0x1bb,0x94),(0xe3,0x50)))
            if g(17)!=0xaa:self.writes(zip((0xe4,0xe5,0xe6),(g(15),g(16),g(17))))
        self.writes(((0x1ec,0x1f),(0x1f1,0x1f),(0x1f5,0xff),(9,0),(8,0),
                     (0x7c8,0xff),(0x7c7,0x3f),(0x7c6,5),(0x7c5,0xff),
                     (0x622,1),(0xe0,0x37),(0x603,0x82),(0x1d7,0),
                     (0x583,0x1b),(0xc0,0x35)))
        self.profile_index=self.rd(0xca)&15
        self.wr(0x7f0,0x31);self.wr(0x1f,self.rd(0x1f)&0xfb)
        self.wr(0x1bc,0x30);self.wr(0xaa,self.rd(0xaa)|0x80)
        self.writes(((0xa3,1),(0xa4,0xbf),(0x1a5,0x7f),(0x1a0,0x10),
                     (0x1a1,0xff),(0x1a3,2),(0x1a4,0),(0x1da,0x58),(0x17,0)))
        self.wr(0x602,g(0));self.wr(0x603,(self.rd(0x603)&0xe0)|g(1))
        self.writes(zip((0x1d1,0x1f7,0x1d0,0x1d3,0x1f8,0x1d4,0x1f9,0x1d6),
                        (g(i) for i in range(3,11))))
        self.wr(0x26,0)
        if g(11)>10:self.ram[0x13]=10;self.ram[0x10]=10;self.ram[0xf]=0
        else:self.ram[0x13]=g(11);self.ram[0x10]=g(13);self.ram[0xf]=g(12)
        mode=g(2)&3;level=self.ram[0x13]
        if mode==2:self.wr(0xb3,0x2f)
        else:
            if level==0:self.wr(0xb3,0x20)
            elif level==10:self.wr(0xb3,0x2c)
            else:self.timer=True
            if mode==1:self.timer=True
        self.timer_high=self.ram[0xb];self.timer_low=self.ram[0xc]
        self.state='train'

    def recover(self):
        if self.rd(0x1b4)==0x5c:return False
        self.writes(((5,0xfd),(0x1f,0x19),(0xba,0xfe),(0xbb,0xff),(0xb1,0x27),
                     (0x1b1,0xa2),(0x1b5,0xb9),(0x1b3,0x88),(0x1b2,0xa2),
                     (0x9f,1),(0xa7,0x23),(0x8a,0xe9),(0xa,1),(0x1b4,0x5c),
                     (0xdc,0xff),(0xdd,0xff),(0xb8,0)))
        self.wr(0xc4,self.rd(0xc4)+1);return True

    def lane_good(self):return self.rd(0x611)==(7 if self.lanes==1 else 0x77)

    def clock(self):
        m=0;n=0
        for a in range(0x549,0x54c):m=(m<<8)|self.rd(a)
        for a in range(0x54c,0x54f):n=(n<<8)|self.rd(a)
        q,e7,e1=clock_numbers(m,n,self.rd(0x60a),self.profile()[0])
        self.wr(0xe7,e7);self.wr(0xe1,(self.rd(0xe1)&0x8f)|e1)
        self.writes(( (0x564+i,(q>>(16-8*i))&255) for i in range(3)))
        self.wr(0x554,self.rd(0x554)|0xc0)
        old=self.rd(6);self.wr(6,old|8);self.wr(6,old&0xf7)
        self.delay(2);self.wr(0xd0,0xff);self.delay(3)

    def apply_profile(self):
        p=self.profile();g=self.g
        values=[*p[:12]];values[3]&=0xf7;values[4]|=8;values[11]|=(g(18)&15)<<4
        self.writes(zip((0x9f,0x1dc,0x1de,0x1e1,0x1e2,0x1e3,0x1e4,0x1e7,0x1ed,0x1f2,0x1f3,0x1f4),values))
        self.wr(0x22,15);self.wr(0xe1,self.rd(0xe1)|0x80)
        if not self.rd(0x1d7)&1:
            self.wr(0x1d8,0xb4);self.delay(2*(g(3)+(g(4)<<8)+g(5)));self.wr(0x1d8,0xbc)
        self.interrupts=self.timer;self.state='steady'

    def timeout_poll(self):
        self.delay(10);self.wait_count+=1
        if self.wait_count>200:
            self.writes(((6,0x20),(6,0)));self.state='train'

    def brightness_buttons(self):
        buttons=self.rd(0xb0)
        if self.g(2)&0x20:buttons=((buttons&0x40)>>1)|((buttons&0x20)<<1)
        if not buttons&0x40:
            if self.ram[0x13]<self.ram[0x10]:self.ram[0x13]+=1
            self.delay(150);self.delay(150)
        if not buttons&0x20:
            if self.ram[0x13]>self.ram[0xf]:self.ram[0x13]-=1
            self.delay(150);self.delay(150)
        self.wr(0xc8,self.ram[0x13])

    def power_button(self):
        first=self.rd(0xb1)&0x20;self.delay(100)
        both=first|(self.rd(0xb1)&0x20)
        if both==0 and self.ram[0x23]==0 and self.ram[0x24]==0x20:
            off=not(self.ram[0x11]|self.ram[0x12])
            self.ram[0x11]=0;self.ram[0x12]=int(off)
            self.wr(0x1d8,0x80 if off else 0xbc)
        self.ram[0x23]=0;self.ram[0x24]=both;self.delay(200)

    def shutdown(self):
        g=self.g
        if g(2)&0x10:self.ram[0x11]=self.ram[0x12]=0
        if not self.rd(0x1d7)&1:
            self.wr(0x1d8,0xb4);self.delay(2*(g(6)+(g(7)<<8)+g(8)));self.wr(0x1d8,0x94)
        self.wr(0xe1,self.rd(0xe1)&0x7f);self.interrupts=False
        self.delay(2*((g(9)<<8)+g(10)));self.state='train'

    def timer_isr(self):
        level=self.ram[0x13]
        if level==10:self.wr(0xb3,0x2c);return
        if self.ram[0x15]==0:
            self.ram[0x15]=1;self.timer_high=self.ram[(0x16+level)&255];self.timer_low=0
            if level==0:return
            self.wr(0xb3,0x2c)
        else:
            self.ram[0x15]=0;self.timer_high=self.ram[(0x20-level)&255];self.timer_low=0
            self.wr(0xb3,0x20)
        self.ram[0xa]=(self.ram[0xa]+1)&255
        if self.ram[0xa]==0:self.ram[9]=(self.ram[9]+1)&255

    def step(self):
        if self.state=='initialize':self.initialize()
        elif self.state=='train':self.wr(0x22,0);self.state='train_poll'
        elif self.state=='train_poll':
            self.lanes=self.rd(0x60b)&31
            if self.lane_good():
                self.rd(0x613) # OR 1 makes the following branch unconditional.
                self.wr(0x22,14);self.wait_count=0;self.state='wait_video'
            elif self.recover():self.state='train'
            else:self.delay(10)
        elif self.state=='wait_video':
            if self.rd(0xc)&0x20:
                self.wr(0x22,13);self.clock();self.wait_count=0;self.state='wait_clock'
            elif not self.lane_good() or self.recover():self.state='train'
            else:self.timeout_poll()
        elif self.state=='wait_clock':
            if self.rd(0xc)&1:self.apply_profile()
            elif self.recover():self.state='train'
            else:self.timeout_poll()
        elif self.state=='steady':
            ready=self.rd(0xc);self.rd(0x611)
            if self.recover():self.state='train';return
            self.delay(10)
            if self.g(2)&3==1:self.brightness_buttons()
            if self.g(2)&0x10:self.power_button()
            if not ready&0x20 or not self.lane_good():self.shutdown()
        else:raise ValueError(self.state)
