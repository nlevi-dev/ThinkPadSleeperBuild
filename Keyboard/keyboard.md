# Keyboard

← [Back to README](../README.md)

The T60 keyboard is a plain matrix interface — no active components on the keyboard itself, just a grid of switches. It also carries the PS2 TrackPoint (joystick) lanes on the same cable.

The connector is confirmed. See [Connectors](../Connectors/connectors.md#keyboard) for the full spec.

## Bridging it

There are a lot of projects out there doing exactly this — making a USB adapter for ThinkPad keyboards. The problem is most of them are either semi-open source or badly documented — code missing, gerber files missing, or both.

The best leads found so far:

- https://www.scribd.com/document/997574050/Pi-Pico-T61-Keyboard-Controller
- https://www.instructables.com/Make-a-ThinkPad-keyboard-USB-adapter-with-Arduino/
- https://github.com/rampadc/arduino-thinkpadkb-usb

The plan is to make a fully open source version. Prototyping started with a breakout board and an Arduino Mega to reverse engineer the matrix.

The gerber for the breakout board is in this folder: `Gerber_T60_Keyboard-Breakout.zip`

The scanner sketch is in `scanner/scanner.ino`. It drives each DRIVE line LOW in turn and reads the SENSE lines, printing the key name and coordinates over serial.

## Wiring (Arduino Mega)

| Signal | Arduino Mega Pin |
|---|---|
| DRIVE\<0\> | 42 |
| DRIVE\<1\> | 39 |
| DRIVE\<2\> | 35 |
| DRIVE\<3\> | 31 |
| DRIVE\<4\> | 23 |
| DRIVE\<5\> | 25 |
| DRIVE\<6\> | 29 |
| DRIVE\<7\> | 33 |
| DRIVE\<8\> | 27 |
| DRIVE\<9\> | 41 |
| DRIVE\<10\> | 37 |
| DRIVE\<11\> | 43 |
| DRIVE\<12\> | 45 |
| DRIVE\<13\> | 40 |
| DRIVE\<14\> | 44 |
| DRIVE\<15\> | 46 |
| SENSE\<0\> | 26 |
| SENSE\<1\> | 34 |
| SENSE\<2\> | 30 |
| SENSE\<3\> | 28 |
| SENSE\<4\> | 32 |
| SENSE\<5\> | 24 |
| SENSE\<6\> | 36 |
| SENSE\<7\> | 38 |
| HOTKEY | 22 |
| HOTKEY_RTN | 47 |

Full connector pinout in [connection.csv](connection.csv).

## Power Button

JAE pin 19 (PWR SW) and pin 34 (PWR GND) — pressing the button closes these two pins together through a 200 Ω resistor. Wire them directly to whatever power button input the candidate board expects.

## Matrix

Verified with a Hungarian layout keyboard. ISO-102 is the extra key between Left Shift and Z (`í`/`<` on HU/NL). ISO-103 is the extra key right of the apostrophe (`ű`/`ú` on HU/NL).

| | S\<0\> | S\<1\> | S\<2\> | S\<3\> | S\<4\> | S\<5\> | S\<6\> | S\<7\> |
|---|---|---|---|---|---|---|---|---|
| **D\<0\>** | Back-Tick | 1 | Q | Tab | A | Esc | Z | |
| **D\<1\>** | F1 | 2 | W | Caps-Lock | S | ISO-102 | X | |
| **D\<2\>** | F2 | 3 | E | F3 | D | F4 | C | |
| **D\<3\>** | 5 | 4 | R | T | F | G | V | B |
| **D\<4\>** | 6 | 7 | U | Y | J | H | M | N |
| **D\<5\>** | Equal | 8 | I | Right-Brace | K | F6 | Comma | |
| **D\<6\>** | F8 | 9 | O | F7 | L | | Period | |
| **D\<7\>** | Minus | 0 | P | Left-Brace | Semi-colon | Quote | ISO-103 | Forward-Slash |
| **D\<8\>** | F9 | F10 | | Back-Space | Back-Slash | F5 | Enter | Space |
| **D\<9\>** | Insert | F12 | | | | | | Arrow-Right |
| **D\<10\>** | Delete | F11 | Volume-Up | Volume-Down | Mute | Think-Vantage | | Arrow-Down |
| **D\<11\>** | Page-Up | Page-Down | GUI | | Menu | | Page-Left | Page-Right |
| **D\<12\>** | Home | End | | | | Arrow-Up | Pause | Arrow-Left |
| **D\<13\>** | | Print-Screen | Scroll-Lock | | | Alt-L | | Alt-R |
| **D\<14\>** | | | | Shift-L | | | Shift-R | |
| **D\<15\>** | Ctrl-L | | | | | | Ctrl-R | |
