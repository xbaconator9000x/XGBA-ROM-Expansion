#!/usr/bin/env python3
"""Phase 1: pinned cross-repository FireRed/mGBA Flash identification witness.
No emulation, Phase 2 change, or independent semantic approval.
"""
import hashlib
import json
import re
import urllib.request

PINS = {
    "pret/pokefirered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "mgba-emu/mgba": "fd9dc5c2cbf234365068855851107e762fc6211b",
}
BLOBS = {
    ("pret/pokefirered", "src/agb_flash_1m.c"): "e249fab9a350f3263e7df5f20ff301a6d008e3db",
    ("pret/pokefirered", "src/agb_flash_le.c"): "39d956e2778af564cf187ea732a019e46479ac12",
    ("pret/pokefirered", "src/agb_flash_mx.c"): "b4f710f36449c46946294d0df3d61d493d5c0d1f",
    ("pret/pokefirered", "src/load_save.c"): "8b723dd044c6024b3671bb890b25b56a53f99ec5",
    ("pret/pokefirered", "include/save.h"): "87fb9b615b434b58823d15688056695acda9feab",
    ("mgba-emu/mgba", "src/gba/overrides.c"): "566968162b29c90167199ef43f3d7a99248798e8",
    ("mgba-emu/mgba", "src/gba/core.c"): "6bfc518bb8899205c07d1d0fc091a287cb42f874",
    ("mgba-emu/mgba", "src/gba/memory.c"): "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
    ("mgba-emu/mgba", "src/gba/savedata.c"): "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
    ("mgba-emu/mgba", "include/mgba/internal/gba/savedata.h"): "6227be25e8c9d2c1cc14c06ded34389b96138577",
    ("mgba-emu/mgba", "include/mgba/internal/gba/memory.h"): "0aad912613e726560d06bbdbf6061986e69e5842",
}
F = "pret/pokefirered"
M = "mgba-emu/mgba"
ANCHORS = {
    (F, "src/load_save.c"): {48:"if (!IdentifyFlash())",50:"gFlashMemoryPresent = TRUE",55:"gFlashMemoryPresent = FALSE"},
    (F, "src/agb_flash_1m.c"): {8:"&MX29L010",9:"&LE26FV10N1TS",10:"&DefaultFlash",21:"flashId = ReadFlashId();",26:"result = 1;",32:"if (flashId == (*setupInfo)->type.ids.joined)",34:"result = 0;",49:"return result;"},
    (F, "src/agb_flash_le.c"): {12:"const struct FlashSetupInfo LE26FV10N1TS",20:"131072",22:"4096",24:"32",29:"0x62, 0x13"},
    (F, "include/save.h"): {8:"#define SECTOR_DATA_SIZE 3968",9:"#define SECTOR_FOOTER_SIZE 128",11:"#define SECTOR_SIZE (SECTOR_DATA_SIZE + SECTOR_FOOTER_SIZE)",24:"#define NUM_SECTORS_PER_SLOT",29:"#define SECTOR_ID_TRAINER_TOWER_2",30:"#define SECTORS_COUNT"},
    (M, "src/gba/overrides.c"): {133:'"BPRJ", GBA_SAVEDATA_FLASH1M',134:'"BPRE", GBA_SAVEDATA_FLASH1M',135:'"BPRP", GBA_SAVEDATA_FLASH1M',422:"bool isPokemon = false;",423:'"pokemon red version"',434:"if (isPokemon && !isKnownPokemon)",436:"override.savetype = GBA_SAVEDATA_FLASH1M;",440:"GBAOverrideFindConfig",442:"GBAOverrideFind(overrides, &override)",443:"GBAOverrideApply(gba, &override)"},
    (M, "src/gba/core.c"): {787:"if (gbacore->hasOverride)",788:"GBAOverrideApply(gba, &gbacore->override)",790:"GBAOverrideApplyDefaults(gba, gbacore->overrides)"},
    (M, "src/gba/memory.c"): {1064:"GBA_SAVEDATA_AUTODETECT",1065:"address == SAVEDATA_FLASH_BASE",1067:"GBASavedataInitFlash(&memory->savedata)"},
    (M, "src/gba/savedata.c"): {267:"void GBASavedataInitFlash",268:"GBA_SAVEDATA_AUTODETECT",269:"GBA_SAVEDATA_FLASH512",377:"GBASavedataReadFlash",379:"GBA_SAVEDATA_FLASH512",381:"FLASH_PANASONIC_MN63F805MNP",383:"GBA_SAVEDATA_FLASH1M",385:"FLASH_SANYO_LE26FV10N1TS",759:"void _flashSwitchBank",761:"bank > 0 && savedata->type == GBA_SAVEDATA_FLASH512",763:"GBA_SAVEDATA_FLASH1M",776:"bank << 16"},
    (M, "include/mgba/internal/gba/savedata.h"): {52:"FLASH_PANASONIC_MN63F805MNP = 0x1B32",53:"FLASH_SANYO_LE26FV10N1TS = 0x1362"},
    (M, "include/mgba/internal/gba/memory.h"): {72:"GBA_SIZE_FLASH512 = 0x00010000",73:"GBA_SIZE_FLASH1M = 0x00020000"},
}

def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def validate_sources(data):
    if set(data) != set(BLOBS):
        raise ValueError("Incomplete or extra source set")
    for key, expected in BLOBS.items():
        raw = data[key]
        if blob_sha(raw) != expected:
            raise ValueError("Pinned Git blob mismatch: " + str(key))
    return True

def contract(data):
    for key, anchors in ANCHORS.items():
        lines = data[key].decode("utf-8").splitlines()
        for n, phrase in anchors.items():
            if n > len(lines) or phrase not in lines[n-1]:
                raise ValueError("Cross-repo anchor drift: " + str((key,n,phrase)))
    le = data[(F,"src/agb_flash_le.c")].decode()
    em = data[(M,"include/mgba/internal/gba/savedata.h")].decode()
    le_match = re.search(r"\{ \{ 0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+) \} \} // ID", le)
    sanyo = re.search(r"FLASH_SANYO_LE26FV10N1TS\s*=\s*(0x[0-9A-Fa-f]+)", em)
    panasonic = re.search(r"FLASH_PANASONIC_MN63F805MNP\s*=\s*(0x[0-9A-Fa-f]+)", em)
    if not all((le_match,sanyo,panasonic)):
        raise ValueError("Chip ID extraction failed")
    joined = int(le_match[1],16) | (int(le_match[2],16)<<8)
    if joined != int(sanyo[1],16) or joined == int(panasonic[1],16):
        raise ValueError("Flash ID compatibility mismatch")
    # A contract for expected paths, not a claim of real emulator execution.
    return {"matched_1m_chip_id":hex(joined),
            "autodetected_512k_id":hex(int(panasonic[1],16)),
            "flash_1m_bytes":131072,"sector_bytes":4096,
            "sectors":32,"save_slots":2,"sectors_per_slot":14,
            "conditional_case_known_BPRE":"forced_1M_via_override_table",
            "conditional_case_unknown_code_marker_preserved":"forced_1M_via_hack_heuristic",
            "conditional_case_unknown_code_marker_absent_no_manual_override":"autodetect_first_flash_command_512K_then_unrecognized_ID",
            "unproven":["actual ROM header contents","override configuration and call order in a running emulator",
                        "save-file behavior and timing","other emulators","independent review"]}

def negative_controls(data):
    count=0
    def rejected(mod):
        nonlocal count
        try:contract(mod)
        except ValueError:count+=1
        else:raise AssertionError("Mutated source contract accepted")
    for key,old,new in [
        ((F,"src/agb_flash_le.c"),b"0x62, 0x13",b"0x62, 0x12"),
        ((M,"src/gba/overrides.c"),b'"BPRE", GBA_SAVEDATA_FLASH1M',b'"BPRE", GBA_SAVEDATA_FLASH512'),
        ((M,"src/gba/overrides.c"),b'"pokemon red version"',b'"not pokemon red ver"'),
        ((M,"src/gba/savedata.c"),b"savedata->type = GBA_SAVEDATA_FLASH512;",b"savedata->type = GBA_SAVEDATA_FLASH1M;"),
        ((F,"src/load_save.c"),b"gFlashMemoryPresent = FALSE;",b"gFlashMemoryPresent = TRUE;"),
        ((M,"src/gba/memory.c"),b"GBASavedataInitFlash(&memory->savedata);",b"GBASavedataInitSRAM(&memory->savedata);")
    ]:
        if old not in data[key]:raise AssertionError("Negative fixture not anchored")
        mod=dict(data);mod[key]=data[key].replace(old,new,1);rejected(mod)
    corrupt=dict(data);key=(F,"include/save.h");corrupt[key]+=b"\n"
    try:validate_sources(corrupt)
    except ValueError:count+=1
    else:raise AssertionError("Altered blob accepted")
    if count!=7:raise AssertionError("Incomplete negative controls")
    return count

def fetch(repo,path):
    url="https://raw.githubusercontent.com/"+repo+"/"+PINS[repo]+"/"+path
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-cross-repo-contract"}),timeout=30) as response:
        return response.read()

def main():
    data={key:fetch(*key) for key in sorted(BLOBS)}
    validate_sources(data)
    result=contract(data)
    result.update({"schema":"xgba-phase1-cross-repo-flash-contract-v1",
                   "pinned_blob_count":len(data),"negative_controls":negative_controls(data),
                   "independently_approved":0,"prepared_register_baseline":113,
                   "inventory":14834,"gate":"FAIL_INCOMPLETE"})
    print(json.dumps(result,sort_keys=True,indent=2))

if __name__=="__main__":
    main()
