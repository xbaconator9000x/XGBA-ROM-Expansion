#!/usr/bin/env python3
"""Additional Phase 1 source-anchored P0 assertions, additive to 25 legacy contracts.

Keep legacy source_contract_assertions.json stable: the signed/archived v1
contract has exactly 25 checks. This separate evidence file is additive, not
approval or an XGBA runtime certification.
"""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from verify_source_contracts import PINS

EXTRA_CHECKS=[
("FIRERED_NATIVE_MAP_BLOCK_TRIPLE_MASK","pret/pokefirered","include/global.fieldmap.h",
 "e2828ec0cb1439718e830fbef4366770b3b77b1c",
 r"#define MAPGRID_METATILE_ID_MASK\s+0x03FF[^\n]*\n#define MAPGRID_COLLISION_MASK\s+0x0C00[^\n]*\n#define MAPGRID_ELEVATION_MASK\s+0xF000"),
("FIRERED_NATIVE_MAP_ATTRIBUTE_LAYER_BITS","pret/pokefirered","src/fieldmap.c",
 "41567772299000ba5855419e5c39ad9373a34c20",
 r"\[METATILE_ATTRIBUTE_LAYER_TYPE\]\s*=\s*0x60000000"),
("FIRERED_BACKUP_MAP_FIXED_U16_BUDGET","pret/pokefirered","include/fieldmap.h",
 "639e329a9a0f721abd7e40001228859cb9466005",
 r"#define MAX_MAP_DATA_SIZE\s+0x2800\s*#define VIRTUAL_MAP_SIZE\s+\(MAX_MAP_DATA_SIZE\)"),
("FIRERED_SAVE_VIEW_ARRAY_256_CELLS","pret/pokefirered","include/global.h",
 "77155b09014aa854fcf87260e6ad2969e222da53",
 r"u16 mapView\[0x100\];"),
("FIRERED_SAVE_VIEW_UBFIX_512_VS_256","pret/pokefirered","src/fieldmap.c",
 "41567772299000ba5855419e5c39ad9373a34c20",
 r"#ifndef UBFIX\s*// BUG:[^\n]*\n\s*for \(i = 0; i < 0x200; i\+\+\).*?#else\s*for \(i = 0; i < NELEMS\(gSaveBlock2Ptr->mapView\); i\+\+\)"),
("FIRERED_MODERN_CONFIG_ENABLES_UBFIX","pret/pokefirered","include/config.h",
 "db131b2717ab739e62e41c5054a798f045c0631d",
 r"#if MODERN\s*#ifndef BUGFIX\s*#define BUGFIX\s*#endif // BUGFIX\s*#ifndef UBFIX\s*#define UBFIX"),
("FIRERED_SCRIPT_STACK_20_PTR_SLOTS","pret/pokefirered","include/script.h",
 "ce10c87266a8019eeefaaf787f43b291e7a58624",
 r"const u8 \*stack\[20\];"),
("FIRERED_SCRIPT_PUSH_OFF_BY_ONE_LIMIT","pret/pokefirered","src/script.c",
 "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
 r"if \(ctx->stackDepth \+ 1 >= \(int\)ARRAY_COUNT\(ctx->stack\)\)"),
("FIRERED_SCRIPT_CALL_PUSH_FAILURE_IGNORED","pret/pokefirered","src/script.c",
 "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
 r"void ScriptCall\([^)]*\)\s*\{\s*ScriptPush\(ctx, ctx->scriptPtr\);\s*ctx->scriptPtr = ptr;"),
("PORYMAP_DEFAULT_MAP_BLOCK_FIELDS","huderlem/porymap","src/core/block.cpp",
 "fc4fe774ccd75673c549734055907eb7c79c0fc2",
 r"bitsMetatileId = BitPacker\(0x3FF\);\s*static BitPacker bitsCollision = BitPacker\(0xC00\);\s*static BitPacker bitsElevation = BitPacker\(0xF000\);"),
("PORYMAP_MAP_BLOCK_SERIALIZED_AS_LE16","huderlem/porymap","src/core/blockdata.cpp",
 "5fcd4e32b115790f5a86b5cef5726cace8005017",
 r"uint16_t word = block.rawValue\(\);.*?data.append\(static_cast<char>\(word & 0xff\)\);.*?data.append\(static_cast<char>\(\(word >> 8\) & 0xff\)\);"),
("PORYMAP_EDITOR_SET_ID_PRESERVES_COLLISION_ELEVATION","huderlem/porymap","src/core/maplayout.cpp",
 "44616ab6c9c3ea9b04eff011586b7ec29183588f",
 r"bool Layout::setMetatileId\([^)]*\).*?setBlock\(x, y, Block\(metatileId, block\.collision\(\), block\.elevation\(\)\), enableScriptCallback\);"),
("FIRERED_MAP_SET_ID_REWRITES_COLLISION","pret/pokefirered","src/fieldmap.c",
 "41567772299000ba5855419e5c39ad9373a34c20",
 r"void MapGridSetMetatileIdAt\([^)]*\).*?VMap\.map\[i\] = \(VMap\.map\[i\] & MAPGRID_ELEVATION_MASK\) \| \(metatile & ~MAPGRID_ELEVATION_MASK\);"),
("FIRERED_MAP_SET_ENTRY_OVERWRITES_ALL_FIELDS","pret/pokefirered","src/fieldmap.c",
 "41567772299000ba5855419e5c39ad9373a34c20",
 r"void MapGridSetMetatileEntryAt\([^)]*\).*?VMap\.map\[i\] = metatile;"),
("FIRERED_MAP_IMPASSABILITY_OVERWRITES_COLLISION_BITS","pret/pokefirered","src/fieldmap.c",
 "41567772299000ba5855419e5c39ad9373a34c20",
 r"void MapGridSetMetatileImpassabilityAt\([^)]*\).*?VMap\.map\[x \+ VMap\.Xsize \* y\] \|= MAPGRID_COLLISION_MASK;.*?VMap\.map\[x \+ VMap\.Xsize \* y\] &= ~MAPGRID_COLLISION_MASK;"),
("FIRERED_SCRIPT_SET_TILE_IMPASSABILITY_BRANCH","pret/pokefirered","src/scrcmd.c",
 "97b695ee2f6fca80a3b78f52f6a444f696fe5814",
 r"bool8 ScrCmd_setmetatile\([^)]*\).*?if \(!isImpassable\)\s*MapGridSetMetatileIdAt\(x, y, metatileId\);\s*else\s*MapGridSetMetatileIdAt\(x, y, metatileId \| MAPGRID_COLLISION_MASK\);"),
]

def run(root: Path) -> None:
    if len(EXTRA_CHECKS)!=16:
        raise RuntimeError("Expected 16 additive source contracts; preserve exact review scope")
    if len({r[0] for r in EXTRA_CHECKS})!=len(EXTRA_CHECKS):
        raise RuntimeError("Duplicate P0 source contract names")
    evidence=[]
    for name,repo,path,expected_sha,pattern in EXTRA_CHECKS:
        folder=root/repo.split("/")[-1]
        revision=subprocess.check_output(
            ["git","-C",str(folder),"rev-parse","HEAD"],text=True).strip()
        if revision!=PINS[repo]:
            raise RuntimeError("Pinned source revision changed: "+repo)
        data=(folder/path).read_bytes()
        blob=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        if blob!=expected_sha:
            raise RuntimeError("Source Git blob mismatch: "+repo+"/"+path)
        src=data.decode("utf-8","surrogateescape")
        matched=re.search(pattern,src,re.S)
        if not matched:
            raise RuntimeError("Source ABI contract changed: "+name)
        evidence.append({
            "contract_id":name, "source_repository":repo, "pinned_revision":revision,
            "source_path":path,"source_git_blob_sha1":blob,
            "source_line_start":src.count("\n",0,matched.start())+1,
            "source_line_end":src.count("\n",0,matched.end())+1,
            "matched_source_sha256":hashlib.sha256(
                matched.group(0).encode("utf-8","surrogateescape")).hexdigest(),
            "status":"PINNED_SOURCE_ASSERTION_PASS_NOT_INDEPENDENTLY_REVIEWED",
            "runtime_proof":False, "independent_signoff":False
        })
    output={
        "schema":"xgba.phase1.additive_p0_source_contracts.v1",
        "additive_source_checks_expected":16,
        "additive_source_checks_passed":len(evidence),
        "baseline_source_contracts_expected_unchanged":25,
        "phase1_mapping_complete":False,
        "independent_whole_file_dispositions_approved":0,
        "source_interpretation_scope":"map layout, map-cell mutation, script call stack, default UBFIX switch, editor block writer",
        "source_evidence":evidence
    }
    out=Path("audit-output/p0_additive_source_contract_assertions.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Phase 1 additive pinned P0 contracts: 16/16 source assertions PASS; independent review pending")

if __name__=="__main__":
    try:run(Path(sys.argv[1] if len(sys.argv)>1 else "upstream"))
    except Exception as ex:
        print("P0 ADDITIVE CONTRACT CHECK FAILED:",ex,file=sys.stderr)
        sys.exit(2)
