#!/usr/bin/env python3
"""XGBA's shared, fail-closed GBA working-memory planner.

External storage capacity is NOT directly addressable GBA memory. Every asset
using a native guest pointer must declare its live phases and transient needs.
Mutually exclusive phases reuse one EWRAM heap-tail reservation; simultaneously
resident resources get distinct aligned slots. The engine's heap, save-copy
scratch, static BSS and physical 256 KiB EWRAM boundaries are never waived.

This module is reusable by all future XGBA resource integrations; it replaces
one-off R14 'max(pack sizes)' arithmetic and hard-coded heap injection.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

EWRAM_START=0x02000000
EWRAM_END=0x02040000
EWRAM_BYTES=EWRAM_END-EWRAM_START
FIRERED_HEAP_BYTES=0x1C000
DEFAULT_HEAP_FLOOR=0x10000
GUEST_FETCH_MAX=0x4000

class MemoryBudgetError(ValueError):
    """The declared resource residency cannot fit safe native memory."""

def align_up(n:int, a:int)->int:
    if not isinstance(n,int) or isinstance(n,bool) or n<0:
        raise MemoryBudgetError("size must be a nonnegative integer")
    if not isinstance(a,int) or isinstance(a,bool) or a<=0 or (a&(a-1)):
        raise MemoryBudgetError("alignment must be a positive power of 2")
    return (n+a-1)&~(a-1)

@dataclass(frozen=True)
class Resource:
    name:str
    bytes:int
    alignment:int=4
    # A single synchronous guest XGBA request remains limited to 16 KiB.
    guest_fetch:bool=True
    def __post_init__(self):
        if not isinstance(self.name,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}",self.name):
            raise MemoryBudgetError("Invalid resource identifier")
        if not isinstance(self.bytes,int) or isinstance(self.bytes,bool) or self.bytes<=0:
            raise MemoryBudgetError("Resource length must be positive")
        align_up(self.bytes,self.alignment)
        if self.guest_fetch and self.bytes>GUEST_FETCH_MAX:
            raise MemoryBudgetError(f"{self.name} exceeds current synchronous guest-request limit")

@dataclass(frozen=True)
class Phase:
    name:str
    resident:tuple[str,...]
    transient_heap_bytes:int=0
    def __post_init__(self):
        if not self.name or not isinstance(self.name,str):
            raise MemoryBudgetError("Missing resource phase identifier")
        if not self.resident or len(self.resident)!=len(set(self.resident)):
            raise MemoryBudgetError("Phase must declare distinct resident resources")
        if not isinstance(self.transient_heap_bytes,int) or self.transient_heap_bytes<0:
            raise MemoryBudgetError("Invalid transient heap demand")

@dataclass(frozen=True)
class Plan:
    reserve_bytes:int
    minimum_heap_bytes:int
    remaining_heap_bytes:int
    phase_slots:dict[str,dict[str,int]]
    phase_live_bytes:dict[str,int]
    resource_sizes:dict[str,int]
    heap_size:int
    save_copy_scratch_bytes:int
    linker_start_symbol:str
    linker_end_symbol:str
    def verify_linker(self,symbols:dict[str,int],heap_symbol:str="gHeap") -> tuple[int,int]:
        """Independently verify real compiled ELF addresses, never inferred offsets."""
        try:
            start=symbols[self.linker_start_symbol]
            end=symbols[self.linker_end_symbol]
            heap=symbols[heap_symbol]
        except KeyError as exc:
            raise MemoryBudgetError("Missing audited native linker symbol") from exc
        if (heap<EWRAM_START or end>EWRAM_END or end-heap!=self.heap_size
            or start!=end-self.reserve_bytes or start%4
            or self.remaining_heap_bytes<self.minimum_heap_bytes):
            raise MemoryBudgetError("Compiled arena violates actual native EWRAM/heap bounds")
        return start,end

def plan_residency(resources:Iterable[Resource], phases:Iterable[Phase], *,
                   heap_bytes:int=FIRERED_HEAP_BYTES,
                   base_heap_floor:int=DEFAULT_HEAP_FLOOR,
                   save_copy_scratch_bytes:int=0,
                   symbol_prefix:str="gXgbaStaging") -> Plan:
    """Return per-phase placements and a single linker-auditable heap-tail arena.

    Different phases may reuse bytes. Within a phase, slots are non-overlapping;
    transient allocations remain charged to the normal engine heap. This does
    not authorise overlapping resource lifetimes outside the declared phases.
    """
    items=list(resources)
    by_name={r.name:r for r in items}
    phase_list=list(phases)
    if not items or len(by_name)!=len(items):
        raise MemoryBudgetError("Resource declarations missing or duplicated")
    if not phase_list or len({p.name for p in phase_list})!=len(phase_list):
        raise MemoryBudgetError("Phases missing or duplicated")
    if (not isinstance(heap_bytes,int) or heap_bytes<=0 or heap_bytes>EWRAM_BYTES
        or not isinstance(base_heap_floor,int) or base_heap_floor<0
        or not isinstance(save_copy_scratch_bytes,int) or save_copy_scratch_bytes<0):
        raise MemoryBudgetError("Invalid physical or engine heap constraint")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",symbol_prefix):
        raise MemoryBudgetError("Invalid linker symbol prefix")
    live={}
    slots={}
    worst_heap=base_heap_floor
    for phase in phase_list:
        placement={}
        cursor=0
        for name in phase.resident:
            if name not in by_name:
                raise MemoryBudgetError(f"Unregistered simultaneous resource: {name}")
            resource=by_name[name]
            cursor=align_up(cursor,resource.alignment)
            placement[name]=cursor
            cursor+=resource.bytes
        slots[phase.name]=placement
        live[phase.name]=cursor
        worst_heap=max(worst_heap,base_heap_floor+phase.transient_heap_bytes)
    reserve=align_up(max(live.values()),4)
    remaining=heap_bytes-reserve
    minimum=max(worst_heap,save_copy_scratch_bytes)
    if remaining<minimum:
        raise MemoryBudgetError(
            f"insufficient GBA working memory: arena={reserve}, heap remains="
            f"{remaining}, required engine/save scratch={minimum}, total={heap_bytes}")
    return Plan(reserve,minimum,remaining,slots,live,
                {r.name:r.bytes for r in items},heap_bytes,save_copy_scratch_bytes,
                symbol_prefix+"ArenaStart",symbol_prefix+"HeapEnd")

def patch_firered_heap_tail(firered:Path, *, reserve_bytes:int,
                            symbol_prefix:str, source_config_header:Path,
                            replace_once) -> dict[Path,str]:
    """Patch every pinned FireRed heap reset with one protected arena contract.

    Returns original source contents for reliable try/finally restoration.
    The same guard is installed in the shared allocator, not just one map
    callback, so future reset callers inherit the protection automatically.
    """
    if not (0<reserve_bytes<FIRERED_HEAP_BYTES and reserve_bytes%4==0):
        raise MemoryBudgetError("Arena reserve must be aligned and fit FireRed heap")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",symbol_prefix):
        raise MemoryBudgetError("Invalid linker symbol prefix")
    cfg=str(source_config_header.resolve())
    if '"' in cfg or "\n" in cfg:
        raise MemoryBudgetError("Unsafe guest include path")
    originals={}
    malloc=firered/"src/malloc.c"
    save=firered/"src/load_save.c"
    linker=firered/"ld_script_modern.ld"
    for path in (malloc,save,linker):
        originals[path]=path.read_text()
    ms=replace_once(originals[malloc],'#include "global.h"',
        '#include "global.h"\n#include "malloc.h"\n#include "'+cfg+'"',
        "XGBA shared heap-budget config")
    ms=replace_once(ms,"void InitHeap(void *heapStart, u32 heapSize)\n{",
        "void InitHeap(void *heapStart, u32 heapSize)\n{\n"
        "    /* XGBA: all subsequent game heap resets retain the reserved tail. */\n"
        f"    if (heapStart == gHeap && heapSize > HEAP_SIZE - {reserve_bytes}u)\n"
        f"        heapSize = HEAP_SIZE - {reserve_bytes}u;",
        "XGBA protected global heap reset")
    ss=replace_once(originals[save],"void MoveSaveBlocks_ResetHeap(void)\n{",
        "void MoveSaveBlocks_ResetHeap(void)\n{\n"
        "    /* FireRed copies saveblocks into the low heap during reset. */\n"
        "    _Static_assert(sizeof(struct SaveBlock2) + sizeof(struct SaveBlock1) + "
        f"sizeof(struct PokemonStorage) <= HEAP_SIZE - {reserve_bytes}u, "
        '"XGBA reserved tail overlaps native save-copy scratch");',
        "XGBA bounded native save-copy scratch")
    ld=replace_once(originals[linker],"        . = 0x1C000;",
        "        . = 0x1C000;\n"
        f"        {symbol_prefix}HeapEnd = .;\n"
        f"        {symbol_prefix}ArenaStart = . - {reserve_bytes};",
        "XGBA real EWRAM linker boundaries")
    malloc.write_text(ms)
    save.write_text(ss)
    linker.write_text(ld)
    return originals
