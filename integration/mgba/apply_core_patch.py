#!/usr/bin/env python3
"""Apply the narrowly scoped, opt-in XGBA R7 extension to pinned mGBA sources.

Fail closed on revision/source drift. This patches a *working copy* of mGBA
for building the extended emulator library, never an installed stock mGBA.
mGBA remains MPL-2.0; no source copied into the XGBA repo.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"


def patch_once(path: Path, old: str, new: str):
    original = path.read_text(encoding="utf-8")
    if original.count(old) != 1:
        raise RuntimeError(f"BLOCKED: expected exactly one pinned source anchor in {path}")
    path.write_text(original.replace(old, new), encoding="utf-8")


def apply(checkout: Path):
    if not (checkout / ".git").is_dir():
        raise RuntimeError("BLOCKED: real upstream mGBA Git checkout missing")
    actual = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if actual != PIN:
        raise RuntimeError("BLOCKED: pinned mGBA revision mismatch: " + actual)
    diff = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain"], text=True)
    if diff.strip():
        raise RuntimeError("BLOCKED: refusing to modify a dirty upstream mGBA checkout")

    header = checkout / "include/mgba/internal/gba/gba.h"
    patch_once(
        header,
        "struct GBA {\n\tstruct mCPUComponent d;",
        "struct XgbaGbaDevice;\n\nstruct GBA {\n"
        "\tstruct XgbaGbaDevice* xgbaDevice; /* null when disabled */\n"
        "\tstruct mCPUComponent d;",
    )
    source = checkout / "src/gba/gba.c"
    patch_once(
        source,
        "static void GBAInit(void* cpu, struct mCPUComponent* component) {\n"
        "\tstruct GBA* gba = (struct GBA*) component;",
        "static void GBAInit(void* cpu, struct mCPUComponent* component) {\n"
        "\tstruct GBA* gba = (struct GBA*) component;\n"
        "\tgba->xgbaDevice = NULL;",
    )
    memory = checkout / "src/gba/memory.c"
    patch_once(
        memory,
        "#include <mgba/internal/gba/memory.h>\n",
        "#include <mgba/internal/gba/memory.h>\n"
        '#include "xgba_mgba_device.h"\n',
    )
    patch_once(
        memory,
        "uint32_t GBALoad32(struct ARMCore* cpu, uint32_t address, int* cycleCounter) {\n"
        "\tstruct GBA* gba = (struct GBA*) cpu->master;",
        "uint32_t GBALoad32(struct ARMCore* cpu, uint32_t address, int* cycleCounter) {\n"
        "\tstruct GBA* gba = (struct GBA*) cpu->master;\n"
        "\tuint32_t xgbaValue = 0;\n"
        "\tif (XgbaDeviceLoad32(gba, address, &xgbaValue)) {\n"
        "\t\tif (cycleCounter) *cycleCounter += 2;\n"
        "\t\treturn xgbaValue;\n"
        "\t}",
    )
    patch_once(
        memory,
        "void GBAStore32(struct ARMCore* cpu, uint32_t address, int32_t value, int* cycleCounter) {\n"
        "\tstruct GBA* gba = (struct GBA*) cpu->master;",
        "void GBAStore32(struct ARMCore* cpu, uint32_t address, int32_t value, int* cycleCounter) {\n"
        "\tstruct GBA* gba = (struct GBA*) cpu->master;\n"
        "\tif (XgbaDeviceStore32(gba, address, (uint32_t)value)) {\n"
        "\t\tif (cycleCounter) ++*cycleCounter;\n"
        "\t\treturn;\n"
        "\t}",
    )
    print("PASS R7 patched pinned mGBA core GBA struct/init/Load32/Store32")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    apply(args.checkout)


if __name__ == "__main__":
    main()
