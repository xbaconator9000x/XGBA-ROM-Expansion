#!/usr/bin/env python3
"""Pinned source closure and native evidence checks for the Phase 1 save path."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

F = "pret/pokefirered"
A = "pret/agbcc"
M = "mgba-emu/mgba"
PINS = {
    F: "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    A: "da598c1d918402c42c0c0d7128ba14567f3175e9",
    M: "fd9dc5c2cbf234365068855851107e762fc6211b",
}
def _file(repo, path, blob, role, dependencies=()):
    return (repo, path), {
        "blob": blob,
        "role": role,
        "dependencies": list(dependencies),
    }


FILES = dict([
    _file(F, "src/main.c", "542b0f5d16dd93107523d11163bfcb70a42b707a",
          "input and callback dispatch", ["src/field_control_avatar.c", "src/main_menu.c", "src/task.c"]),
    _file(F, "src/task.c", "01503dc7ae78cf2348524bfb5bbb89183640f944",
          "task scheduler", ["include/task.h", "src/main_menu.c"]),
    _file(F, "include/task.h", "2f9f1c0d8755572d5ccc5c4190339ffaca2d4bbf",
          "task ABI", ["src/task.c"]),
    _file(F, "src/field_control_avatar.c", "b1b6465941133b927505be92d189a7c283e4722f",
          "controller-driven field input", ["src/overworld.c", "include/main.h"]),
    _file(F, "src/main_menu.c", "5cef7c46ea5dcaccbdb3698909e9fc23e7d00b9c",
          "title-menu task dispatch", ["src/task.c", "src/overworld.c"]),
    _file(F, "src/menu.c", "9ee9968cbce6a271e37cee856234a38c07904537",
          "menu cursor and selection", ["src/main_menu.c", "src/start_menu.c"]),
    _file(F, "src/start_menu.c", "88cc377cea556d3663aa5ea5f5bd4537cb29ea72",
          "in-field Save menu and dialog", ["src/save.c", "src/task.c", "include/save.h"]),
    _file(F, "src/save.c", "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
          "save selection, sectors, and writer", ["include/save.h", "src/agb_flash.c"]),
    _file(F, "src/load_save.c", "8b723dd044c6024b3671bb890b25b56a53f99ec5",
          "Flash detection and save load", ["src/save.c", "src/agb_flash_1m.c"]),
    _file(F, "src/overworld.c", "339014da46ae8543143edc99ab72bf7496203a0d",
          "field/map continuation", ["src/field_control_avatar.c", "src/load_save.c"]),
    _file(F, "src/agb_flash.c", "08aeed1638e214a3cad8b28d103964ab24342fba",
          "Flash-sector program and verify", ["src/agb_flash_mx.c", "include/gba/flash_internal.h"]),
    _file(F, "src/agb_flash_1m.c", "e249fab9a350f3263e7df5f20ff301a6d008e3db",
          "Flash device identification", ["src/agb_flash_le.c", "src/agb_flash_mx.c"]),
    _file(F, "src/agb_flash_le.c", "39d956e2778af564cf187ea732a019e46479ac12",
          "1-Mbit Flash device geometry", ["include/gba/flash_internal.h"]),
    _file(F, "src/agb_flash_mx.c", "b4f710f36449c46946294d0df3d61d493d5c0d1f",
          "Flash erase/program bus protocol", ["src/agb_flash.c", "include/gba/flash_internal.h"]),
    _file(F, "include/save.h", "87fb9b615b434b58823d15688056695acda9feab",
          "save-sector layout and status ABI", ["src/save.c"]),
    _file(F, "include/global.h", "77155b09014aa854fcf87260e6ad2969e222da53",
          "game global structures", ["include/save.h", "include/main.h"]),
    _file(F, "include/main.h", "31b22a3faa75409125257396913689a6a37c98ac",
          "input and callback state layout", ["src/main.c"]),
    _file(F, "include/gba/flash_internal.h", "39e14ef73ce3d020427baada43ab165d34d04e8b",
          "game Flash API and device ABI", ["src/agb_flash.c"]),
    _file(F, "ld_script.ld", "9a4b45031e93c1e1da8186d8c697332710526048",
          "revision-0 link layout", ["include/global.h", "pokefirered.elf"]),
    _file(A, "build.sh", "dff3352a35d2c38f38f04d8035acfd80cbe6af9d",
          "pinned agbcc build entry", ["install.sh"]),
    _file(A, "install.sh", "637a21da683e0fb78a38355548a42319cd6291e9",
          "pinned agbcc install entry", ["firered/Makefile"]),
    _file(M, "src/arm/arm.c", "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
          "native ARM/Thumb instruction execution", ["src/gba/memory.c", "src/gba/core.c"]),
    _file(M, "src/gba/core.c", "6bfc518bb8899205c07d1d0fc091a287cb42f874",
          "mCore stepping and GBA lifecycle", ["include/mgba/core/core.h", "src/arm/arm.c"]),
    _file(M, "src/gba/memory.c", "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
          "GBA store dispatch to savedata", ["src/gba/savedata.c", "include/mgba/internal/gba/memory.h"]),
    _file(M, "src/gba/savedata.c", "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
          "Flash command/state and mapped bytes", ["include/mgba/internal/gba/savedata.h", "src/util/vfs/vfs-fd.c"]),
    _file(M, "src/gba/gba.c", "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
          "frame-end save cleanup dispatch", ["src/gba/savedata.c", "src/gba/core.c"]),
    _file(M, "src/util/vfs/vfs-fd.c", "2535bd0fb76740745ae038d5523ead28658f1035",
          "file mapping, sync, and close behavior", ["src/gba/savedata.c"]),
    _file(M, "include/mgba/core/core.h", "64ddf851ef00ab09416a9c1c9b5a88798fcd6fc8",
          "core input, step, and save APIs", ["src/gba/core.c"]),
    _file(M, "include/mgba/internal/gba/memory.h", "0aad912613e726560d06bbdbf6061986e69e5842",
          "Flash memory regions and savedata member", ["src/gba/memory.c"]),
    _file(M, "include/mgba/internal/gba/savedata.h", "6227be25e8c9d2c1cc14c06ded34389b96138577",
          "Flash state, dirty flag, and mapped data ABI", ["src/gba/savedata.c"]),
    _file(M, "LICENSE", "14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e",
          "mGBA license text", []),
])

ANCHORS = {
    (F, "src/main.c"): (
        "static void ReadKeys(void)", "static void CallCallbacks(void)",
        "gMain.callback2()", "gMain.newKeys = gMain.newKeysRaw;",
    ),
    (F, "src/task.c"): ("void RunTasks(void)", "gTasks[taskId].func(taskId);"),
    (F, "src/field_control_avatar.c"): ("FieldGetPlayerInput",),
    (F, "src/main_menu.c"): (
        "CB2_InitMainMenu", "Task_ExecuteMainMenuSelection", "RunTasks();",
    ),
    (F, "src/start_menu.c"): (
        "StartMenuSaveCallback", "SaveDialogCB_DoSave",
        "TrySavingData(SAVE_NORMAL)",
    ),
    (F, "src/save.c"): (
        "static u8 TryWriteSector(u8 sectorNum, u8 *data)",
        "ProgramFlashSectorAndVerify(sectorNum, data)",
        "u8 TrySavingData(u8 saveType)",
    ),
    (F, "src/overworld.c"): (
        "FieldGetPlayerInput(&fieldInput, newKeys, heldKeys)",
        "RunTasks();", "CB2_Overworld",
    ),
    (F, "src/agb_flash.c"): (
        "u32 ProgramFlashSectorAndVerify(u16 sectorNum, u8 *src)",
        "ProgramFlashSector(sectorNum, src)",
        "VerifyFlashSector(sectorNum, src)",
    ),
    (F, "src/agb_flash_mx.c"): (
        "u16 ProgramFlashSector_MX(u16 sectorNum, void *src)",
        "EraseFlashSector_MX(sectorNum)",
        "*dest = *src;",
    ),
    (M, "src/arm/arm.c"): ("void ARMRun(", "void ARMRunLoop("),
    (M, "src/gba/memory.c"): (
        "void GBAStore8(", "GBASavedataWriteFlash(&memory->savedata, address, value)",
    ),
    (M, "src/gba/savedata.c"): (
        "void GBASavedataWriteFlash(",
        "savedata->currentBank[address] = value;",
        "savedata->dirty |= mSAVEDATA_DIRT_NEW;",
    ),
    (M, "src/gba/gba.c"): ("GBASavedataClean(&gba->memory.savedata",),
    (M, "src/util/vfs/vfs-fd.c"): (
        "MAP_SHARED", "msync(buffer, size, MS_ASYNC)", "fsync(vfd->fd)",
    ),
    (M, "include/mgba/core/core.h"): (
        "void (*runFrame)(struct mCore*);", "void (*step)(struct mCore*);",
        "void (*setKeys)(struct mCore*, uint32_t keys);",
    ),
}

MUTATIONS = (
    ((F, "src/start_menu.c"), b"TrySavingData(SAVE_NORMAL)", b"TrySavingData(0)"),
    ((F, "src/save.c"), b"ProgramFlashSectorAndVerify(sectorNum, data)", b"TryWriteSector(sectorNum, data)"),
    ((F, "src/agb_flash_mx.c"), b"*dest = *src;", b"*dest = 0xFF;"),
    ((M, "src/gba/memory.c"),
     b"GBASavedataWriteFlash(&memory->savedata, address, value)",
     b"GBASavedataWriteFlash(NULL, address, value)"),
    ((M, "src/gba/savedata.c"),
     b"savedata->currentBank[address] = value;", b"savedata->currentBank[address] = 0;"),
    ((M, "src/util/vfs/vfs-fd.c"), b"MAP_SHARED", b"MAP_PRIVATE"),
)


def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def validate_sources(data):
    if set(data) != set(FILES):
        raise ValueError("Pinned save-path source inventory is incomplete or has extras")
    for key, metadata in FILES.items():
        if blob_sha(data[key]) != metadata["blob"]:
            raise ValueError("Pinned Git blob mismatch: " + str(key))
    return True


def validate_callgraph(data):
    lines_by_file = {key: raw.decode("utf-8").splitlines() for key, raw in data.items()}
    line_refs = {}
    for key, phrases in ANCHORS.items():
        lines = lines_by_file[key]
        for phrase in phrases:
            found = [n for n, line in enumerate(lines, 1) if phrase in line]
            if not found:
                raise ValueError("Source callgraph anchor missing: " + str((key, phrase)))
            line_refs.setdefault(key, {})[phrase] = found
    save = data[(F, "src/save.c")].decode()
    if "svc_WriteSector(sectorNum, data);" not in save:
        raise ValueError("Revision-10 save branch disappeared from the pinned source context")
    return line_refs


def negative_controls(data):
    count = 0
    for key, old, new in MUTATIONS:
        if old not in data[key]:
            raise AssertionError("Source mutation is not anchored: " + str(key))
        mutated = dict(data)
        mutated[key] = data[key].replace(old, new, 1)
        try:
            validate_callgraph(mutated)
        except ValueError:
            count += 1
        else:
            raise AssertionError("Mutated source callgraph was accepted: " + str(key))
    changed_blob = dict(data)
    key = (F, "include/save.h")
    changed_blob[key] += b"\n"
    try:
        validate_sources(changed_blob)
    except ValueError:
        count += 1
    else:
        raise AssertionError("Mutated source blob was accepted")
    return count


def validate_native_flash_trace(rows, no_save=False):
    if not isinstance(rows, list):
        raise AssertionError("Flash-program evidence must be a list")
    if no_save:
        if rows:
            raise AssertionError("No-input control observed compiled Flash program calls")
        return []
    if len(rows) != 14:
        raise AssertionError("Expected fourteen compiled game Flash-sector program returns")
    expected = set(range(14, 28))
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise AssertionError("Malformed compiled Flash-sector observation")
        values = (row.get("sector"), row.get("return_value"),
                  row.get("changed_bytes"), row.get("dirty_after"),
                  row.get("entry_pc"), row.get("return_pc"),
                  row.get("entry_frame"), row.get("return_frame"))
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise AssertionError("Flash-sector observation contains non-integer evidence")
        sector, result, changed, dirty, entry_pc, return_pc, entry_frame, return_frame = values
        if sector not in expected or sector in seen:
            raise AssertionError("Missing, duplicate, or unexpected physical Flash sector")
        if (result != 0 or changed <= 0 or dirty == 0 or
                not 0x08000000 <= entry_pc < 0x0A000000 or
                not 0x08000000 <= return_pc < 0x0A000000 or
                entry_frame < 180 or return_frame < entry_frame):
            raise AssertionError("Flash-sector return or mapped mGBA effect was not verified")
        seen.add(sector)
    if seen != expected:
        raise AssertionError("Compiled game did not program every expected physical sector")
    return sorted(seen)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_dossier(data, line_refs, output):
    output.mkdir(parents=True, exist_ok=True)
    dossier_dir = output / "source_dossiers"
    records = []
    for key, metadata in FILES.items():
        repo, path = key
        license_note = (
            "MPL-2.0; see pinned mgba/LICENSE"
            if (repo, path) == (M, "LICENSE")
            else "No root LICENSE file at pinned commit; original file headers/repository terms apply"
            if repo in (F, A)
            else "See the pinned repository LICENSE"
        )
        record = {
            "schema": "xgba-phase1-source-file-v1",
            "repository": repo,
            "commit": PINS[repo],
            "path": path,
            "git_blob_sha1": metadata["blob"],
            "source_sha256": hashlib.sha256(data[key]).hexdigest(),
            "source_bytes": len(data[key]),
            "role": metadata["role"],
            "direct_dependencies": metadata["dependencies"],
            "license_evidence": license_note,
            "source_anchor_lines": line_refs.get(key, {}),
            "evidence_status": "NEEDS_EVIDENCE",
        }
        record_bytes = _canonical(record)
        record["machine_dossier_sha256"] = hashlib.sha256(record_bytes).hexdigest()
        compressed = gzip.compress(record_bytes, mtime=0)
        record["compressed_dossier_sha256"] = hashlib.sha256(compressed).hexdigest()
        relative = Path("source_dossiers") / repo.replace("/", "_") / (path.replace("/", "__") + ".json.gz")
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(compressed)
        records.append({
            "path": str(relative),
            "machine_dossier_sha256": record["machine_dossier_sha256"],
            "compressed_dossier_sha256": record["compressed_dossier_sha256"],
            "compressed_bytes": len(compressed),
        })
    manifest = {
        "schema": "xgba-phase1-save-path-closure-v1",
        "pinned_revisions": PINS,
        "source_file_count": len(FILES),
        "source_mutation_negative_controls": negative_controls(data),
        "callgraph": [
            {"from": "FireRed input ReadKeys -> callback/task dispatch",
             "to": "CB2_Overworld/RunTasks -> FieldGetPlayerInput -> StartMenuSaveCallback"},
            {"from": "StartMenuSaveCallback -> SaveDialogCB_DoSave",
             "to": "TrySavingData(SAVE_NORMAL)"},
            {"from": "TrySavingData -> TryWriteSector",
             "to": "ProgramFlashSectorAndVerify (REVISION < 0xA); svc_WriteSector is a distinct revision-10 branch"},
            {"from": "ProgramFlashSectorAndVerify -> ProgramFlashSector_MX",
             "to": "EraseFlashSector_MX and byte program/verify using GBA Flash bus stores"},
            {"from": "mGBA ARM/Thumb store -> GBAStore8",
             "to": "GBASavedataWriteFlash for Flash-backed SRAM-region writes"},
            {"from": "GBASavedataWriteFlash",
             "to": "mapped currentBank bytes and dirty state; GBAFrameEnded later calls GBASavedataClean"},
            {"from": "GBASavedataClean -> VFile sync",
             "to": "host mapping/sync semantics; not physical power-loss durability"},
            {"from": "new process loads game-written .sav",
             "to": "FireRed LoadGameSave and controller-observed field recovery"},
        ],
        "runtime_observation_boundary": (
            "Native probe observes compiled ProgramFlashSectorAndVerify entry/return and per-sector "
            "GBASavedata mapped-byte/dirty-state effects. It does not instrument/count direct "
            "GBASavedataWriteFlash callback entries."
        ),
        "license_presence": {
            "pret/pokefirered": "No root LICENSE file at pinned commit",
            "pret/agbcc": "No root LICENSE file at pinned commit",
            "mgba-emu/mgba": "MPL-2.0 in pinned LICENSE file",
        },
        "per_file_dossiers": records,
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approval": False,
    }
    manifest_path = output / "source_path_closure.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    manifest["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (output / "source_path_closure.sha256").write_text(manifest["manifest_sha256"] + "\n")
    return manifest


def load_sources(roots):
    return {key: (roots[key[0]] / key[1]).read_bytes() for key in FILES}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--firered-source", required=True, type=Path)
    parser.add_argument("--agbcc-source", required=True, type=Path)
    parser.add_argument("--mgba-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    roots = {F: args.firered_source, A: args.agbcc_source, M: args.mgba_source}
    for repo in (F, A):
        if (roots[repo] / "LICENSE").exists():
            raise ValueError("Pinned root license presence changed: " + repo)
    data = load_sources(roots)
    validate_sources(data)
    line_refs = validate_callgraph(data)
    result = build_dossier(data, line_refs, args.output)
    print(json.dumps({
        "source_file_count": result["source_file_count"],
        "source_mutation_negative_controls": result["source_mutation_negative_controls"],
        "manifest_sha256": result["manifest_sha256"],
        "runtime_observation_boundary": result["runtime_observation_boundary"],
        "phase1_gate": result["phase1_gate"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
