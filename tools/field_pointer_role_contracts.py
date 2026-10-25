#!/usr/bin/env python3
"""FireRed field 32-bit operand pointer-role contracts, source and opcode pinned.

A 32-bit script word is NOT a universally relocatable resource identifier.
Source-backed typing distinguishes RAM byte read/write, native callback, field
script target, and virtual/rebased script addresses. These contracts are not
full path or memory lifetime proofs.
"""
import csv,gzip,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered");OUT=Path("audit-output")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
SHA="97b695ee2f6fca80a3b78f52f6a444f696fe5814"
# name -> role, 32-bit words read, required exact C source patterns
CONTRACTS={
 "ScrCmd_call":("SCRIPT_CODE_ADDRESS_CALL",1,("ScriptCall(ctx, scrptr)","(const u8 *)ScriptReadWord(ctx)")),
 "ScrCmd_goto":("SCRIPT_CODE_ADDRESS_JUMP",1,("ScriptJump(ctx, scrptr)","(const u8 *)ScriptReadWord(ctx)")),
 "ScrCmd_goto_if":("CONDITIONAL_SCRIPT_JUMP",1,("ScriptJump(ctx, scrptr)","(const u8 *)ScriptReadWord(ctx)")),
 "ScrCmd_call_if":("CONDITIONAL_SCRIPT_CALL",1,("ScriptCall(ctx, scrptr)","(const u8 *)ScriptReadWord(ctx)")),
 "ScrCmd_setvaddress":("SET_SCRIPT_REBASE_OFFSET",1,("sAddressOffset = addr2 - addr1","addr2 = ScriptReadWord(ctx)")),
 "ScrCmd_vgoto":("REBASED_SCRIPT_JUMP",1,("ScriptJump(ctx, scrptr - sAddressOffset)","(const u8 *)ScriptReadWord(ctx)")),
 "ScrCmd_vcall":("REBASED_SCRIPT_CALL",1,("ScriptCall(ctx, scrptr - sAddressOffset)","(const u8 *)ScriptReadWord(ctx)")),
 "ScrCmd_vgoto_if":("CONDITIONAL_REBASED_SCRIPT_JUMP",1,("ScriptJump(ctx, scrptr)","- sAddressOffset")),
 "ScrCmd_vcall_if":("CONDITIONAL_REBASED_SCRIPT_CALL",1,("ScriptCall(ctx, scrptr)","- sAddressOffset")),
 "ScrCmd_callnative":("DIRECT_NATIVE_VOID_FUNCTION_POINTER",1,("void (*func )(void)","func();")),
 "ScrCmd_gotonative":("NATIVE_BOOL_FUNCTION_POINTER_ASYNC",1,("bool8 (*func)(void)","SetupNativeScript(ctx, func)")),
 "ScrCmd_setptr":("WRITE_ONE_RAW_MEMORY_BYTE",1,("*(u8 *)ScriptReadWord(ctx) = value",)),
 "ScrCmd_setptrbyte":("WRITE_ONE_RAW_MEMORY_BYTE",1,("*(u8 *)ScriptReadWord(ctx) = ctx->data[index]",)),
 "ScrCmd_loadbytefromptr":("READ_ONE_RAW_MEMORY_BYTE",1,("*(const u8 *)ScriptReadWord(ctx)",)),
 "ScrCmd_copybyte":("READ_AND_WRITE_RAW_MEMORY_BYTE",2,("u8 * dest = (u8 *)ScriptReadWord(ctx)","*dest = *(const u8 *)ScriptReadWord(ctx)")),
 "ScrCmd_compare_local_to_ptr":("READ_ONE_RAW_MEMORY_BYTE_FOR_COMPARE",1,("*(const u8 *)ScriptReadWord(ctx)",)),
 "ScrCmd_compare_ptr_to_local":("READ_ONE_RAW_MEMORY_BYTE_FOR_COMPARE",1,("*(const u8 *)ScriptReadWord(ctx)",)),
 "ScrCmd_compare_ptr_to_value":("READ_ONE_RAW_MEMORY_BYTE_FOR_COMPARE",1,("*(const u8 *)ScriptReadWord(ctx)",)),
 "ScrCmd_compare_ptr_to_ptr":("READ_TWO_RAW_MEMORY_BYTES_FOR_COMPARE",2,("*(const u8 *)ScriptReadWord(ctx)",))
}
HEADERS=("opcode","opcode_hex","handler","role","pointer_words","source_path","source_sha",
 "start_line","end_line","source_section_sha256","required_evidence_tokens",
 "source_role_evidenced","compatibility_policy","path_complete_role_signoff")
def gitsha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def rows(name):
 with gzip.open(OUT/name,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Pinned FireRed source changed")
 data=(ROOT/"src/scrcmd.c").read_bytes()
 if gitsha(data)!=SHA:raise RuntimeError("Source Git blob differs")
 lines=data.decode("utf-8","surrogateescape").splitlines()
 indexed={r["handler"]:r for r in rows("script_opcode_semantic_obligations.csv.gz") if r["script_kind"]=="FIELD"}
 frommacro={int(r["opcode"]):r for r in rows("field_opcode_macro_vs_handler_alignment.csv.gz")}
 allroles=[]
 for name,(role,count,needles) in CONTRACTS.items():
  r=indexed.get(name)
  if not r:raise RuntimeError("No indexed source definition "+name)
  opcode=int(r["opcode"])
  aligned=frommacro.get(opcode)
  if not aligned or aligned["handler"]!=name:
   raise RuntimeError("Assembler-to-handler opcode mismatch "+name)
  a,b=int(r["definition_line"]),int(r["end_line"])
  section="\n".join(lines[a-1:b])
  if int(r["field_read_word_sites"])!=count or len(re.findall(r"\bScriptReadWord\s*\(",section))!=count:
   raise RuntimeError("Unexpected number of 32-bit pointer words "+name)
  for needle in needles:
   if needle not in section:raise RuntimeError("Source pointer role evidence changed "+name+" :: "+needle)
  role_policy=("DISALLOW_UNNEGOTIATED_EXTERNAL_HANDLE_AS_NATIVE_OR_RAM_POINTER"
    if role.startswith(("NATIVE","DIRECT_NATIVE","READ","WRITE"))
    else "TAGGED_SCRIPT_RESOURCE_ONLY_WITH_EXPLICIT_REBASE_AND_CONTEXT_VALIDATION")
  allroles.append({"opcode":opcode,"opcode_hex":hex(opcode),"handler":name,"role":role,
    "pointer_words":count,"source_path":"src/scrcmd.c","source_sha":SHA,
    "start_line":a,"end_line":b,"source_section_sha256":hashlib.sha256(
       section.encode("utf-8","surrogateescape")).hexdigest(),
    "required_evidence_tokens":";".join(needles),
    "source_role_evidenced":True,"compatibility_policy":role_policy,
    "path_complete_role_signoff":False})
 with gzip.open(OUT/"field_pointer_role_contracts.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=HEADERS);w.writeheader();w.writerows(allroles)
 policy_categories={}
 for p in allroles:policy_categories[p["role"]]=policy_categories.get(p["role"],0)+1
 report={"pinned_32bit_pointer_command_handlers":len(allroles),
  "source_verified_pointer_word_sites":sum(x["pointer_words"] for x in allroles),
  "pointer_roles":policy_categories,
  "byte_writes":sum(x["role"] in ("WRITE_ONE_RAW_MEMORY_BYTE","READ_AND_WRITE_RAW_MEMORY_BYTE") for x in allroles),
  "native_callbacks":sum(x["role"] in ("NATIVE_BOOL_FUNCTION_POINTER_ASYNC","DIRECT_NATIVE_VOID_FUNCTION_POINTER") for x in allroles),
  "script_control_and_virtual_address_commands":sum(x["role"] in (
    "SCRIPT_CODE_ADDRESS_CALL","SCRIPT_CODE_ADDRESS_JUMP","CONDITIONAL_SCRIPT_JUMP",
    "CONDITIONAL_SCRIPT_CALL","SET_SCRIPT_REBASE_OFFSET",
    "REBASED_SCRIPT_JUMP","REBASED_SCRIPT_CALL",
    "CONDITIONAL_REBASED_SCRIPT_JUMP","CONDITIONAL_REBASED_SCRIPT_CALL") for x in allroles),
  "source_level_semantic_roles_evidenced":len(allroles),
  "runtime_pointer_validity_or_lifetime_verified":False,
  "independent_file_semantic_approvals":0,"phase1_mapping_complete":False,
  "warning":"These 19 pinned handler roles are supported by specific source code; their complete dynamic dataflow and safe relocation are not proved."}
 (OUT/"field_pointer_role_summary.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in report.items() if k!="pointer_roles"},indent=2))
 if len(allroles)!=19:raise RuntimeError("Incomplete pointer role catalog")
if __name__=="__main__":main()
