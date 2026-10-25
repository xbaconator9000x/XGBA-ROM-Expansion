#!/usr/bin/env python3
"""Source-backed ROM mapping, music pointer and animated-tile DMA lifecycle contracts.

Only exact, ordered source invariants verified at immutable pinned Git blobs
are accepted; no claims of actual emulator runtime behavior, race freedom, or
all-file semantic signoff. Emits line-level provenance + design obligations.
"""
from __future__ import annotations
import csv,hashlib,json,re,subprocess,sys
from pathlib import Path

PINS={"mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b",
      "pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982"}
BLOBS={
 ("mgba-emu/mgba","src/gba/gba.c"):"c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
 ("mgba-emu/mgba","src/gba/memory.c"):"aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
 ("pret/pokefirered","src/m4a.c"):"ebd3afe291b6c4e9f2ac62250a87c6a0482086d4",
 ("pret/pokefirered","src/tileset_anims.c"):"04854a2e46a1d2ca89626e7be92955d6a20490e5"}
ROOT=Path("upstream");OUT=Path("audit-output")
FIELDS=["contract_id","repo","pinned_commit","path","git_blob_sha",
        "begin_line","end_line","source_exact_anchors","observed_semantics",
        "required_extension_invariant","verification_type","runtime_test_status"]
# All sequences require the listed source substrings in order, within a named function
CONTRACTS=[
 ("XC23-ROM-UNLOAD-RESOURCE-OWNERSHIP","mgba-emu/mgba","src/gba/gba.c",
  "GBAUnloadROM",["GBAUnlCartUnload(gba);","mappedMemoryFree(gba->memory.rom, GBA_SIZE_ROM0);",
                 "gba->romVf->unmap(gba->romVf, gba->memory.rom, gba->pristineRomSize);",
                 "gba->romVf->close(gba->romVf);","gba->memory.rom = NULL;","gba->memory.romSize = 0;"],
  "ROM backing memory is freed/unmapped and ROM VFile closed; active memory pointer becomes invalid.",
  "Sidecar streams and all cached pointers must be invalidated when game ROM unloads."),
 ("XC23-ROM-MATRIX-OVER32-LOAD","mgba-emu/mgba","src/gba/gba.c",
  "GBALoadROM",["GBAUnloadROM(gba);","gba->pristineRomSize = vf->size(vf);",
                "if (gba->pristineRomSize > GBA_SIZE_ROM0)","vf->seek(vf, 0xAC, SEEK_SET);",
                "if (ident == 'M')","gba->memory.romSize = 0x01000000;"],
  "Oversize ROM takes special cartridge path when byte at 0xAC is M, rather than direct contiguous ROM.",
  "XGBA extension activation must not commandeer Matrix's header discriminator."),
 ("XC23-ROM-OVER32-NONMATRIX-CAPPED","mgba-emu/mgba","src/gba/gba.c",
  "GBALoadROM",["if (gba->pristineRomSize > GBA_SIZE_ROM0)",
               "if (ident == 'M')","gba->memory.rom = vf->map(vf, GBA_SIZE_ROM0, MAP_READ);",
               "gba->memory.romSize = GBA_SIZE_ROM0;"],
  "Oversize non-Matrix input is mapped to 32 MiB; underlying file size is not addressable as a single ROM pointer.",
  "Use explicit bounded bank windows or host-side opaque resources, not a linear multi-GB ROM load."),
 ("XC23-ROM-LOAD-ACTIVE-REGION-REFRESH","mgba-emu/mgba","src/gba/gba.c",
  "GBALoadROM",["gba->memory.romMask = toPow2(gba->memory.romSize) - 1;",
                "if (gba->cpu && gba->memory.activeRegion >= GBA_REGION_ROM0)",
                "gba->cpu->memory.setActiveRegion(gba->cpu, gba->cpu->gprs[ARM_PC]);"],
  "ROM load updates the mask and refreshes instruction activeRegion when CPU points into cartridge space.",
  "After any bank replacement, re-evaluate ARM/Thumb instruction base and prefetch coherence."),
 ("XC23-ROM-COPY-ON-WRITE-PIPELINE","mgba-emu/mgba","src/gba/memory.c",
  "_pristineCow",["void* newRom = anonymousMemoryMap(GBA_SIZE_ROM0);",
                 "memcpy(newRom, gba->memory.rom, gba->memory.romSize);",
                 "if (gba->cpu->memory.activeRegion == gba->memory.rom)",
                 "gba->cpu->memory.activeRegion = newRom;",
                 "gba->memory.rom = newRom;",
                 "gba->memory.hw.gpioBase = &((uint16_t*) gba->memory.rom)[GPIO_REG_DATA >> 1];"],
  "ROM COW rewires active CPU fetch pointer and GPIO address after changing mapped backing bytes.",
  "Any streaming page replacement must preserve CPU fetch and GPIO pointer validity, including cheat/patch writes."),
 ("XC23-ROM-PATCH-NEW-BACKING","mgba-emu/mgba","src/gba/gba.c",
  "GBAApplyPatch",["size_t patchedSize = patch->outputSize(patch, gba->memory.romSize);",
                   "if (!patchedSize || patchedSize > GBA_SIZE_ROM0)",
                   "void* newRom = anonymousMemoryMap(GBA_SIZE_ROM0);",
                   "gba->memory.rom = newRom;",
                   "gba->memory.hw.gpioBase = &((uint16_t*) gba->memory.rom)[GPIO_REG_DATA >> 1];",
                   "gba->memory.romMask = toPow2(patchedSize) - 1;"],
  "Standard mGBA ROM patch path bounds output to 32 MiB and changes the underlying mapped pointer.",
  "Extension patcher needs a separate host-side package contract; do not overload original ROM patch semantics."),
 ("XC23-AUDIO-MPLAY-HEADER-OWNED","pret/pokefirered","src/m4a.c",
  "MPlayStart",["mplayInfo->songHeader = songHeader;","mplayInfo->tone = songHeader->tone;",
                "while (i < songHeader->trackCount && i < mplayInfo->trackCount)",
                "track->cmdPtr = songHeader->part[i];"],
  "Sound driver persists song header, tone and per-track bytecode pointers after MPlayStart returns.",
  "Externally stored music must stage stable voicegroup/header/track bodies for full playback lifetime."),
 ("XC23-AUDIO-SONG-TABLE-INDEX","pret/pokefirered","src/m4a.c",
  "m4aSongNumStart",["const struct Song *songTable = gSongTable;",
                     "const struct Song *song = &songTable[n];",
                     "const struct MusicPlayer *mplay = &mplayTable[song->ms];",
                     "MPlayStart(mplay->info, song->header);"],
  "Song IDs index a compiled pointer-bearing table and choose mplay by field song->ms.",
  "Adding songs needs bounded table and player indices; package IDs are not raw GBA song-header pointers."),
 ("XC23-AUDIO-STOP-DOES-NOT-FREE-HEADER","pret/pokefirered","src/m4a.c",
  "m4aMPlayStop",["mplayInfo->status |= MUSICPLAYER_STATUS_PAUSE;",
                  "TrackStop(mplayInfo, track);","mplayInfo->ident = ID_NUMBER;"],
  "Stop pauses and stops tracks but source has no explicit clearing of songHeader.",
  "Avoid eviction based solely on stop invocation without checking retained pointers and resume paths."),
 ("XC23-TILE-DMA-QUEUE-BOUNDED","pret/pokefirered","src/tileset_anims.c",
  "AppendTilesetAnimToBuffer",["if (sTilesetDMA3TransferBufferSize < 20)",
                               "sTilesetDMA3TransferBuffer[sTilesetDMA3TransferBufferSize].src = src;",
                               "sTilesetDMA3TransferBuffer[sTilesetDMA3TransferBufferSize].dest = dest;",
                               "sTilesetDMA3TransferBuffer[sTilesetDMA3TransferBufferSize].size = size;",
                               "sTilesetDMA3TransferBufferSize++;"],
  "Animation transfer queue records borrowed data pointers in a 20-slot bounded buffer.",
  "Streaming tiles must remain resident until queued DMA executes; preserve full buffer behavior."),
 ("XC23-TILE-DMA-QUEUE-DEFERRED","pret/pokefirered","src/tileset_anims.c",
  "TransferTilesetAnimsBuffer",["for (i = 0; i < sTilesetDMA3TransferBufferSize; i++)",
                               "DmaCopy16(3, sTilesetDMA3TransferBuffer[i].src, sTilesetDMA3TransferBuffer[i].dest, sTilesetDMA3TransferBuffer[i].size);",
                               "sTilesetDMA3TransferBufferSize = 0;"],
  "DMA3 reads queued source pointers later rather than copying synchronously during enqueue.",
  "Page eviction and animated-frame replacement must be synchronized after transfer completion."),
 ("XC23-TILE-DMA-CALLBACKS-MAP-BOUND","pret/pokefirered","src/tileset_anims.c",
  "_InitPrimaryTilesetAnimation",["if (gMapHeader.mapLayout->primaryTileset && gMapHeader.mapLayout->primaryTileset->callback)",
                                   "gMapHeader.mapLayout->primaryTileset->callback();"],
  "Current map layout's primary tileset callback installs the animation callback.",
  "Tile animations depend on map layout/tileset metadata and cannot be flattened to static bitmap."),
 ("XC23-TILE-DMA-SECONDARY-MAP-BOUND","pret/pokefirered","src/tileset_anims.c",
  "_InitSecondaryTilesetAnimation",["if (gMapHeader.mapLayout->secondaryTileset && gMapHeader.mapLayout->secondaryTileset->callback)",
                                     "gMapHeader.mapLayout->secondaryTileset->callback();"],
  "Current map layout's secondary tileset callback is independently installed.",
  "Preserve independently addressable primary/secondary animation callbacks during map edits."),
]
def gitblob(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def function_extent(src,name):
 # Generic, constrained definition: after token and an open/closed parameter list, first {
 expr=re.compile(r"\b"+re.escape(name)+r"\s*\([^;{}]*\)\s*\{",re.S)
 hits=list(expr.finditer(src))
 if len(hits)!=1:raise ValueError(f"Expected one definition of {name}: {len(hits)}")
 m=hits[0];open_at=src.find("{",m.start(),m.end())
 depth=0;end=None
 # Inputs are pinned; substring order checks do not need to infer nested scope.
 for pos in range(open_at,len(src)):
  if src[pos]=="{":depth+=1
  elif src[pos]=="}":
   depth-=1
   if depth==0:end=pos+1;break
 if end is None:raise ValueError("Unbalanced function "+name)
 return m.start(),end
def main():
 for repo,pin in PINS.items():
  folder=ROOT/repo.split("/")[-1]
  actual=subprocess.check_output(["git","-C",str(folder),"rev-parse","HEAD"],text=True).strip()
  if actual!=pin:raise RuntimeError("Pinned revision mismatch "+repo)
 cache={}
 evidence=[]
 for cid,repo,path,func,anchors,observation,requirement in CONTRACTS:
  key=(repo,path)
  if key not in cache:
   folder=ROOT/repo.split("/")[-1];raw=(folder/path).read_bytes()
   expected=BLOBS[key]
   if gitblob(raw)!=expected:raise RuntimeError("Wrong source Git blob "+repr(key))
   cache[key]=raw.decode("utf-8","surrogateescape")
  src=cache[key]
  start,end=function_extent(src,func)
  body=src[start:end];last=-1;positions=[]
  for token in anchors:
   i=body.find(token,last+1)
   if i<0:raise RuntimeError(f"{cid}: missing or out-of-order source clause: {token[:100]}")
   last=i;positions.append(start+i)
  evidence.append({"contract_id":cid,"repo":repo,"pinned_commit":PINS[repo],
    "path":path,"git_blob_sha":BLOBS[key],
    "begin_line":min(src.count("\n",0,pos)+1 for pos in positions),
    "end_line":max(src.count("\n",0,pos)+1 for pos in positions),
    "source_exact_anchors":json.dumps(anchors),"observed_semantics":observation,
    "required_extension_invariant":requirement,
    "verification_type":"EXACT_PINNED_SOURCE_FUNCTION_ORDER",
    "runtime_test_status":"NOT_RUN"})
 OUT.mkdir(exist_ok=True)
 with (OUT/"resource_lifecycle_contracts.csv").open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(evidence)
 summary={"pinned_source_contracts_passed":len(evidence),
  "distinct_source_files_checked":len(cache),"critical_areas":{
    "mGBA_ROM_lifecycle":sum(e["repo"]=="mgba-emu/mgba" for e in evidence),
    "FireRed_music_lifecycle":sum(e["path"]=="src/m4a.c" for e in evidence),
    "FireRed_tileset_DMA_lifecycle":sum(e["path"]=="src/tileset_anims.c" for e in evidence)},
  "source_blob_revisions":[{"repo":repo,"path":path,"sha":BLOBS[(repo,path)]} for repo,path in sorted(cache)],
  "runtime_paths_exercised":0,"whole_file_semantic_dispositions_approved":0,
  "phase1_mapping_complete":False,
  "limitations":["Exact source clauses verified in pinned functions but branching and aliasing are not path-complete.",
    "No emulator/audio/VRAM runtime instrumentation run in this stage.",
    "No XGBA sidecar, bank switch or external music payload implemented."]}
 (OUT/"resource_lifecycle_contracts_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":
 try:main()
 except Exception as e:
  print("RESOURCE CONTRACT FAILED:",repr(e),file=sys.stderr)
  sys.exit(2)
