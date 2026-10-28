#!/usr/bin/env python3
"""Bounded offline model of pinned FireRed map-script table reader ABI.

This is NOT a native FireRed malformed-data safety test. FireRed's reader has
no byte-length argument; these checks reject malformed evidence in the host
validator before it can be misclassified as a valid native ABI witness.
"""
import struct

BASE = 0x08000000


def decode(blob: bytes) -> dict:
    def require(ok, reason):
        if not ok:
            raise ValueError(reason)

    def pointer(off):
        require(off + 4 <= len(blob), "truncated 32-bit pointer")
        address = struct.unpack_from("<I", blob, off)[0]
        require(BASE <= address < BASE + len(blob), "pointer outside linked section")
        return address - BASE

    outer, pos = [], 0
    while True:
        require(pos < len(blob), "missing outer sentinel")
        tag = blob[pos]
        if tag == 0:
            break
        require(pos + 5 <= len(blob), "truncated five-byte outer record")
        outer.append((tag, pointer(pos + 1)))
        require(len(outer) <= 8, "outer table exceeds fixture bound")
        pos += 5

    require(pos == 10 and len(outer) == 2 and [tag for tag, _ in outer] == [3, 2],
            "unexpected outer table shape or sentinel")
    require(outer[0][1] == 29 and outer[1][1] == 11,
            "outer pointer targets wrong labels")

    inner, pos = [], outer[1][1]
    while True:
        require(pos + 2 <= len(blob), "missing two-byte conditional sentinel")
        first = struct.unpack_from("<H", blob, pos)[0]
        if first == 0:
            break
        require(pos + 8 <= len(blob), "truncated eight-byte conditional record")
        second = struct.unpack_from("<H", blob, pos + 2)[0]
        inner.append((first, second, pointer(pos + 4)))
        require(len(inner) <= 8, "conditional table exceeds fixture bound")
        pos += 8

    require(pos == 27 and len(inner) == 2,
            "unexpected conditional table shape or sentinel")
    require(inner == [(0x4000, 0x1234, 30), (0x4001, 0x1235, 31)],
            "conditional values or pointer targets wrong")
    return {
        "outer_records": len(outer),
        "conditional_records": len(inner),
        "outer_sentinel_offset": 10,
        "conditional_sentinel_offset": 27,
    }


def run_negative_controls(linked: bytes) -> list[str]:
    controls = []

    def changed(label, offset, replacement):
        value = bytearray(linked)
        value[offset:offset + len(replacement)] = replacement
        controls.append((label, bytes(value)))

    changed("outer-sentinel-nonzero", 10, b"\x02")
    changed("conditional-sentinel-nonzero", 27, b"\x01\x00")
    changed("conditional-early-zero", 11, b"\x00\x00")
    changed("outer-pointer-outside", 6, struct.pack("<I", BASE + 0x100))
    changed("conditional-pointer-outside", 15, struct.pack("<I", BASE + 0x100))
    changed("outer-pointer-wrong-target", 6, struct.pack("<I", BASE + 12))
    controls += [
        ("truncated-outer", linked[:4]),
        ("truncated-conditional", linked[:14]),
        ("truncated-script", linked[:-1]),
    ]
    passed = []
    for label, value in controls:
        try:
            decode(value)
        except ValueError:
            passed.append(label)
        else:
            raise AssertionError("malformed linked table accepted by bounded host model: " + label)
    return passed
