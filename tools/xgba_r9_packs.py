"""Two real, native 64x64 4bpp GBA OBJ tile packs for XGBA R9.

The ROM does not contain these arrays. Same ID/size/offset, different SHA-256
and art. Both are stored in external sidecars after the ROM's 32 MiB window.
"""
from __future__ import annotations
import hashlib
import xgba_r8_emblem


def make_pack(style: str) -> bytes:
    cool = xgba_r8_emblem.generate_emblem()
    if style == "crystal":
        return cool
    if style != "magma":
        raise ValueError("Unknown R9 resource pack: " + style)
    # Recolor native tile nibble indices, NOT a post-processing effect on
    # a screenshot: this artwork is loaded by FireRed from external storage.
    # Crystal rim/facets -> molten orange, gold, scarlet and intense pink.
    remap = {0:0, 1:1, 2:7, 3:6, 4:4, 5:7, 6:6, 7:7, 8:5, 9:7}
    result = bytearray(len(cool))
    for idx, b in enumerate(cool):
        lo, hi = b & 15, b >> 4
        if lo not in remap or hi not in remap:
            raise ValueError("Unknown source 4bpp palette index")
        result[idx] = remap[lo] | (remap[hi] << 4)
    magma = bytes(result)
    if len(magma) != 2048 or magma == cool:
        raise AssertionError("R9 art packs must be distinct native 4bpp tiles")
    return magma


def metadata(style: str) -> dict:
    raw = make_pack(style)
    return {"style":style, "bytes":len(raw), "sha256":hashlib.sha256(raw).hexdigest()}


if __name__ == "__main__":
    for name in ("crystal", "magma"):
        print(metadata(name))
