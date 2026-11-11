#!/usr/bin/env python3
"""Hash- and version-pinned source-level pret/pokeemerald adapter bootstrap.

Never write a ROM file to this repository. Apply only to a locally cloned,
pinned decomp; restore all upstream source even on build failure.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
EMERALD_PIN="731ad5bfd6e6f265508d0efcca0ba42f9dcf5881"
MGBA_PIN="fd9dc5c2cbf234365068855851107e762fc6211b"
EWRAM_FIRST=0x02000000
EWRAM_END=0x02040000
RESOURCE_SIZE=64

class AdapterDrift(RuntimeError):
    pass

def one(s:str,needle:str,after:str,description:str)->str:
    count=s.count(needle)
    if count!=1:
        raise AdapterDrift(f"pinned Emerald {description} drift: expected one anchor, got {count}")
    return s.replace(needle,after,1)

def make_emerald_boot_sources(emerald:Path)->dict[Path,str]:
    root=Path(emerald)
    if not (root/"src/main.c").is_file():
        raise AdapterDrift("pinned Emerald decomp source is absent")
    main=root/"src/main.c"
    before=main.read_text(encoding="utf-8")
    if "gXgbaEmeraldProbe" in before:
        raise AdapterDrift("refusing to modify an already patched Emerald source")
    inc=(ROOT/"integration/emerald/xgba_r16_emerald_boot.inc").read_text()
    inc=inc.replace("__XGBA_SHARED_GUEST__",
                    (ROOT/"integration/fire_red/xgba_guest.h").resolve().as_posix())
    if "__XGBA_" in inc:
        raise AdapterDrift("unresolved guest header path")
    after=one(before,'#include "global.h"',
              '#include "global.h"\n'+inc,"global game ABI include")
    after=one(after,
              "    InitHeap(gHeap, HEAP_SIZE);\n\n    gSoftResetDisabled = FALSE;",
              "    InitHeap(gHeap, HEAP_SIZE);\n"
              "    /* Native XGBA test adapter: original Emerald game continues. */\n"
              "    XgbaEmeraldProbeRun();\n\n    gSoftResetDisabled = FALSE;",
              "source-level post-heap boot callback")
    after=one(after,
              "    for (;;)\n    {\n        ReadKeys();",
              "    for (;;)\n    {\n        XgbaEmeraldMainLoopTick();\n        ReadKeys();",
              "original Emerald main loop iteration instrumentation")
    main.write_text(after,encoding="utf-8")
    return {main:before}

def restore_sources(originals:dict[Path,str])->None:
    for p,data in originals.items():
        p.write_text(data,encoding="utf-8")

def verify_source_contract(emerald:Path)->dict[str,str|int]:
    """Read-only checks for game-specific differences and upstream ABI."""
    path=Path(emerald)
    files={n:(path/n).read_text() for n in (
        "src/main.c","src/overworld.c","src/load_save.c","src/malloc.c",
        "src/save.c","include/malloc.h","ld_script_modern.ld")}
    expected={
        "heap_bytes":(files["include/malloc.h"],"#define HEAP_SIZE 0x1C000"),
        "boot_hook":(files["src/main.c"],"    InitHeap(gHeap, HEAP_SIZE);"),
        "map_lookup":(files["src/overworld.c"],"const struct MapLayout *GetMapLayout(void)"),
        "connected_header":(files["src/overworld.c"],"Overworld_GetMapHeaderByGroupAndId("),
        "flash_save":(files["src/save.c"],"u8 TrySavingData(u8 saveType)"),
        "flash_load":(files["src/save.c"],"u8 LoadGameSave(u8 saveType)"),
        "heap_allocator":(files["src/malloc.c"],"void InitHeap(void *heapStart, u32 heapSize)"),
        "save_copy":(files["src/load_save.c"],"void MoveSaveBlocks_ResetHeap(void)"),
        "emerald_relocate_signature":(files["src/load_save.c"],"void SetSaveBlocksPointers(u16 offset)"),
        "trainerid_relocate":(files["src/load_save.c"],"saveBlock2Copy->playerTrainerId[0] +"),
        "emerald_linker":(files["ld_script_modern.ld"],"    ewram 0x2000000 (NOLOAD) :"),
    }
    missing=[name for name,(s,anchor) in expected.items() if anchor not in s]
    if missing:
        raise AdapterDrift("unsupported Emerald source revision: "+", ".join(missing))
    # FireRed-specific linker symbol and zero-arg save pointer updater
    # MUST NOT be naively patched into Emerald.
    if re.search(r"void SetSaveBlocksPointers\s*\(\s*void\s*\)",files["src/load_save.c"]):
        raise AdapterDrift("Emerald was incorrectly treated as FireRed save ABI")
    return {"engine":"pokeemerald","revision":EMERALD_PIN,
            "guest_abi":1,"heap_bytes":0x1C000,
            "save_pointer_relocate":"SetSaveBlocksPointers(u16 trainer_id_offset)",
            "linker":"ld_script_modern.ld (Emerald-specific; no FireRed heap-tail assumptions)",
            "map_resolver":"GetMapLayout + Overworld_GetMapHeaderByGroupAndId",
            "validated_hooks":len(expected)}
