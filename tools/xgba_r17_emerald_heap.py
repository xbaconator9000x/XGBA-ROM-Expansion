"""Emerald-specific, actual-linker-audited reusable guest EWRAM heap-tail policy.

The memory planner is SHARED with FireRed; only ABI/source/linker integration
is Emerald-specific. Save-copy size and HEAP_SIZE are compiled assertions.
"""
from __future__ import annotations
from pathlib import Path
import re
from xgba_memory_plan import MemoryBudgetError

def patch_emerald_heap_tail(emerald:Path,*,reserve_bytes:int,replace_once)->dict[Path,str]:
    if type(reserve_bytes) is not int or not (0<reserve_bytes<=16384) or reserve_bytes%4:
        raise MemoryBudgetError("Emerald heap-tail reserve must be 4-byte aligned <=16KiB")
    base=Path(emerald)
    files=[base/"src/malloc.c",base/"src/load_save.c",base/"ld_script_modern.ld"]
    originals={f:f.read_text() for f in files}
    malloc=replace_once(originals[files[0]],"void InitHeap(void *heapStart, u32 heapSize)\n{",
       "void InitHeap(void *heapStart, u32 heapSize)\n{\n"
       "    /* Preserve external pack arena on EVERY Emerald heap reset. */\n"
       f"    if (heapStart == gHeap && heapSize > HEAP_SIZE - {reserve_bytes}u)\n"
       f"        heapSize = HEAP_SIZE - {reserve_bytes}u;",
       "Emerald native heap reset policy")
    save=replace_once(originals[files[1]],"void MoveSaveBlocks_ResetHeap(void)\n{",
       "void MoveSaveBlocks_ResetHeap(void)\n{\n"
       "    /* Emerald's trainer-ID-dependent relocation copies all three save"
       " blocks into the low heap. This must never overlap XGBA's tail. */\n"
       "    _Static_assert(sizeof(struct SaveBlock2)+sizeof(struct SaveBlock1)+"
       f"sizeof(struct PokemonStorage) <= HEAP_SIZE - {reserve_bytes}u,"
       '"Emerald save-copy overlaps shared XGBA resource arena");',
       "Emerald native save-copy workspace bound")
    ld=replace_once(originals[files[2]],
        "    } > EWRAM",
        "    } > EWRAM\n"
        "    /* R17 real linker-address accounting for existing heap object. */\n"
        "    gXgbaR17HeapEnd = gHeap + 0x1C000;\n"
        f"    gXgbaR17ArenaStart = gXgbaR17HeapEnd - {reserve_bytes};",
        "Emerald source-specific linker audit symbols")
    for file,changed in zip(files,[malloc,save,ld]):
        file.write_text(changed)
    return originals
