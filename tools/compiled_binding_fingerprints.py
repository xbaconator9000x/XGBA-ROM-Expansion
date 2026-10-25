#!/usr/bin/env python3
"""Generate versioned source+ELF-binding fingerprints for two pinned FireRed modes.

This is a machine-readable *preflight* compatibility contract for future
plugins, not an address resolver for arbitrary forks and not a ROM patcher.
Refuse if source revision, build SHA, ABI widths or any symbol address changes.
"""
import copy,hashlib,json,sys
from pathlib import Path
SRC=Path("firered-variant-evidence/firered_variants_abi_summary.json")
OUT=Path("firered-variant-evidence/firered_variant_binding_fingerprints.json")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
CRITICAL={
 "gScriptCmdTable":{"segment":"ROM","role":"field_script_opcode_table","element_bytes":4},
 "gScriptCmdTableEnd":{"segment":"ROM","role":"field_script_table_end_sentinel","element_bytes":4},
 "gBattleScriptingCommandsTable":{"segment":"ROM","role":"battle_script_opcode_table","element_bytes":4},
 "gMonFrontPicTable":{"segment":"ROM","role":"front_sprite_entries","element_bytes":8},
 "gMonBackPicTable":{"segment":"ROM","role":"back_sprite_entries","element_bytes":8},
 "gSongTable":{"segment":"ROM","role":"music_header_descriptor_table","element_bytes":None},
 "gMPlayTable":{"segment":"ROM","role":"music_player_info_table","element_bytes":None},
 "gMapGroups":{"segment":"ROM","role":"map_group_pointer_table","element_bytes":None},
 "gMapLayouts":{"segment":"ROM","role":"map_layout_pointer_table","element_bytes":None},
 "gSaveBlock1Ptr":{"segment":"IWRAM","role":"dynamic_save_block_1_pointer","element_bytes":4},
 "gSaveBlock2Ptr":{"segment":"IWRAM","role":"dynamic_save_block_2_pointer","element_bytes":4}}
def stable_hash(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
def preflight(p,expected):
 if p.get("fingerprint")!=expected["fingerprint"]:return False,"binary ABI fingerprint mismatch"
 if p.get("source_revision")!=PIN:return False,"source revision mismatch"
 if p.get("variant")!=expected["variant"]:return False,"compiler variant mismatch"
 if p.get("elf_sha256")!=expected["elf_sha256"]:return False,"ELF identity mismatch"
 if set(p.get("bindings",{}))!=set(CRITICAL):return False,"symbol coverage mismatch"
 canonical={k:p[k] for k in ("source_revision","variant","elf_sha256","bindings")}
 if stable_hash(canonical)!=p["fingerprint"]:return False,"symbol binding modified"
 for n,e in p["bindings"].items():
  if e["segment"]!=CRITICAL[n]["segment"]:return False,"segment role changed: "+n
  address=int(e["address_hex"],16)
  if e["segment"]=="ROM" and not 0x08000000<=address<0x0A000000:
   return False,"ROM pointer out of native bounds: "+n
  if e["segment"]=="IWRAM" and not 0x03000000<=address<0x03008000:
   return False,"save pointer out of native IWRAM: "+n
 return True,"source + compiled binary ABI verified"
def main():
 src=json.loads(SRC.read_text())
 if src["pinned_commit"]!=PIN or src["compiled_ABI_check_count_passed"]!=12:
  raise RuntimeError("Pinned two-variant ABI comparison must pass first")
 output={"contract_version":"XGBA/Phase1/CompiledABIFingerprint/1",
  "pinned_revision":PIN,"supported_compiled_baselines":{},
  "verification":"SOURCE_AND_ELF_SPECIFIC_NOT_AUTO_COMPATIBLE_WITH_FORKS",
  "mapping_complete":False}
 variants=src["variants"]
 if set(variants)!={"original_agbcc","modern_gcc"}:raise RuntimeError("Unexpected binary variants")
 for name,build in variants.items():
  bindings={}
  for symbol,role in CRITICAL.items():
   s=build["symbols"][symbol]
   e={"address_hex":hex(s["address"]),"symbol_size":s["bytes"],
      "segment":role["segment"],"semantic_role":role["role"]}
   if role["element_bytes"]:e["element_bytes"]=role["element_bytes"]
   bindings[symbol]=e
  base={"source_revision":PIN,"variant":name,
        "elf_sha256":build["elf_sha256"],"bindings":bindings}
  record=copy.deepcopy(base)
  record["fingerprint"]=stable_hash(base)
  output["supported_compiled_baselines"][name]=record
  result,reason=preflight(record,record)
  if not result:raise RuntimeError("Valid fingerprint not accepted: "+reason)
  negatives=[
   ("wrong_source_revision",lambda c:c.update(source_revision="0000000000000000000000000000000000000000")),
   ("wrong_binary_sha",lambda c:c.update(elf_sha256="0"*64)),
   ("wrong_compiler_mode",lambda c:c.update(variant="nonexistent")),
   ("different_rom_symbol_location",lambda c:c["bindings"]["gScriptCmdTable"].update(address_hex="0x09000000")),
   ("different_battle_table_width",lambda c:c["bindings"]["gBattleScriptingCommandsTable"].update(symbol_size=123)),
   ("unknown_extra_symbol",lambda c:c["bindings"].update(extra_symbol={}))]
  for label,mut in negatives:
   copy=globals()["copy"].deepcopy(record)
   mut(copy)
   ok,reason=preflight(copy,record)
   if ok:raise RuntimeError("Preflight accepted invalid adapter fixture: "+label)
  output["supported_compiled_baselines"][name]["negative_preflight_fixtures_rejected"]=len(negatives)
 # Check that source-identical compiler variants cannot accidentally be mistaken for same ABI
 if output["supported_compiled_baselines"]["original_agbcc"]["fingerprint"]==output["supported_compiled_baselines"]["modern_gcc"]["fingerprint"]:
  raise RuntimeError("Distinct compiled variants collided in fingerprint")
 output["negative_preflight_tests_passed"]=12
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"compiled_variants":len(variants),"critical_symbols_per_variant":len(CRITICAL),
                   "negative_tests_passed":12,"whole_file_signoffs":0},indent=2))
if __name__=="__main__":
 try:main()
 except Exception as e:print("FINGERPRINT CHECK FAILED",repr(e),file=sys.stderr);sys.exit(2)
