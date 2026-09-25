# CS5211 LVDS profile map

The CS5211's 8051 firmware treats the data at ROM `0x1010–0x110f` as sixteen
16-byte GPIO-selected panel profiles. The profile index is derived from
`XDATA[0x00ca] & 0x0f`. Each record's first twelve bytes are copied during boot
to the following undocumented CS5211 XDATA registers:

| Profile byte | XDATA register | Write operation |
| ---: | ---: | --- |
| `+0` | `0x009f` | direct |
| `+1`, `+2` | `0x01dc`, `0x01de` | direct |
| `+3` | `0x01e1` | `value & 0xf7` |
| `+4` | `0x01e2` | `value | 0x08` |
| `+5`, `+6`, `+7` | `0x01e3`, `0x01e4`, `0x01e7` | direct |
| `+8`, `+9`, `+10` | `0x01ed`, `0x01f2`, `0x01f3` | direct |
| `+11` | `0x01f4` | low nibble from profile, high nibble from firmware `0x0122` |

All profiles in `dump_CS5211.txt` are identical:

```text
01 00 00 01 08 00 00 08 03 03 44 04 aa aa aa aa
```

The public CS5211 datasheet says these boot-ROM parameters select OpenLDI/SPWG
configuration, but does not publish the XDATA register map. Static analysis
therefore establishes the source bytes and target registers, not vendor bit
names.

## LVDS mapping evidence

The [LTN141P4-L03 specification](../specs_14inch_Samsung_LTN141P4-L03.pdf)
shows the three active LVDS lanes as:

```text
lane 0: G0 R5 R4 R3 R2 R1 R0
lane 1: B1 B0 G5 G4 G3 G2 G1
lane 2: DE VS HS B5 B4 B3 B2
```

That panel accepts dual-pixel 18-bit LVDS. VESA/SPWG 24-bit maps source low
bits onto those lanes; JEIDA 24-bit maps source high bits there. Thus JEIDA
24-bit is compatible with the panel's missing fourth data lane, while VESA/SPWG
24-bit produces correct black/full-scale colours but corrupt intermediate
values. See TI's [mapping note](https://www.ti.com/lit/an/snla014a/snla014a.pdf).

The likely required change is therefore a mapping-mode bit in the profile block
above, with dual-port operation left unchanged. Profile bytes `+8…+11` are the
first candidates for a controlled one-bit test; their semantics remain unknown.
