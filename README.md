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

## Navigation

| Section | What's in there |
|---|---|
| [Candidates](Candidates/candidates.md) | Candidate laptops that fit the chassis dimensions |
| [Connectors](Connectors/connectors.md) | T60 internal connector specs and replacement leads |
| [Keyboard](Keyboard/keyboard.md) | Matrix interface, PS2 joystick, breakout board |
| [Touchpad](Touchpad/touchpad.md) | PS2 interface, connector status |
| [Screen](Screen/screen.md) | Panel options, CCFL→LED swap, LVDS problem |
| [Sound](Sound/sound.md) | Current status |
| [Power](Power/power.md) | V2 power delivery challenges |
| [Cooling](Cooling/cooling.md) | V2 cooling challenges |
| [Cosmetic](Cosmetic/cosmetic.md) | Rubberized coating cleanup |
