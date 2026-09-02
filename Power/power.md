# Power Delivery

← [Back to README](../README.md)

*This is a V2 full sleeper concern. V1 keeps the candidate's own battery and charging as-is.*

Getting the candidate board to run off the T60's original battery and charger is one of the two biggest unsolved problems in the full sleeper build. Here's why it's hard.

## The Battery Problem

Modern laptop batteries use flat cells with proprietary BMS firmware that almost certainly requires a handshake with the host board. Swapping those flat cells for cylindrical ones that fit the T60 battery housing is a non-starter — the voltage profiles are completely different.

Theoretically you could swap the flat cells for other flat cells that happen to fit the T60 housing dimensions, but modern BMS boards have tamper protection: if they lose power even briefly, they blow an internal fuse and refuse to work. So any cell swap has to be done "hot" — the BMS can never lose power during the swap. That's a green-blue deployment for a battery, which is not fun.

The only realistic path is to **take the candidate's battery out of the equation entirely** and run the board off permanent DC input.

## USB-C Only Charging

All the candidates charge over USB-C — no dedicated barrel jack. That means tapping into the power delivery system, which is well above the complexity threshold for this build. So USB-C PD it is.

Losing a USB-C port permanently to charging is painful given how few ports some of these boards have. There are USB-C splitter accessories sold mainly for AR glasses that can separate the host PD from the data lines — one of those would be needed to split charging from the rest of the USB-C functionality.

## The Full Chain

To make this work, the component chain would look something like:

1. USB-C PD splitter (separates power from data)
2. PD/QC USB-C buck-boost converter (steps voltage to what the board needs)
3. CC/CV supply for charging the T60 battery
4. Ideal diode to switch between AC adapter and battery

That's a lot of components and a lot of points of failure. There's also a performance concern: gaming laptops at peak load typically pull from both the AC adapter and the battery simultaneously. This setup would cap the available power to whatever the USB-C PD supply can deliver, which could cause throttling under sustained load.

## Status

Unsolved. This whole chain needs to be designed, sourced, and tested before a full sleeper build is viable.
