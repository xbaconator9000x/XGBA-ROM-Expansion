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


def verify_map_cell_word_reference():
    """Exhaustive default-mask arithmetic model, not compiled FireRed or Qt proof.

    Source formulas are first pinned by EXTRA_CHECKS in run(). Model the
    overwrite/preserve effects independently from reconstructed bitfields.
    """
    tile_mask, collision_mask, elevation_mask = 0x03FF, 0x0C00, 0xF000
    if tile_mask | collision_mask | elevation_mask != 0xFFFF:
        raise RuntimeError("Native packed map-cell masks no longer cover 16 bits")
    collisions, elevations = set(), set()
    for raw in range(65536):
        old_id, old_collision, old_elevation = raw & tile_mask, (raw >> 10) & 3, raw >> 12
        collisions.add(old_collision)
        elevations.add(old_elevation)
        new_id = (raw ^ 0x02A5) & tile_mask
        supplied = ((raw * 73) ^ 0xA5C3) & 0xFFFF
        supplied_id = supplied & tile_mask
        supplied_collision = (supplied >> 10) & 3
        supplied_elevation = supplied >> 12
        # Actual formulas are derived from pinned Porymap and FireRed sources.
        actual = {
            "editor_set_id": (raw & (collision_mask | elevation_mask)) | new_id,
            "runtime_set_id": (raw & elevation_mask) | (supplied & ~elevation_mask),
            "runtime_set_entry": supplied,
            "runtime_impassable": raw | collision_mask,
            "runtime_passable": raw & ~collision_mask,
            "script_unblocked": (raw & elevation_mask) | (supplied & ~elevation_mask),
            "script_blocked": (raw & elevation_mask) | ((supplied | collision_mask) & ~elevation_mask),
        }
        # Independent field-wise oracle: elevation/collision/ID ownership.
        expected = {
            "editor_set_id": (old_elevation << 12) | (old_collision << 10) | new_id,
            "runtime_set_id": (old_elevation << 12) | (supplied_collision << 10) | supplied_id,
            "runtime_set_entry": (supplied_elevation << 12) | (supplied_collision << 10) | supplied_id,
            "runtime_impassable": (old_elevation << 12) | (3 << 10) | old_id,
            "runtime_passable": (old_elevation << 12) | old_id,
            "script_unblocked": (old_elevation << 12) | (supplied_collision << 10) | supplied_id,
            "script_blocked": (old_elevation << 12) | (3 << 10) | supplied_id,
        }
        for operation, result in actual.items():
            if result != expected[operation] or not 0 <= result <= 0xFFFF:
                raise RuntimeError(f"Map-cell {operation} field contract failed for 0x{raw:04X}")
    if collisions != set(range(4)) or elevations != set(range(16)):
        raise RuntimeError("Native map-cell collision/elevation coverage incomplete")
    sample = 0x5809
    editor = (sample & (collision_mask | elevation_mask)) | 10
    runtime = (sample & elevation_mask) | 10
    blocked = (sample & elevation_mask) | (10 | collision_mask)
    if (editor, runtime, blocked) != (0x580A, 0x500A, 0x5C0A):
        raise RuntimeError("Editor/runtime/script map-cell distinction regressed")
    return {
        "scope": "PINNED_DEFAULT_16BIT_MAP_CELL_ARITHMETIC_REFERENCE_ONLY",
        "exhaustive_input_words": 65536,
        "operation_models_per_word": 7,
        "field_oracle_comparisons": 65536 * 7,
        "collision_values_covered": 4,
        "elevation_values_covered": 16,
        "distinct_editor_runtime_script_example": ["0x580A", "0x500A", "0x5C0A"],
        "out_of_bounds_coordinates_tested": False,
        "compiled_runtime_tested": False,
        "independent_whole_file_signoff": False,
    }

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
    map_cell_reference=verify_map_cell_word_reference()
    output={
        "schema":"xgba.phase1.additive_p0_source_contracts.v1",
        "map_cell_word_reference":map_cell_reference,
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
    print("Phase 1 additive pinned P0 contracts: 16/16 source assertions PASS; map-cell 65536 words x 7 operations PASS; independent review pending")

if __name__=="__main__":
    try:run(Path(sys.argv[1] if len(sys.argv)>1 else "upstream"))
    except Exception as ex:
        print("P0 ADDITIVE CONTRACT CHECK FAILED:",ex,file=sys.stderr)
        sys.exit(2)
