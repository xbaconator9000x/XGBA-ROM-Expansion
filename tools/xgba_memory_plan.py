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


# Virtual storage addresses, graphics residency, and reset-safe transitions.
#
# Source offsets are 64-bit *storage addresses*, not CPU or PPU pointers.
# A very large logical offset may resolve to a compact host-pack file: it
# never implies a 67-TB sparse file, or 67 TB of GBA EWRAM/VRAM.
#
# R15 budget modelling is not yet an extended EWRAM bus, a PPU change, or a
# working general multi-pack runtime. That requires separate native proofs.

MAX_U64=(1<<64)-1
MAX_POSIX_FILE_OFFSET=(1<<63)-1
ROM_WINDOW_BYTES=32*1024*1024
PHYSICAL_POOLS={
    "bg_vram":64*1024,  # GBA tile modes 0–2
    "obj_vram":32*1024, # GBA tile modes 0–2
    "bg_palette":512,
    "obj_palette":512,
    "oam":1024,
}
GPU_POOLS=frozenset(PHYSICAL_POOLS)
RESIDENCY_POOLS=frozenset(("rom","ewram",*GPU_POOLS))


@dataclass(frozen=True)
class StorageRef:
    """Source identity is independent of guest memory residency.

    virtual_offset addresses the *logical external collection*.
    host_offset is a per-file signed seek; pack_id can select another file,
    segment, or future remote cache. No file is allocated by planning.
    """
    kind:str
    virtual_offset:int
    stored_bytes:int
    resource_id:str=""
    pack_id:str=""
    host_offset:int|None=None

    def __post_init__(self):
        if self.kind not in ("rom","external"):
            raise MemoryBudgetError("unknown storage backing")
        for n,label in ((self.virtual_offset,"logical offset"),(self.stored_bytes,"stored length")):
            if type(n) is not int or n<0 or n>MAX_U64:
                raise MemoryBudgetError(label+" outside unsigned 64-bit range")
        if self.stored_bytes==0 or self.virtual_offset>MAX_U64-self.stored_bytes:
            raise MemoryBudgetError("virtual resource range exceeds uint64")
        if self.kind=="rom":
            if self.virtual_offset+self.stored_bytes>ROM_WINDOW_BYTES:
                raise MemoryBudgetError("ROM backing exceeds 32 MiB")
            if self.resource_id or self.pack_id or self.host_offset is not None:
                raise MemoryBudgetError("ROM source cannot contain external file mapping")
        else:
            if not self.resource_id or not self.pack_id:
                raise MemoryBudgetError("external source needs pack and resource IDs")
            for name in (self.pack_id,self.resource_id):
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",name):
                    raise MemoryBudgetError("invalid external source ID")
            if self.host_offset is not None:
                if (type(self.host_offset) is not int or
                    self.host_offset<0 or
                    self.host_offset>MAX_POSIX_FILE_OFFSET-self.stored_bytes):
                    raise MemoryBudgetError("host signed-64-bit file offset exceeded")

    def host_file_range(self)->tuple[str,int,int]:
        if self.kind!="external" or self.host_offset is None:
            raise MemoryBudgetError("source has no resolved host-file mapping")
        return (self.pack_id,self.host_offset,self.stored_bytes)


@dataclass(frozen=True)
class SceneAsset:
    name:str
    storage:StorageRef
    target:str
    resident_bytes:int
    alignment:int=4
    staging_bytes:int=0

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{0,63}",self.name):
            raise MemoryBudgetError("invalid scene asset ID")
        if self.target not in RESIDENCY_POOLS:
            raise MemoryBudgetError("invalid guest memory target")
        if self.target=="rom" and self.storage.kind!="rom":
            raise MemoryBudgetError("external storage is not CPU-addressable ROM")
        if type(self.resident_bytes) is not int or self.resident_bytes<=0:
            raise MemoryBudgetError("invalid decompressed resident size")
        align_up(self.resident_bytes,self.alignment)
        if (type(self.staging_bytes) is not int or
            self.staging_bytes<0 or self.staging_bytes>GUEST_FETCH_MAX):
            raise MemoryBudgetError("invalid synchronous staging size")
        if self.storage.kind=="rom" and self.staging_bytes:
            raise MemoryBudgetError("local ROM data requires no external staging")
        if (self.storage.kind=="external" and self.target in GPU_POOLS and
            not self.staging_bytes):
            raise MemoryBudgetError("external GPU assets need explicit EWRAM transfer staging")


@dataclass(frozen=True)
class ScenePhase:
    name:str
    assets:tuple[str,...]
    transient_heap_bytes:int=0
    concurrent_fetches:int=1

    def __post_init__(self):
        if not isinstance(self.name,str) or not self.name:
            raise MemoryBudgetError("invalid scene phase name")
        if not self.assets or len(self.assets)!=len(set(self.assets)):
            raise MemoryBudgetError("scene phase needs unique live assets")
        if type(self.transient_heap_bytes) is not int or self.transient_heap_bytes<0:
            raise MemoryBudgetError("invalid transient heap load")
        if type(self.concurrent_fetches) is not int or self.concurrent_fetches<1:
            raise MemoryBudgetError("invalid number of simultaneous fetches")


@dataclass(frozen=True)
class SceneBudget:
    """Budget-only plan. No runtime EWRAM/VRAM extension is claimed."""
    arena_bytes:int
    remaining_heap_bytes:int
    physical_pool_limits:dict[str,int]
    physical_pool_usage:dict[str,dict[str,int]]
    phase_slots:dict[str,dict[str,tuple[str,int,int]]]
    phase_staging_bytes:dict[str,int]
    resource_sources:dict[str,StorageRef]

    def transition(self,old:str,new:str,*,hardware_reset:bool=False)->dict[str,tuple[str,...]]:
        """Explicit retain/release/load/relocate; don't trust stale VRAM pointers."""
        if old not in self.phase_slots or new not in self.phase_slots:
            raise MemoryBudgetError("unknown transition endpoint")
        before=self.phase_slots[old]
        after=self.phase_slots[new]
        release=tuple(x for x in before if x not in after)
        load=tuple(x for x in after if x not in before)
        keep=[]
        relocate=[]
        rebuild=[]
        for name in before.keys()&after.keys():
            prior,current=before[name],after[name]
            if hardware_reset:
                # CPU ROM bytes survive; all RAM/VRAM/palette residency does not.
                if current[0]=="rom":
                    keep.append(name)
                else:
                    rebuild.append(name)
            elif prior!=current:
                relocate.append(name)
            else:
                keep.append(name)
        return {
            "retain":tuple(sorted(keep)),
            "evict":tuple(sorted(release)),
            "load":tuple(sorted(load)),
            "relocate":tuple(sorted(relocate)),
            "rebuild_after_reset":tuple(sorted(rebuild)),
        }


def plan_scene_assets(assets:Iterable[SceneAsset],phases:Iterable[ScenePhase],*,
                      pool_reserved:dict[str,int]|None=None,
                      heap_bytes:int=FIRERED_HEAP_BYTES,
                      engine_heap_floor:int=DEFAULT_HEAP_FLOOR,
                      save_copy_scratch_bytes:int=0)->SceneBudget:
    """Check all simultaneous GBA memory pools; reuse storage between scenes.

    For GPU pools, explicit audited base-engine reservations are MANDATORY.
    GPU bytes are placements relative to the free pool, not native addresses.
    Peak temporary EWRAM staging is the sum of the largest N concurrent
    fetches in that phase, independent of multi-terabyte host offsets.
    """
    items=list(assets)
    live_phases=list(phases)
    if not items or len(items)!=len({x.name for x in items}):
        raise MemoryBudgetError("missing or duplicated scene assets")
    if not live_phases or len(live_phases)!=len({p.name for p in live_phases}):
        raise MemoryBudgetError("missing or duplicated scene phases")
    if type(heap_bytes) is not int or not 0<heap_bytes<=EWRAM_BYTES:
        raise MemoryBudgetError("invalid physical EWRAM heap size")
    if (type(engine_heap_floor) is not int or engine_heap_floor<0 or
        type(save_copy_scratch_bytes) is not int or save_copy_scratch_bytes<0):
        raise MemoryBudgetError("invalid engine/saving heap requirements")
    by_name={a.name:a for a in items}
    referenced=set()
    pool_reserved={} if pool_reserved is None else dict(pool_reserved)
    if any(k not in GPU_POOLS for k in pool_reserved):
        raise MemoryBudgetError("unrecognised GBA graphics memory pool")
    physical_limits={}
    for name,total in PHYSICAL_POOLS.items():
        if name in pool_reserved:
            amount=pool_reserved[name]
            if type(amount) is not int or not 0<=amount<=total:
                raise MemoryBudgetError("invalid existing engine VRAM/palette allocation")
            physical_limits[name]=total-amount
    slots={}
    usage={}
    staging={}
    peak=0
    for phase in live_phases:
        phase_slots={}
        offset={k:0 for k in ("ewram",*GPU_POOLS)}
        sources=[]
        for name in phase.assets:
            if name not in by_name:
                raise MemoryBudgetError("unregistered live asset "+name)
            referenced.add(name)
            asset=by_name[name]
            if asset.target=="rom":
                phase_slots[name]=("rom",asset.storage.virtual_offset,asset.resident_bytes)
                continue
            if asset.target in GPU_POOLS and asset.target not in physical_limits:
                raise MemoryBudgetError("native GPU pool requires audited engine reservation: "+asset.target)
            cursor=align_up(offset[asset.target],asset.alignment)
            offset[asset.target]=cursor+asset.resident_bytes
            phase_slots[name]=(asset.target,cursor,asset.resident_bytes)
            if asset.storage.kind=="external":
                sources.append(asset.staging_bytes)
        for pool,total in PHYSICAL_POOLS.items():
            if offset[pool]>physical_limits.get(pool,total):
                raise MemoryBudgetError(f"{phase.name} exceeds real {pool}: "+str(offset[pool]))
        sizes=sorted(sources,reverse=True)
        temp=sum(sizes[:phase.concurrent_fetches])
        ewr=offset["ewram"]+temp
        needed=max(engine_heap_floor+phase.transient_heap_bytes,
                   save_copy_scratch_bytes)
        if align_up(ewr,4)+needed>heap_bytes:
            raise MemoryBudgetError(f"{phase.name} exceeds real EWRAM working-memory budget")
        peak=max(peak,align_up(ewr,4))
        staging[phase.name]=temp
        usage[phase.name]=offset
        slots[phase.name]=phase_slots
    if referenced!=set(by_name):
        raise MemoryBudgetError("declared assets not assigned to any phase")
    return SceneBudget(peak,heap_bytes-peak,physical_limits,usage,slots,staging,
                       {a.name:a.storage for a in items})
