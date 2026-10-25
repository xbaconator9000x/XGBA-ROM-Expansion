#!/usr/bin/env python3
"""Prove pinned FireRed save sector and mGBA savedata storage constraints.

This is save-data *format/lifecycle* mapping, not emulation, extension save
implementation, cryptographic protection or whole-file semantic approval.
"""
import csv,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path("upstream");OUT=Path("audit-output")
PINS={"pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
 "mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b"}
BLOBS={
 ("pret/pokefirered","include/save.h"):"87fb9b615b434b58823d15688056695acda9feab",
 ("pret/pokefirered","src/save.c"):"36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
 ("pret/pokefirered","src/load_save.c"):"8b723dd044c6024b3671bb890b25b56a53f99ec5",
 ("mgba-emu/mgba","src/gba/savedata.c"):"fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
 ("mgba-emu/mgba","include/mgba/internal/gba/memory.h"):"0aad912613e726560d06bbdbf6061986e69e5842"}
FIELDS=["contract_id","repository","revision","file","source_blob","line",
 "source_expression","observed_semantics","extension_requirement","verification","runtime_test"]
CHECKS=[
 ("XS25-SAVE-DATA-BYTES","pret/pokefirered","include/save.h","#define SECTOR_DATA_SIZE 3968",
  "Native save sector stores 3968 useful bytes, followed by a footer.",
  "External state must never occupy native sector footer or overrun native sector data."),
 ("XS25-SAVE-FOOTER-BYTES","pret/pokefirered","include/save.h","#define SECTOR_FOOTER_SIZE 128",
  "Native save-sector footer uses 128 bytes of 4096-byte flash sector.",
  "Preserve original footer layout, ID, checksum, signature and save counter."),
 ("XS25-SAVE-TWO-ROTATING-SLOTS","pret/pokefirered","include/save.h","#define NUM_SAVE_SLOTS 2",
  "Vanilla FireRed saves have two rotating logical slots.",
  "External save association must follow chosen validated slot/counter, not overwrite the other."),
 ("XS25-SAVE-14-SECTORS-PER-SLOT","pret/pokefirered","include/save.h","#define NUM_SECTORS_PER_SLOT         14",
  "Each logical save slot consists of 14 sectors.",
  "Do not reassign any 14 core sector IDs as XGBA data."),
 ("XS25-SAVE-32-FLASH-SECTORS","pret/pokefirered","include/save.h","#define SECTORS_COUNT                32",
  "All 32 sectors are assigned: 28 core save sectors and four dedicated special sectors.",
  "Native 128 KiB flash cannot be repurposed as unlimited extension storage."),
 ("XS25-SAVE-HOF-AND-TOWER","pret/pokefirered","include/save.h","#define SECTOR_ID_TRAINER_TOWER_2    31",
  "Highest 4 sectors are reserved for Hall of Fame/Trainer Tower storage.",
  "Preserve special sector identity, do not assume space after the main save slot."),
 ("XS25-SAVE-METADATA-LAYOUT","pret/pokefirered","include/save.h","u8 unused[SECTOR_FOOTER_SIZE - 12];",
  "SaveSector footer reserves exact positions for 12 bytes of sector metadata.",
  "A new save version must preserve legacy sector signature/counter/checksum layout."),
 ("XS25-SAVE-SLOT-ROTATION","pret/pokefirered","src/save.c","sectorNum += NUM_SECTORS_PER_SLOT * (gSaveCounter % NUM_SAVE_SLOTS);",
  "Sector address selection follows rolling save counter and alternating slot.",
  "Extended state should be transactionally associated with the commit counter."),
 ("XS25-SAVE-WRITE-CHECKSUM","pret/pokefirered","src/save.c","gSaveDataBufferPtr->checksum = CalculateChecksum(data, size);",
  "Save write adds checksum over actual sector data size.",
  "Do not change vanilla checksum algorithm or payload length."),
 ("XS25-SAVE-READ-SIGNATURE","pret/pokefirered","src/save.c","gSaveDataBufferPtr->signature == SECTOR_SIGNATURE && gSaveDataBufferPtr->checksum == checksum",
  "Save read requires both native signature and checksum equality.",
  "Reject corrupted auxiliary state separately, never weaken native save validation."),
 ("XS25-SAVE-VALIDATE-BOTH-SLOTS","pret/pokefirered","src/save.c","if (slot1Status == SAVE_STATUS_OK && slot2Status == SAVE_STATUS_OK)",
  "Reader evaluates both slot statuses before choosing latest counter.",
  "Extension state must handle fallback to an older native slot without mismatching data."),
 ("XS25-SAVE-BLOCK-RANDOM-POINTERS","pret/pokefirered","src/load_save.c","gSaveBlock2Ptr = (void *)(&gSaveBlock2) + offset;",
  "SaveBlock pointers are intentionally shifted by randomized offset.",
  "Never persist host pointers or raw IWRAM addresses in external resource metadata."),
 ("XS25-SAVE-ENCRYPTION-ROTATION","pret/pokefirered","src/load_save.c","ApplyNewEncryptionKeyToAllEncryptedData(encryptionKey);",
  "SaveBlock relocation updates encryption of native money/item/stat fields.",
  "External save payload must use a different stable versioned keyed representation."),
 ("XS25-MGBA-FLASH128K","mgba-emu/mgba","include/mgba/internal/gba/memory.h","GBA_SIZE_FLASH1M = 0x00020000,",
  "Emulated FLASH1M capacity is exactly 128 KiB.",
  "Native flash file size is bounded independently of external save resources."),
 ("XS25-MGBA-FLASH64K","mgba-emu/mgba","include/mgba/internal/gba/memory.h","GBA_SIZE_FLASH512 = 0x00010000,",
  "mGBA separately supports 64 KiB FLASH512 mode.",
  "Do not silently reinterpret cartridge save-type detection when XGBA is enabled."),
 ("XS25-MGBA-BACKEND-SIZE","mgba-emu/mgba","src/gba/savedata.c","return GBA_SIZE_FLASH1M;",
  "mGBA selected savedata type controls the exact save file byte length.",
  "Keep native save type and size separate from versioned sidecar format."),
 ("XS25-MGBA-SAVE-COPY","mgba-emu/mgba","src/gba/savedata.c","return in->read(in, savedata->data, size) == size;",
  "Savedata import expects exactly the selected native byte count.",
  "Do not append extension bytes to vanilla savestates or flash images."),
]
def sha1blob(x):return hashlib.sha1(f"blob {len(x)}\0".encode()+x).hexdigest()
def main():
 for repo,pin in PINS.items():
  if subprocess.check_output(["git","-C",str(ROOT/repo.split("/")[-1]),"rev-parse","HEAD"],text=True).strip()!=pin:
   raise RuntimeError("Pinned source changed "+repo)
 records=[];cache={}
 for cid,repo,path,needle,observed,required in CHECKS:
  key=(repo,path)
  if key not in cache:
   data=(ROOT/repo.split("/")[-1]/path).read_bytes()
   if sha1blob(data)!=BLOBS[key]:raise RuntimeError("Unpinned source content "+repr(key))
   cache[key]=data.decode("utf-8","surrogateescape")
  text=cache[key]
  if needle not in text:raise RuntimeError("Missing exact source contract "+cid)
  line=text.count("\n",0,text.index(needle))+1
  records.append({"contract_id":cid,"repository":repo,"revision":PINS[repo],
   "file":path,"source_blob":BLOBS[key],"line":line,
   "source_expression":needle,"observed_semantics":observed,
   "extension_requirement":required,
   "verification":"EXACT_SOURCE_ANCHOR_IN_PINNED_GIT_BLOB",
   "runtime_test":"NOT_RUN"})
 if 3968+128!=4096 or 2*14+4!=32 or 32*4096!=0x20000:
  raise RuntimeError("Flash sector arithmetic no longer matches contract")
 OUT.mkdir(exist_ok=True)
 with (OUT/"save_sector_source_contracts.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(records)
 summary={"source_contracts_passed":len(records),"tracked_files_verified":len(cache),
 "native_sector_bytes":4096,"native_data_bytes_per_sector":3968,
 "native_footer_bytes_per_sector":128,
 "native_save_slots":2,"sectors_per_main_slot":14,
 "special_sectors":4,"total_flash_sectors":32,
 "occupied_native_flash_bytes":131072,
 "native_256KiB_flash_extension_available":False,
 "whole_file_semantic_signoffs":0,"phase1_mapping_complete":False,
 "limitations":["This validates pinned save format and read/write source structure, not runtime power-loss atomicity.",
  "An external save sidecar needs a separately designed commit/identity protocol.",
  "Legacy save sector ID bounds under corrupted data need runtime fuzz testing.",
  "No XGBA savedata extension has been implemented."]}
 (OUT/"save_sector_source_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":
 try:main()
 except Exception as e:print("SAVE CONTRACT ERROR:",repr(e),file=sys.stderr);sys.exit(2)
