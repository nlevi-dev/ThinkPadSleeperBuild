/* Instrumentation adapter for jarikomppa/emu8051 (MIT), not a silicon model.
 * Build with scripts/cs5211_blackbox.py --build. All CPU instructions and
 * timer handling are delegated to the independent emulator core.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "emu8051.h"

#define EVENTS 100000
typedef struct { uint32_t tick, pc, address, value, kind; } Event;
typedef struct {
    struct em8051 cpu; /* must be first for callbacks */
    uint8_t code[65536], xdata[65536], upper[128];
    uint8_t seeded[65536], written[65536];
    uint32_t coverage[65536], code_reads[65536], xreads[65536], unwritten_reads[65536];
    uint8_t branch_outcomes[65536]; /* bit 0 fallthrough, bit 1 taken */
    uint32_t log_mask;
    uint32_t steps, ticks, count, dropped, exceptions[16], max_sp;
    em8051operation original[256];
    Event events[EVENTS];
} State;

static void event(State *s, unsigned kind, unsigned addr, unsigned value) {
    if (!(s->log_mask & (1u << kind))) return;
    if (s->count == EVENTS) { s->dropped++; return; }
    s->events[s->count++] = (Event){s->ticks, s->cpu.mPC, addr, value, kind};
}
static uint8_t xread(struct em8051 *cpu, uint16_t addr) {
    State *s = (State*)cpu;
    s->xreads[addr]++;
    if (!s->seeded[addr] && !s->written[addr]) s->unwritten_reads[addr]++;
    event(s, 0, addr, s->xdata[addr]);
    return s->xdata[addr];
}
static void xwrite(struct em8051 *cpu, uint16_t addr, uint8_t value) {
    State *s = (State*)cpu;
    s->xdata[addr] = value; s->written[addr] = 1;
    event(s, 1, addr, value);
}
static void exception(struct em8051 *cpu, int code) {
    State *s = (State*)cpu;
    if (code >= 0 && code < 16) s->exceptions[code]++;
}
static uint8_t instrument(struct em8051 *cpu) {
    State *s = (State*)cpu;
    uint16_t pc = cpu->mPC;
    uint8_t op = s->code[pc];
    s->coverage[pc]++; s->steps++;
    if (op == 0x93 || op == 0x83) {
        uint16_t base = op == 0x93 ? ((cpu->mSFR[REG_DPH]<<8)|cpu->mSFR[REG_DPL]) : pc+1;
        uint16_t addr = base + cpu->mSFR[REG_ACC];
        s->code_reads[addr]++;
        event(s, 2, addr, s->code[addr]);
    }
    if (cpu->mSFR[REG_SP] > s->max_sp) s->max_sp = cpu->mSFR[REG_SP];
    uint8_t delay = s->original[op](cpu);
    unsigned length = 0;
    if(op==0x10 || op==0x20 || op==0x30 || (op>=0xb4 && op<=0xbf) || op==0xd5) length=3;
    if(op==0x40 || op==0x50 || op==0x60 || op==0x70 || (op>=0xd8 && op<=0xdf)) length=2;
    if(length) s->branch_outcomes[pc] |= cpu->mPC==(uint16_t)(pc+length) ? 1 : 2;
    return delay;
}
void *cs_new(const uint8_t *rom, unsigned length) {
    if (length != 8192) return NULL;
    State *s = calloc(1, sizeof(State));
    if (!s) return NULL;
    s->log_mask = 7;
    s->cpu.mCodeMem = s->code; s->cpu.mCodeMemMaxIdx = 65535;
    s->cpu.mExtData = s->xdata; s->cpu.mExtDataMaxIdx = 65535;
    s->cpu.mUpperData = s->upper;
    reset(&s->cpu, 1);
    memcpy(s->code, rom+0x1000, length-0x1000);
    s->cpu.xread = xread; s->cpu.xwrite = xwrite; s->cpu.except = exception;
    for (unsigned i=0;i<256;i++) { s->original[i] = s->cpu.op[i]; s->cpu.op[i] = instrument; }
    return s;
}
void cs_free(void *p) { free(p); }
void cs_log_mask(void *p, unsigned mask) { ((State*)p)->log_mask=mask; }
void cs_clear_events(void *p) { State *s=p; s->count=0; s->dropped=0; }
void cs_seed(void *p, unsigned address, unsigned value) {
    State *s=p; s->xdata[address&65535] = value; s->seeded[address&65535]=1;
}
void cs_pc(void *p, unsigned pc) { State *s=p; s->cpu.mPC=pc; s->cpu.mTickDelay=0; }
void cs_direct(void *p, unsigned address, unsigned value) {
    State *s=p; address &= 255;
    if(address<128) s->cpu.mLowerData[address]=value;
    else s->cpu.mSFR[address-128]=value;
}
/* Returns 1 on target PC, 2 on exception, 0 on tick-budget exhaustion. */
int cs_run(void *p, unsigned budget, unsigned stop) {
    State *s=p;
    /* Resume must execute the breakpoint instruction before stopping again.
     * Draining a pending tick or entering/returning from an ISR is insufficient. */
    int resume = s->cpu.mPC == stop;
    unsigned initial_hits = s->coverage[stop & 65535];
    for(unsigned i=0;i<budget;i++) {
        if(s->cpu.mPC==stop && (!resume || s->coverage[stop & 65535]>initial_hits)) return 1;
        tick(&s->cpu); s->ticks++;
        for(unsigned j=0;j<16;j++) if(s->exceptions[j]) return 2;
    }
    return 0;
}
unsigned cs_get(void *p, unsigned space, unsigned address) {
    State *s=p; address &= 65535;
    switch(space) {
        case 0: return s->code[address];
        case 1: return s->xdata[address];
        case 2: return address<128?s->cpu.mLowerData[address]:s->upper[address&127];
        case 3: return s->cpu.mSFR[address&127];
        case 4: return s->coverage[address];
        case 5: return s->code_reads[address];
        case 6: return s->xreads[address];
        case 7: return s->unwritten_reads[address];
        case 8: return s->written[address];
        case 9: return s->exceptions[address&15];
        case 11: return s->branch_outcomes[address];
        case 10: switch(address) {
            case 0:return s->cpu.mPC; case 1:return s->steps; case 2:return s->ticks;
            case 3:return s->count; case 4:return s->dropped; case 5:return s->max_sp;
        }
    }
    return 0;
}
void cs_event(void *p, unsigned n, uint32_t *out) {
    State *s=p;
    if(n<s->count) memcpy(out, &s->events[n], sizeof(Event));
}
