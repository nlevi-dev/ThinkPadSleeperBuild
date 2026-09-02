# Keyboard

← [Back to README](../README.md)

The T60 keyboard is a plain matrix interface — no active components on the keyboard itself, just a grid of switches. It also carries the PS2 TrackPoint (joystick) lanes on the same cable.

The connector is confirmed. See [Connectors](../Connectors/connectors.md#keyboard) for the full spec.

## Bridging it

There are a lot of projects out there doing exactly this — making a USB adapter for ThinkPad keyboards. The problem is most of them are either semi-open source or badly documented — code missing, gerber files missing, or both.

The best leads found so far:

- https://www.instructables.com/Make-a-ThinkPad-keyboard-USB-adapter-with-Arduino/
- https://github.com/rampadc/arduino-thinkpadkb-usb

The plan is to make a fully open source version. Prototyping started with a breakout board and an Arduino Mega to reverse engineer the matrix. Results are still pending.

The gerber for the breakout board is in this folder: `Gerber_T60_Keyboard-Breakout.zip`
