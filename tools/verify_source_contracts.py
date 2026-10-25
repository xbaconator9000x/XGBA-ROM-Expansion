#!/usr/bin/env python3
"""Source-backed contract checks against pinned upstream bytes.
Assertions are exact invariants, not semantic signoff or execution tests."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
PINS={
"pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
"mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b",
"huderlem/porymap":"26b919d7ff4b54152de010abd5bf344af2ebe116",
"huderlem/poryscript":"c32481161c767b25a3425fa9f1f8729927ff3d55",
"pret/agbcc":"da598c1d918402c42c0c0d7128ba14567f3175e9"}
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
("PORYSCRIPT_MAP_TERMINATORS","huderlem/poryscript","emitter/emitter.go",
 "d35843ef29929ead47351646d7a33dd5c692b850",
 r"map_script.*?\\t\.byte 0.*?map_script_2.*?\\t\.2byte 0"),
("FIRERED_CLASSIC_LINKER_32M","pret/pokefirered","ld_script.ld",
 "9a4b45031e93c1e1da8186d8c697332710526048",
 r"ROM\s+\(rx\)\s*:\s*ORIGIN = 0x8000000, LENGTH = 32M"),
("FIRERED_MODERN_LINKER_32M","pret/pokefirered","ld_script_modern.ld",
 "e930243522bd21da40cc1a05de9a42b8ad409b46",
 r"ROM\s+\(rx\)\s*:\s*ORIGIN = 0x8000000, LENGTH = 32M"),
("FIRERED_OBJCOPY_FIXED_PAD_ABSOLUTE","pret/pokefirered","Makefile",
 "8b454dbd18eb0069fa5851d788697190890a5b37",
 r"\$\(OBJCOPY\) -O binary --gap-fill 0xFF --pad-to 0x9000000"),
("AGBCC_ARM_INTERWORK_MULTILIB","pret/agbcc","gcc_arm/config/arm/t-arm-elf",
 "b57eeca9805d5aeb0ba20e08948758cb27da82fd",
 r"MULTILIB_OPTIONS\s*=.*?mlittle-endian.*?mthumb-interwork")
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
