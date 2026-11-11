"""A real 64x64 4bpp GBA OBJ emblem stored ONLY in the XGBA external sidecar.

This generates raw GBA tiled graphics (2048 bytes), not a mock screenshot.
The compiled FireRed game supplies only palette/OAM display instructions.
mGBA must fetch these bytes from beyond the 32 MiB ROM window via R7 MMIO.
"""
from __future__ import annotations

WIDTH = HEIGHT = 64
SIZE = WIDTH * HEIGHT // 2
FONT = {
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
}


def generate_emblem() -> bytes:
    px = [[0 for _ in range(WIDTH)] for _ in range(HEIGHT)]

    # A crisp pixel-art crystal seal. Zero is transparent; all design pixels
    # are palette indices 1..10 assigned by the real running FireRed code.
    for y in range(3, 61):
        for x in range(3, 61):
            dx, dy = abs(x - 31.5), abs(y - 31.5)
            diamond = dx + dy
            if diamond <= 33:
                if diamond >= 30:
                    color = 6  # gold outer highlight
                elif diamond >= 27:
                    color = 3  # crystal-blue glowing edge
                elif diamond >= 24:
                    color = 2  # aqua rim
                else:
                    color = 8 if y >= x - 2 else 9  # luminous facet
                if 15 <= y < 49 and 8 <= x < 56 and diamond < 21:
                    color = 1  # navy label center
                px[y][x] = color

    # Diagonal facets and twinkle details.
    for k in range(7, 24):
        x, y = 32 - k, 32 - k
        if px[y][x] and (x + y) % 3 == 0:
            px[y][x] = 4
    for cx, cy in ((8, 16), (54, 17), (9, 49), (55, 49)):
        for dx, dy in ((0,-3), (0,-2), (0,-1),(0,0),(0,1),(0,2),(0,3),
                       (-3,0),(-2,0),(-1,0),(1,0),(2,0),(3,0)):
            x, y = cx+dx, cy+dy
            if 0 <= x < 64 and 0 <= y < 64:
                px[y][x] = 4 if abs(dx)+abs(dy)<2 else 3

    # Two-pixel font creates legible XGBA wording within 64x64 sprite art.
    phrase = "XGBA"
    origin_x, origin_y = 8, 25
    for index, letter in enumerate(phrase):
        for row, bits in enumerate(FONT[letter]):
            for col, on in enumerate(bits):
                if on == "1":
                    x = origin_x + index * 12 + col * 2
                    y = origin_y + row * 2
                    for yy in (y, y + 1):
                        for xx in (x, x + 1):
                            if 0 <= xx < 64 and 0 <= yy < 64:
                                px[yy][xx] = 6 if yy < 30 else 4

    # GBA OBJ 4bpp: 8x8 tiles, two 4-bit palette indexes per byte, 1D
    # tile layout, 8 tiles across x 8 tiles down for one 64x64 object.
    result = bytearray()
    for tile_y in range(0, HEIGHT, 8):
        for tile_x in range(0, WIDTH, 8):
            for yy in range(8):
                for xx in range(0, 8, 2):
                    a = px[tile_y + yy][tile_x + xx]
                    b = px[tile_y + yy][tile_x + xx + 1]
                    result.append(a | b << 4)
    assert len(result) == SIZE == 2048
    assert set(result) != {0}
    return bytes(result)


if __name__ == "__main__":
    from pathlib import Path
    p = Path("xgba-r8-emblem.4bpp")
    p.write_bytes(generate_emblem())
    print(f"Wrote {p}: {SIZE} bytes of native GBA 64x64 4bpp OBJ tiles")
