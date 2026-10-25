#!/usr/bin/env python3
"""Source-backed contract checks against pinned upstream bytes.
Assertions are exact invariants, not semantic signoff or execution tests."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
PINS={
"pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
"mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b",
"huderlem/porymap":"26b919d7ff4b54152de010abd5bf344af2ebe116",
"huderlem/poryscript":"c32481161c767b25a3425fa9f1f8729927ff3d55"}
CHECKS=[
("MGBA_CRC_WARNING_NONFATAL","mgba-emu/mgba","src/gba/serialize.c",
 "a307a51e751f412c64a7378323c56758304ebe85",
 r"if \(ucheck != gba->romCrc32\)\s*\{\s*mLOG\([^;]+;\s*\}"),
("MGBA_REMAP_BEFORE_REGION_RESET","mgba-emu/mgba","src/gba/serialize.c",
 "a307a51e751f412c64a7378323c56758304ebe85",
 r"GBAUnlCartDeserialize\(gba, state\);\s*gba->memory\.activeRegion = -1;\s*gba->cpu->memory\.setActiveRegion"),
("FIRERED_RAW_BYTECODE_DISPATCH","pret/pokefirered","src/script.c",
 "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
 r"cmdCode = \*\(ctx->scriptPtr\);\s*ctx->scriptPtr\+\+;"),
("FIRERED_RAW_SCRIPT_WORD","pret/pokefirered","src/script.c",
 "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
 r"u32 ScriptReadWord\([^)]*\)\s*\{[^}]*ctx->scriptPtr\+\+[^}]*\}"),
("FIRERED_SAVEBLOCK_RANDOM_OFFSET","pret/pokefirered","src/load_save.c",
 "8b723dd044c6024b3671bb890b25b56a53f99ec5",
 r"offset = \(Random\(\)\)[^;]*;\s*gSaveBlock2Ptr"),
("FIRERED_SAVE_ENCRYPTION_ROTATION","pret/pokefirered","src/load_save.c",
 "8b723dd044c6024b3671bb890b25b56a53f99ec5",
 r"ApplyNewEncryptionKeyToAllEncryptedData\(encryptionKey\);"),
("MGBA_ARM_DIRECT_PREFETCH","mgba-emu/mgba","src/arm/arm.c",
 "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
 r"LOAD_32\(cpu->prefetch\[1\], cpu->gprs\[ARM_PC\] & cpu->memory\.activeMask, cpu->memory\.activeRegion\);"),
("MGBA_THUMB_DIRECT_PREFETCH","mgba-emu/mgba","src/arm/arm.c",
 "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
 r"LOAD_16\(cpu->prefetch\[1\], cpu->gprs\[ARM_PC\] & cpu->memory\.activeMask, cpu->memory\.activeRegion\);"),
("MGBA_REGION_ROM_DIRECT_BASE","mgba-emu/mgba","src/gba/memory.c",
 "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
 r"cpu->memory\.activeRegion = memory->rom;\s*cpu->memory\.activeMask = memory->romMask;"),
("MGBA_ROM2_EEPROM_PRIORITY","mgba-emu/mgba","src/gba/memory.c",
 "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
 r"case GBA_REGION_ROM2_EX:\s*wait = .*?if \(memory->savedata\.type == GBA_SAVEDATA_EEPROM"),
("MGBA_DMA_EEPROM_SPECIAL_READ","mgba-emu/mgba","src/gba/dma.c",
 "da2a800ba48cb32d6e10e42c3b3527ef406bad22",
 r"sourceRegion == GBA_REGION_ROM2_EX && .*?GBASavedataReadEEPROM"),
("MGBA_DMA_EEPROM_SPECIAL_WRITE","mgba-emu/mgba","src/gba/dma.c",
 "da2a800ba48cb32d6e10e42c3b3527ef406bad22",
 r"destRegion == GBA_REGION_ROM2_EX.*?GBASavedataWriteEEPROM"),
("MGBA_MATRIX_DIRECT_BACKING_COPY","mgba-emu/mgba","src/gba/cart/matrix.c",
 "9ccbe883235b98bcf56cd609015e7b4003aa832c",
 r"gba->romVf->seek\(.*?gba->romVf->read\("),
("MGBA_MATRIX_SAVESTATE_MAP","mgba-emu/mgba","src/gba/cart/matrix.c",
 "9ccbe883235b98bcf56cd609015e7b4003aa832c",
 r"void GBAMatrixDeserialize\(.*?gba->memory\.matrix\.mappings\[i\].*?_remapMatrix\(gba\);"),
("FIRERED_SCRIPT_NATIVE_CALLBACK","pret/pokefirered","src/scrcmd.c",
 "97b695ee2f6fca80a3b78f52f6a444f696fe5814",
 r"ScrCmd_callnative\(.*?ScriptReadWord\(ctx\).*?func\(\);"),
("FIRERED_SCRIPT_RAW_POINTER_STORE","pret/pokefirered","src/scrcmd.c",
 "97b695ee2f6fca80a3b78f52f6a444f696fe5814",
 r"ScrCmd_setptr\(.*?\*\(u8 \*\)ScriptReadWord\(ctx\) = value;"),
("FIRERED_FIELD_MAP_MUTABLE_BACKUP","pret/pokefirered","src/fieldmap.c",
 "41567772299000ba5855419e5c39ad9373a34c20",
 r"VMap\.map = gBackupMapData;\s*VMap\.Xsize = mapLayout->width"),
("PORYMAP_MAP_LAYOUT_SEPARATE","huderlem/porymap","src/project.cpp",
 "d43b0949303433111d4478ad76117c2b3445dd13",
 r"if \(!loadMapData\(map\)\).*?if \(!loadLayout\(map->layoutId\(\)\)\)"),
("PORYMAP_TYPED_EVENT_GROUPS","huderlem/porymap","src/project.cpp",
 "d43b0949303433111d4478ad76117c2b3445dd13",
 r"Event::Group::Object.*?Event::Group::Warp.*?Event::Group::Coord.*?Event::Group::Bg"),
("PORYMAP_METATILE_COLLISION_PRESERVED","huderlem/porymap","src/core/maplayout.cpp",
 "44616ab6c9c3ea9b04eff011586b7ec29183588f",
 r"setBlock\(x, y, Block\(metatileId, block\.collision\(\), block\.elevation\(\)\)"),
("PORYSCRIPT_MAP_TERMINATORS","huderlem/poryscript","emitter/emitter.go",
 "d35843ef29929ead47351646d7a33dd5c692b850",
 r"map_script.*?\\t\.byte 0.*?map_script_2.*?\\t\.2byte 0")
]
def run(root):
 findings=[]
 for label,repo,path,sha,pattern in CHECKS:
  folder=root/repo.split("/")[-1]
  commit=subprocess.check_output(["git","-C",str(folder),"rev-parse","HEAD"],text=True).strip()
  if commit!=PINS[repo]:raise RuntimeError("Wrong pinned commit for "+repo)
  data=(folder/path).read_bytes()
  blob=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
  if blob!=sha:raise RuntimeError("Pinned blob mismatch "+repo+"/"+path)
  text=data.decode("utf-8","surrogateescape")
  match=re.search(pattern,text,re.S)
  if not match:raise RuntimeError("Source invariant not found: "+label)
  start=text.count("\n",0,match.start())+1
  end=text.count("\n",0,match.end())+1
  findings.append({"contract":label,"repo":repo,"commit":commit,"path":path,
                   "git_blob_sha":sha,"lines":[start,end],"source_check":"PASS",
                   "runtime_check":"NOT_RUN","whole_file_semantic_signoff":False})
 result={"source_checks":len(findings),"source_checks_passed":len(findings),
         "runtime_tests_run":0,"phase1_mapping_complete":False,"findings":findings}
 out=Path("audit-output/source_contract_assertions.json")
 out.parent.mkdir(exist_ok=True)
 out.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"passed":len(findings),"mapping_complete":False}))
if __name__=="__main__":
 try:run(Path(sys.argv[1] if len(sys.argv)>1 else "upstream"))
 except Exception as e:print("CONTRACT CHECK FAILED:",e,file=sys.stderr);sys.exit(2)
