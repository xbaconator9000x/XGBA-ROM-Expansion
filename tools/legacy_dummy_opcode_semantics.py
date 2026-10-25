#!/usr/bin/env python3
"""Source-prove FireRed legacy dummy field commands and zero padding semantics.

Crucial XGBA compatibility: some FRLG handlers intentionally never consume
assembler-emitted parameters. The following bytes are separate bytecode opcodes;
not all are safe to reinterpret as extension prefixes. In particular, the
hidemoneybox assembler appends two opcode-0 NOP bytes as legacy padding.
"""
from pathlib import Path
import collections,csv,gzip,hashlib,json,re,subprocess
ROOT=Path("upstream/pokefirered");OUT=Path("audit-output")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
SOURCES={
 "src/scrcmd.c":"97b695ee2f6fca80a3b78f52f6a444f696fe5814",
 "asm/macros/event.inc":"142ad979d7d3093244087a247fa2b4883424f77f",
 "data/script_cmd_table.inc":"c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1",
 "src/script.c":"d0433bdda062b138e53d1a1d3184b4566ad7d9dc"}
EXPECTED={
 "initclock":("0x2c","ScrCmd_initclock",4),
 "drawboxtext":("0x74","ScrCmd_drawboxtext",4),
 "setberrytree":("0x8a","ScrCmd_setberrytree",3),
 "hidemoneybox":("0x94","ScrCmd_hidemoneybox",2),
 "getpokenewsactive":("0x96","ScrCmd_getpokenewsactive",2),
 "addelevmenuitem":("0xb1","ScrCmd_addelevmenuitem",7)}
CLEAN=re.compile(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
def gitsha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def code(text):return CLEAN.sub(lambda m:re.sub(r"[^\n]"," ",m.group(0)),text)
def tracked():
 raw=subprocess.check_output(["git","-C",str(ROOT),"ls-tree","-r","-z","HEAD"])
 result={}
 for e in raw.split(b"\0"):
  if not e:continue
  attrs,path=e.split(b"\t",1)
  _,kind,sha=attrs.decode().split()
  if kind=="blob":result[path.decode("utf-8","surrogateescape")]=sha
 return result
def slice_macro(text,name):
 lines=text.splitlines()
 start=next((i for i,l in enumerate(lines) if re.match(r"^\s*\.macro\s+"+re.escape(name)+r"(?:\s|$)",l)),None)
 if start is None:raise RuntimeError("Missing legacy dummy macro "+name)
 end=next((i for i in range(start+1,len(lines)) if re.match(r"^\s*\.endm\b",lines[i])),None)
 if end is None:raise RuntimeError("Unterminated legacy dummy macro "+name)
 return start+1,lines[start:end+1]
def slice_handler(text,name):
 lines=text.splitlines()
 start=next((i for i,l in enumerate(lines) if re.match(r"^\s*bool8\s+"+re.escape(name)+r"\s*\(",l)),None)
 if start is None:raise RuntimeError("Handler not found "+name)
 brace=next((i for i in range(start,len(lines)) if "{" in lines[i]),None)
 depth=0;end=None
 for i in range(brace,len(lines)):
  sanitized=code(lines[i])
  depth+=sanitized.count("{")-sanitized.count("}")
  if depth==0:end=i;break
 if end is None:raise RuntimeError("Handler unbalanced "+name)
 return start+1,"\n".join(lines[start:end+1])
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Wrong pinned source revision")
 manifest=tracked();sources={}
 for path,sha in SOURCES.items():
  data=(ROOT/path).read_bytes()
  if gitsha(data)!=sha:raise RuntimeError("Source blob drift "+path)
  sources[path]=data.decode("utf-8","surrogateescape")
 table=sources["data/script_cmd_table.inc"]
 if not re.search(r"gScriptCmdTable::\s*\.4byte ScrCmd_nop\s+@\s*0x00",table):
  raise RuntimeError("Original field opcode zero no longer dispatches ScrCmd_nop")
 script=sources["src/script.c"]
 if not re.search(r"cmdCode = \*\(ctx->scriptPtr\);\s*ctx->scriptPtr\+\+;",script):
  raise RuntimeError("Field interpreter opcode cursor semantics changed")
 nline,nbody=slice_handler(sources["src/scrcmd.c"],"ScrCmd_nop")
 if not re.search(r"return FALSE\s*;",code(nbody)) or re.search(r"ScriptRead\w*\s*\(",code(nbody)):
  raise RuntimeError("Opcode 0 is no longer a no-consume nop")
 findings={}
 for name,(op,handler,width) in EXPECTED.items():
  mline,macro=slice_macro(sources["asm/macros/event.inc"],name)
  hline,hbody=slice_handler(sources["src/scrcmd.c"],handler)
  active=code(hbody)
  if re.search(r"\bScriptRead(?:Word|Byte|Halfword)\s*\(",active):
   raise RuntimeError("Legacy dummy command started consuming bytes "+name)
  emits=[]
  for line in macro[1:]:
   m=re.match(r"^\s*\.(byte|2byte|4byte)\s+(.+?)(?:\s+@.*)?$",line)
   if m:
    widths={"byte":1,"2byte":2,"4byte":4}
    arg=m.group(2).strip()
    emits.append((widths[m.group(1)],arg))
  if not emits or int(emits[0][1],0)!=int(op,0) or emits[0][0]!=1:
   raise RuntimeError("Changed opcode byte source "+name)
  total=sum(n for n,_ in emits[1:])
  if total!=width:raise RuntimeError("Encoded legacy dummy parameter width changed "+name)
  if name=="hidemoneybox":
   if emits!=[(1,"0x94"),(1,"0"),(1,"0")]:
    raise RuntimeError("Hidemoneybox does not emit two literal zero NOP bytes")
  findings[name]={"opcode":op,"handler":handler,"macro_line":mline,
    "handler_line":hline,"assembler_operand_bytes":width,
    "handler_explicit_operand_reads":0,
    "source_blob_macro":SOURCES["asm/macros/event.inc"],
    "source_blob_handler":SOURCES["src/scrcmd.c"],
    "interpretation":"TWO_LITERAL_ZERO_NOP_BYTES" if name=="hidemoneybox" else
       "EMITTED_PARAMETER_BYTES_NOT_CONSUMED_BY_THIS_HANDLER",
    "source_status":"PINNED_SOURCE_VERIFIED_NOT_FULL_SCRIPT_RUNTIME"}
 # Audit actual checked-in script command invocation sites. A macro defined in
 # asm/macros is not itself a call; inspect actual data/asm .inc/.s sources.
 occurrences=collections.defaultdict(list)
 for path,sha in manifest.items():
  if not path.startswith(("data/","asm/")) or path.startswith("asm/macros/"):
   continue
  if not path.endswith((".inc",".s",".asm",".pory")):continue
  data=(ROOT/path).read_bytes()
  if gitsha(data)!=sha:raise RuntimeError("Script source hash changed "+path)
  if b"\0" in data:continue
  for n,line in enumerate(data.decode("utf-8","surrogateescape").splitlines(),1):
   cmd=line.split("@",1)[0].strip().split()
   if cmd and cmd[0] in EXPECTED:
    occurrences[cmd[0]].append({"path":path,"line":n,"git_blob_sha":sha,
                                "assembly":line.strip()[:180]})
 if not occurrences["hidemoneybox"]:
  raise RuntimeError("Expected existing source scripts to invoke hidemoneybox")
 result={"original_dispatch_nop_opcode":"0x00","opcode_0_handler":"ScrCmd_nop",
  "opcode_0_is_vanilla_nop_source_verified":True,
  "dummy_source_handlers_confirmed":len(findings),
  "dummy_handler_abi":findings,"checked_in_script_invocations":dict(occurrences),
  "invocation_counts":{name:len(occurrences[name]) for name in EXPECTED},
  "compatibility_hazard":"Opcode 0 cannot be repurposed as unconditional extension prefix; hidemoneybox emits two source-literal NOP bytes.",
  "source_bytecode_execution_tested":False,"whole_file_semantic_signoffs":0,
  "phase1_mapping_complete":False,
  "limitations":["The interpreter source path supports NOP-step interpretation, but compiled runtime execution traces are not run here.",
    "Direct source invocation counts exclude dynamically produced bytecode and macros invoked through other helper macros.",
    "Do not rewrite original parameter bytes or auto-skip them as a universal compatibility fix."]}
 (OUT/"legacy_dummy_opcode_source_semantics.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"dummy_handlers":len(findings),"script_usage_counts":result["invocation_counts"],
  "hidemoneybox_literal_nops_verified":True,"phase1_complete":False},indent=2))
if __name__=="__main__":main()
