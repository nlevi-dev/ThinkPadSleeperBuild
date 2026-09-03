# ThinkPad T60 Sleeper Build

The goal is to gut a ThinkPad T60 and replace the internals with a modern gaming laptop board, keeping the original T60 shell intact. Targeted specifically at the **4:3 models**.

## V1 vs V2

There are two versions of this build with very different scopes.

**V1 — Partial sleeper** is the practical starting point. The original battery shell gets glued into the outer chassis and becomes part of it, so the candidate board drops in as a near-direct replacement for whatever motherboard was in there. The candidate keeps its own battery and cooling solution. Some cooling port holes may be drilled or adjusted in the chassis. Only a limited subset of the original T60 IO is preserved, and the candidate's onboard ports can stay accessible by pushing the board up against the shell. The only interfaces that need bridging are: keyboard, touchpad, speakers, and screen.

**V2 — Full sleeper** is the real deal. From the outside it would be indistinguishable from a stock T60 — original cooling vents, original battery, original IO ports. This requires custom power delivery, custom cooling, and IO extensions. It's a much bigger undertaking and has several hard unsolved problems. See [Power](Power/power.md) and [Cooling](Cooling/cooling.md) for the details.

## Size Constraints

The T60 chassis sets a hard limit on what can fit inside:

- **14 inch model:** 311 x 255 mm
- **15 inch model:** 329 x 268 mm

See [Candidates](Candidates/candidates.md) for the full list of boards that fit.

## Tooling

`arduino.sh` in the root compiles, uploads, and opens a serial monitor for a given sketch. Usage:

```
./arduino.sh Keyboard/test_keyboard
```

Requires [arduino-cli](https://arduino.github.io/arduino-cli/). Targets `/dev/ttyUSB0` at 9600 baud.

## Navigation

| Section | Description |
|---|---|
| [Candidates](Candidates/candidates.md) | All boards that physically fit the 14" and 15" chassis, with specs and dimensions |
| [Connectors](Connectors/connectors.md) | Confirmed T60 internal connectors identified from the original schematic |
| [Keyboard](Keyboard/keyboard.md) | Full matrix reverse-engineered, TrackPoint over PS2, breakout board gerbers, Arduino test sketches |
| [Touchpad](Touchpad/touchpad.md) | PS2 interface, connector identified |
| [Screen](Screen/screen.md) | Panel options, CCFL→LED swap, eDP→LVDS converter problem, 4:3 resolution dead ends |
| [Sound](Sound/sound.md) | Speaker connector identified, audio bridge TBD |
| [Power](Power/power.md) | V2 only — USB-C PD chain, battery problem |
| [Cooling](Cooling/cooling.md) | V2 only — custom cooling approach |
| [Cosmetic](Cosmetic/cosmetic.md) | Rubberized coating cleanup |
