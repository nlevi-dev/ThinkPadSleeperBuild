#!/usr/bin/env python3
"""Generate exact RGB8 probes for the hypothesized LVDS low-six-bit mismatch.

Requires Pillow. The PNGs contain no ICC profile or gamma chunk. Actual display
software and the GPU may still transform their values. Show at 1:1, native
1400x1050 resolution, with colour adjustments disabled/recorded.
"""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1400, 1050), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=18)
    text = lambda x, y, s: draw.text((x, y), s, fill=(255, 255, 255), font=font)
    text(24, 16, "CS5211 probe: show at native 1400 x 1050, 1:1 pixels; disable/record colour transforms")
    text(24, 44, "Rows: grey, red, green, blue. Each upper band: 0..255. Lower band: the same ramp >> 2.")
    text(24, 70, "Healthy mapping: upper smooth, lower dark. Low-six-bit mismatch: upper repeats, lower smooth/full-range.")
    x0, pitch = 188, 4
    channels = [(1, 1, 1), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    regions = []
    for row, (name, weights) in enumerate(zip(("Grey", "Red", "Green", "Blue"), channels)):
        y0 = 110 + row * 125
        text(24, y0+12, name + " normal")
        text(24, y0+62, name + " >> 2")
        for v in range(256):
            for y, value in ((y0, v), (y0+50, v >> 2)):
                color = tuple(value*w for w in weights)
                draw.rectangle((x0+pitch*v, y, x0+pitch*v+pitch-1, y+39), fill=color)
        regions.append({"channel":name,"x":x0,"sample_width":pitch,"normal_y":y0,"compensated_y":y0+50,"band_height":40})
        for v in (0, 63, 64, 127, 128, 191, 192, 255):
            draw.line((x0+pitch*v,y0+91,x0+pitch*v,y0+95),fill=(255,255,255))
        for v, label in ((0,"0"),(63.5,"63/64"),(127.5,"127/128"),(191.5,"191/192"),(255,"255")):
            width = draw.textlength(label, font=font)
            text(round(x0+pitch*v-width/2), y0+98, label)
    text(24, 625, "Individual source bit weights, left to right: 1, 2, 4, 8, 16, 32, 64, 128")
    for row, weights in enumerate(channels):
        for bit in range(8):
            v = 1 << bit
            x, y = 188+128*bit, 660+row*55
            draw.rectangle((x,y,x+119,y+44),fill=tuple(v*w for w in weights))
    text(24, 894, "Odd/even check: alternating red/green columns, then alternating phases (native resolution required)")
    for x in range(1400):
        draw.line((x,930,x,964),fill=(255,0,0) if x%2==0 else (0,255,0))
        draw.line((x,975,x,1009),fill=(0,255,0) if x%2==0 else (255,0,0))
    text(24, 1023, "This is a diagnostic prediction, not a measured result or confirmed firmware fix.")
    image.save(args.out / "normal-vs-compensated.png")
    # A full-frame compensation lets text and patterns participate in the same test.
    compensated = image.point([v >> 2 for v in range(256)] * 3)
    compensated.save(args.out / "whole-image-compensated.png")
    # Exact digital identity behind the proposed workaround.
    for v in range(256):
        assert ((v >> 2) & 63) == (v >> 2)
    # Check encoded files as well, including known boundary values.
    decoded = Image.open(args.out / "normal-vs-compensated.png")
    for r in regions:
        weights = channels[["Grey", "Red", "Green", "Blue"].index(r["channel"])]
        for v in range(256):
            assert decoded.getpixel((x0+pitch*v,r["normal_y"])) == tuple(v*w for w in weights)
            assert decoded.getpixel((x0+pitch*v,r["compensated_y"])) == tuple((v>>2)*w for w in weights)
    (args.out / "pattern-regions.json").write_text(json.dumps(regions, indent=2)+"\n")
    print(f"Wrote two 1400x1050 RGB8 diagnostic PNGs to {args.out}; pixel checks passed")


if __name__ == "__main__":
    main()
