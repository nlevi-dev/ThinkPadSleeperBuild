← [Back to README](../README.md)

# Screen

The screen situation is probably the most complicated part of the whole build. There are problems on multiple fronts: the backlight technology, the signal protocol, and the physical connector.

## The Panels

Three panels are in scope. Specs are in this folder.

**Samsung [LTN141P4-L03](docs/specs_14inch_Samsung_LTN141P4-L03.pdf)** — 14 inch, 1400x1050, CCFL backlight, LVDS. This is the stock panel and a drop-in fit. No modern eDP replacement has been found for this size.

**Hydis [HV150UX2-100](docs/specs_15inch_Hydis_HV150UX2-100.pdf)** — 15 inch, 1600x1200, LED backlight, LVDS. Has a known replacement kit available ([tpart.net](https://www.tpart.net/product/hv150ux2-100-led-inverter-screen-cable-set-for-t60-t70-t700-led-back-light)) but it's not a drop-in — different pinouts and no inverter needed.

**Innolux [G150XJE-E01](docs/specs_15inch_Innolux_G150XJE-E01.pdf)** — 15 inch, 1024x768, LED backlight, eDP. Not a drop-in either, and the resolution is a significant downgrade.

## CCFL → LED Swap

For the 14 inch, one option is to keep the Samsung panel and swap the CCFL backlight for an LED strip. The motivation would be to avoid the inverter circuit and get a more modern backlight.

In practice it's not worth it. The disassembly is fiddly, there's hidden glue that will cause you to snap the CCFL tube if you don't know about it, and the end result is dimmer than the original with bad color balance.

Full teardown notes and photos from an attempt on the LTN141P4: [backlight.md](backlight.md).

## The LVDS Problem

The bigger issue is that modern GPUs output eDP or HDMI, not LVDS. So a converter is needed regardless of which panel is used.

There are two types of converters on the market:

**Bridge IC** — preferred approach. A single chip that performs DP-to-LVDS protocol conversion. Fewer active components, and some ICs support EDID pass-through — reading the panel's EDID over DDC and forwarding it upstream to the GPU, so no custom EDID or VBIOS fallback is needed. The Samsung panel has a very detailed spec sheet with full EDID and timing info, which helps a lot here.

**Scalar board** — a full board that decodes the input signal and re-encodes it as LVDS. Needs the panel timings flashed to its onboard firmware. Can take HDMI in. More moving parts.

Off-the-shelf converters are mostly built for common 16:9 resolutions and won't work with the 4:3 panels out of the box. Reached out to a couple of vendors, and I got the impression that most of them don't even know what they're selling — they couldn't tell me the core IC used or provide a datasheet. After a lot of digging I found the core ICs worth considering:

<table>
    <thead>
        <tr><th rowspan=2></th><th colspan=5>DP to LVDS Chip Comparison</th></tr>
        <tr><th>Function</th><th><a href="docs/specs_NPX_PTN3460.pdf">PTN3460</a></th><th><a href="docs/specs_Parade_PS8615.pdf">PS8615</a></th><th><a href="docs/specs_Chrontel_CH7511B.pdf">CH7511</a></th><th><a href="docs/specs_CapStone_CS5211.pdf">CS5211</a></th></tr>
    </thead>
    <tbody>
        <tr><td rowspan=10>Almost Same</td><td>DP Lane</td><td>1 or 2</td><td>2</td><td>2</td><td>2</td></tr>
        <tr><td>Link Speed</td><td>2.7G max</td><td>2.7G max</td><td>2.7G max</td><td>2.7G max</td></tr>
        <tr><td>Link Training</td><td>Fastlink, Fulllink</td><td>Fastlink, Nolink, Fulllink</td><td>Fastlink, Fulllink</td><td>Fulllink</td></tr>
        <tr><td>Max Resolution</td><td>1920x1200@60Hz</td><td>1920x1200@60Hz</td><td>1920x1200@60Hz</td><td>1920x1200@60Hz</td></tr>
        <tr><td>Dynamic Refresh Rate</td><td>NA</td><td>Support</td><td>Support</td><td>Support</td></tr>
        <tr><td>Alternate Scrambler Seed Reset</td><td>Support</td><td>Support</td><td>Support</td><td>Support</td></tr>
        <tr><td>LVDS Interface</td><td>2 Port</td><td>2 Port</td><td>2 Port</td><td>2 Port</td></tr>
        <tr><td>LVDS Format</td><td>VESA or JEIDA</td><td>VESA or JEIDA</td><td>VESA or JEIDA</td><td>VESA or JEIDA</td></tr>
        <tr><td>LVDS SSC</td><td>Support</td><td>Support</td><td>Support</td><td>Support</td></tr>
        <tr><td>PWM</td><td>Passthrough and On-Chip PWM</td><td>Passthrough and On-Chip PWM</td><td>Passthrough and On-Chip PWM</td><td>Passthrough and On-Chip PWM</td></tr>
        <tr><td rowspan=12>Different</td><td>Crystal Free</td><td>Yes</td><td>Yes</td><td>No</td><td>Yes</td></tr>
        <tr><td>HDCP</td><td>NA</td><td>Support</td><td>NA</td><td>NA</td></tr>
        <tr><td>Firmware-less</td><td>No - on-chip NVM</td><td>Yes (maybe needs EDID 1kbit E2PROM)</td><td>No - 64kbit E2PROM</td><td>No - 64kbit E2PROM</td></tr>
        <tr><td>Power</td><td>3.3V single or 3.3V + 1.8V</td><td>3.3V + 1.2V or 3.3V + integrated DCDC (needs inductor)</td><td>3.3V + 1.8V</td><td>3.3V (2.5-3.3) 1.8V (1.2-3.3) (can support 3.3V single)</td></tr>
        <tr><td>Package</td><td>56pin 7x7</td><td>56pin 7x7</td><td>68pin 8x8</td><td>68pin 8x8</td></tr>
        <tr><td>AUX to DDC</td><td>Yes</td><td>Yes</td><td>No</td><td>No</td></tr>
        <tr><td>Panel Config by Pin</td><td>Yes</td><td>Yes</td><td>No</td><td>No</td></tr>
        <tr><td>16 EDID Select by Pin</td><td>No (7 EDID slots, NVM-based)</td><td>No</td><td>Yes</td><td>Yes</td></tr>
        <tr><td>Gamma Correction</td><td>NA</td><td>NA</td><td>Support</td><td>Support</td></tr>
        <tr><td>Dithering 6bit Input to 8bit</td><td>NA</td><td>NA</td><td>Yes</td><td>Yes</td></tr>
    </tbody>
</table>

Detailed public documentation is hard to come by for all of them. The standout is the [CS5211](docs/specs_CapStone_CS5211.pdf) — it has the most open documentation, mostly surfaced through Chinese electronics forums. There's also a relatively well-documented third-party board design by [Shenzhen Jingxin Quartz Technology](docs/specs_JX_EDP_LVDS_CS5211.pdf) built around it, with schematics and notes that have circulated widely. More notes and teardown on that design: [lvds.md](lvds.md).

## Connector

See [Connectors](../Connectors/connectors.md#screen-assembly) for the confirmed part.

![Screen schematic](../Schematic/specs_Screen.svg)
