#!/usr/bin/env python3
"""FireRed field and battle bytecode dispatch ABI, source backed (not emulator tests).

This closes the function-pointer dispatch gap in regex/AST call graphs: a field
assembler table and a distinct C battle handler table. Each opcode is an indexed
function pointer. Handler operand analysis remains conservative, not compile proof.
"""
import collections,csv,gzip,hashlib,json,re,subprocess
from pathlib import Path
REPO="pret/pokefirered";PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
ROOT=Path("upstream/pokefirered");OUT=Path("audit-output")
EXPECTED={
 "data/script_cmd_table.inc":"c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1",
 "src/script.c":"d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
 "src/scrcmd.c":"97b695ee2f6fca80a3b78f52f6a444f696fe5814",
 "src/battle_script_commands.c":"67f90a37044db87091b2174f78fe1e31ad2ef10d",
 "src/battle_util.c":"bb66a0144b6144a72e1d9b22321c541e22302f7e"}
FIELDS=["repo","dispatch_table","dispatch_table_path","dispatch_table_sha",
 "dispatch_site_path","dispatch_site_sha","opcode","opcode_hex","handler",
 "handler_path","handler_sha","table_line","handler_definition_line",
 "word_operand_reads","halfword_operand_reads","byte_operand_reads",
 "native_pointer_role_candidate","raw_memory_pointer_role_candidate",
 "control_flow_pointer_role_candidate","handler_classification_status"]
def gitsha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def source(path):
 row=EXPECTED[path];data=(ROOT/path).read_bytes()
 if gitsha(data)!=row:
  data=subprocess.check_output(["git","-C",str(ROOT),"cat-file","blob",row])
 if gitsha(data)!=row:raise RuntimeError("Pinned source mismatch "+path)
 return data.decode("utf-8","surrogateescape").splitlines()
def functions(lines,prefix):
 result={}
 for i,line in enumerate(lines):
  m=re.match(r"^\s*(?:(?:static|inline|extern|const)\s+)*(?:void|bool8|bool|u8|u16|u32|s32|int)\s+("+re.escape(prefix)+r"\w+)\s*\([^;]*\)\s*(?:\{|$)",line)
  if not m:continue
  # Skip forward declaration. Require immediately following definition brace.
  j=i
  if "{" not in line:
   j+=1
   while j<len(lines) and not lines[j].strip():j+=1
   if j>=len(lines) or not lines[j].lstrip().startswith("{"):continue
  brace=0;started=False;end=j
  for k in range(j,min(len(lines),j+4000)):
   # Approximate balanced C function body with comments/strings present: widths
   # are candidates unless parser can independently validate.
   t=re.sub(r'//.*',"",lines[k])
   brace+=t.count("{")-t.count("}")
   if "{" in t:started=True
   if started and brace==0:end=k;break
  if m.group(1) in result:
   raise RuntimeError("Duplicate function definition "+m.group(1))
  result[m.group(1)]={"line":i+1,"text":"\n".join(lines[i:end+1])}
 return result
def field_entries(lines):
 entries=[];inside=False
 for n,line in enumerate(lines,1):
  if re.match(r"^\s*gScriptCmdTable::",line):inside=True;continue
  if re.match(r"^\s*gScriptCmdTableEnd::",line):break
  if not inside:continue
  m=re.match(r"^\s*\.4byte\s+(ScrCmd_\w+)\s+@\s*0x([0-9a-fA-F]+)",line)
  if m:
   idx=len(entries)
   if int(m.group(2),16)!=idx:raise RuntimeError(f"Discontiguous field opcode at line {n}: {m.group(2)} != {idx:X}")
   entries.append({"opcode":idx,"handler":m.group(1),"table_line":n})
  elif ".4byte" in line:
   raise RuntimeError("Field opcode missing integer annotation "+str(n))
 if len(entries)!=0xD5:raise RuntimeError(f"Expected 213 field opcodes, observed {len(entries)}")
 return entries
def battle_entries(lines):
 start=next((i for i,line in enumerate(lines) if "gBattleScriptingCommandsTable[])(void)" in line),None)
 if start is None:raise RuntimeError("Battle dispatch table not found")
 opened=False;entries=[]
 for n in range(start+1,len(lines)):
  t=lines[n]
  if not opened:
   if "{" in t:opened=True
   continue
  if re.match(r"^\s*};",t):break
  m=re.match(r"^\s*(Cmd_\w+)\s*,\s*//\s*0x([0-9a-fA-F]+)",t)
  if m:
   idx=len(entries)
   if idx!=int(m.group(2),16):raise RuntimeError("Discontiguous battle opcode at "+str(n+1))
   entries.append({"opcode":idx,"handler":m.group(1),"table_line":n+1})
  elif "Cmd_" in t and not t.lstrip().startswith("//"):
   raise RuntimeError("Battle opcode lacks annotated handler "+str(n+1))
 if len(entries)!=0xF8:raise RuntimeError(f"Expected 248 battle opcodes, observed {len(entries)}")
 return entries
def metrics(body,typ):
 return {
 "word_operand_reads":len(re.findall(r"\b(?:ScriptReadWord|T1_READ_PTR|T2_READ_PTR)\s*\(",body)),
 "halfword_operand_reads":len(re.findall(r"\b(?:ScriptReadHalfword|T1_READ_16|T2_READ_16)\s*\(",body)),
 "byte_operand_reads":len(re.findall(r"\bScriptReadByte\s*\(",body)),
 "native_pointer_role_candidate":bool(re.search(r"(?:\(\s*(?:void|bool8|u16)\s*\(\s*\*|SetupNativeScript)",body)),
 "raw_memory_pointer_role_candidate":bool(re.search(r"\*\s*\(\s*(?:const\s+)?(?:u8|u16|u32)\s*\*\s*\).*?(?:ScriptReadWord|T1_READ_PTR)",body,re.S)),
 "control_flow_pointer_role_candidate":bool(re.search(r"(?:ScriptCall|ScriptJump|gBattlescriptCurrInstr\s*=\s*T1_READ_PTR)\b",body))}
def main():
 rev=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
 if rev!=PIN:raise RuntimeError("Wrong FireRed commit")
 files={path:source(path) for path in EXPECTED}
 field=field_entries(files["data/script_cmd_table.inc"])
 battle=battle_entries(files["src/battle_script_commands.c"])
 fdefs=functions(files["src/scrcmd.c"],"ScrCmd_")
 bdefs=functions(files["src/battle_script_commands.c"],"Cmd_")
 if len(fdefs)<len(set(x["handler"] for x in field)):
  raise RuntimeError("Field function definitions missing")
 if len(bdefs)<len(set(x["handler"] for x in battle)):
  raise RuntimeError("Battle function definitions missing")
 dispatch_field="\n".join(files["src/script.c"])
 dispatch_battle="\n".join(files["src/battle_util.c"])
 if "ctx->cmdTable[cmdCode]" not in dispatch_field:raise RuntimeError("Field dispatch consumer changed")
 if "gBattleScriptingCommandsTable[*gBattlescriptCurrInstr]()" not in dispatch_battle:raise RuntimeError("Battle dispatch consumer changed")
 summary={"field_opcodes":len(field),"battle_opcodes":len(battle),
          "field_unique_handlers":len(set(x["handler"] for x in field)),
          "battle_unique_handlers":len(set(x["handler"] for x in battle)),
          "undefined_field_handlers":[],"undefined_battle_handlers":[],
          "source_blob_anchors_verified":len(EXPECTED),
          "function_pointer_dispatch_paths_captured":2,
          "bytecode_operand_ABI_verified":False,
          "runtime_execution_tested":False,"phase1_mapping_complete":False}
 with gzip.open(OUT/"bytecode_opcode_dispatch_semantic.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
  for typ,rows,table,site,handlerfile,defs in [
   ("FIELD",field,"data/script_cmd_table.inc","src/script.c","src/scrcmd.c",fdefs),
   ("BATTLE",battle,"src/battle_script_commands.c","src/battle_util.c","src/battle_script_commands.c",bdefs)]:
   for e in rows:
    d=defs.get(e["handler"])
    if not d:summary["undefined_"+typ.lower()+"_handlers"].append(e["handler"]);continue
    m=metrics(d["text"],typ)
    w.writerow({"repo":REPO,"dispatch_table":typ,"dispatch_table_path":table,
      "dispatch_table_sha":EXPECTED[table],"dispatch_site_path":site,
      "dispatch_site_sha":EXPECTED[site],"opcode":e["opcode"],
      "opcode_hex":hex(e["opcode"]),"handler":e["handler"],"handler_path":handlerfile,
      "handler_sha":EXPECTED[handlerfile],"table_line":e["table_line"],
      "handler_definition_line":d["line"],**m,
      "handler_classification_status":"SOURCE_PINNED_FUNCTION_TABLE_MATCH;OPERAND_ROLE_HEURISTIC"})
 if summary["undefined_field_handlers"] or summary["undefined_battle_handlers"]:
  raise RuntimeError("Missing declared handlers "+str(summary))
 (OUT/"bytecode_opcode_dispatch_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
