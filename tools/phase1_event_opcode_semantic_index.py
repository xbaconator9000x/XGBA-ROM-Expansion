#!/usr/bin/env python3
"""Exact-pinned FireRed event assembler macro -> opcode table -> runtime handler semantic index.

The index is a machine-verified source interpretation, never an independent whole-file review.
"""
from __future__ import annotations
import copy, hashlib, json, re, subprocess, sys
from pathlib import Path

PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={
 "asm/macros/event.inc":"142ad979d7d3093244087a247fa2b4883424f77f",
 "data/script_cmd_table.inc":"c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1",
 "src/scrcmd.c":"97b695ee2f6fca80a3b78f52f6a444f696fe5814",
 "src/script.c":"d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
}
SECONDARY={0x50:"applymovement",0x52:"waitmovement",0x54:"removeobject",0x56:"addobject"}
OUTPUT=Path("audit-output/field_script_opcode_semantic_index.json")
SUMMARY=Path("audit-output/field_script_opcode_semantic_summary.json")
OPCODE=re.compile(r"^\.byte\s+0x([0-9a-f]+)\s*$",re.I)
DIRECTIVE=re.compile(r"^\.(byte|2byte|4byte)\s+(.+)$")
TABLE=re.compile(r"^\s*\.4byte\s+(ScrCmd_\w+)\s+@\s+(0x[0-9a-f]+)\s*$",re.I)
HANDLER=re.compile(r"^\s*(?:bool8|u8|void|s16|u16|u32|s32)\s+(ScrCmd_\w+)\s*\(")

def fail(message): raise ValueError(message)
def blob_sha(raw): return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def read_pinned(root):
    actual=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    if actual!=PIN: fail("FireRed source revision mismatch")
    sources={}
    for path,expected in BLOBS.items():
        raw=(root/path).read_bytes()
        if blob_sha(raw)!=expected: fail("Pinned source blob mismatch: "+path)
        sources[path]=raw.decode("utf-8").splitlines()
    script=sources["src/script.c"]
    dispatch="\n".join(script[123:134])
    if ("cmdCode = *(ctx->scriptPtr)" not in dispatch
        or "cmdFunc = &ctx->cmdTable[cmdCode]" not in dispatch
        or "if (cmdFunc >= ctx->cmdTableEnd)" not in dispatch):
        fail("Script dispatch source interval changed")
    return sources

def parse_macros(lines):
    result=[]
    current=None
    for line_number,raw in enumerate(lines,1):
        text=raw.split("@",1)[0].strip()
        start=re.match(r"^\.macro\s+([A-Za-z_]\w*)\b",text)
        if start:
            if current is not None: fail("Nested macro without closing .endm")
            current={"name":start.group(1),"start_line":line_number,"body":[]}
        elif text==".endm":
            if current is None: fail("Unpaired .endm")
            current["end_line"]=line_number
            result.append(current)
            current=None
        elif current is not None and text:
            current["body"].append({"line":line_number,"text":text})
    if current is not None: fail("Unclosed assembler macro")
    if len({m["name"] for m in result})!=len(result): fail("Duplicate assembler macro name")
    for macro in result:
        opcodes=[]
        fixed=True
        width=0
        for item in macro["body"]:
            line=item["text"]
            literal=OPCODE.fullmatch(line)
            if literal: opcodes.append({"opcode":int(literal.group(1),16),"line":item["line"]})
            directive=DIRECTIVE.fullmatch(line)
            if directive and "," not in directive.group(2):
                width+={"byte":1,"2byte":2,"4byte":4}[directive.group(1)]
            else:
                fixed=False
        macro["opcode_literals"]=opcodes
        macro["classification"]=("NON_OPCODE_HELPER" if not opcodes else
                                 "FIXED_DIRECT_OPCODE" if fixed and len(opcodes)==1 else
                                 "CONDITIONAL_OR_DELEGATING_OPCODE")
        macro["fixed_encoded_bytes"]=width if macro["classification"]=="FIXED_DIRECT_OPCODE" else None
        del macro["body"]
    return result

def parse_table(lines):
    entries=[]
    for n,line in enumerate(lines,1):
        m=TABLE.match(line)
        if m:
            entries.append({"opcode":int(m.group(2),16),"handler":m.group(1),"table_line":n})
    return entries

def parse_handlers(lines):
    handlers={}
    for n,line in enumerate(lines,1):
        m=HANDLER.match(line)
        if m:
            if m.group(1) in handlers: fail("Duplicate runtime handler definition")
            handlers[m.group(1)]=n
    return handlers

def build_index(sources):
    macros=parse_macros(sources["asm/macros/event.inc"])
    table=parse_table(sources["data/script_cmd_table.inc"])
    handlers=parse_handlers(sources["src/scrcmd.c"])
    by_opcode={}
    for macro in macros:
        for literal in macro["opcode_literals"]:
            opcode=literal["opcode"]
            if opcode in by_opcode: fail("Assembler opcode literal appears in multiple macros")
            by_opcode[opcode]={"macro":macro["name"],"macro_start_line":macro["start_line"],
                               "macro_end_line":macro["end_line"],
                               "opcode_source_line":literal["line"],
                               "macro_classification":macro["classification"],
                               "fixed_encoded_bytes":macro["fixed_encoded_bytes"]}
    opcodes=[]
    for entry in table:
        code=entry["opcode"]
        macro=by_opcode.get(code)
        if macro is None: fail("Dispatch opcode has no assembler macro encoding: "+hex(code))
        opcodes.append(dict(entry,handler_definition_line=handlers.get(entry["handler"]),
                            **macro))
    return {"schema":"xgba.phase1.field_script_opcode_semantic_index.v1",
            "source_revision":PIN,"source_blobs":BLOBS,
            "independent_whole_file_approvals":0,"decision":"FAIL_INCOMPLETE",
            "dispatch":opcodes,"macros":macros,
            "limitations":["Source-level opcode/handler mapping; not compiled-byte validation",
                           "Fixed widths apply only to direct, single-opcode, directive-only macros",
                           "Conditional and delegating macros require expansion and runtime argument review",
                           "No script pointer bounds, compiler variant or independent whole-file signoff"]}

def validate_index(index):
    if (index.get("schema")!="xgba.phase1.field_script_opcode_semantic_index.v1"
        or index.get("source_revision")!=PIN or index.get("source_blobs")!=BLOBS
        or index.get("independent_whole_file_approvals")!=0
        or index.get("decision")!="FAIL_INCOMPLETE"):
        fail("Index provenance or review status drift")
    dispatch=index["dispatch"];macros=index["macros"]
    if len(dispatch)!=213 or len(macros)!=257: fail("Opcode or macro census drift")
    if [x["opcode"] for x in dispatch]!=list(range(213)): fail("Noncontiguous dispatch table")
    if len({x["handler"] for x in dispatch})!=213: fail("Duplicate handler")
    if len({x["name"] for x in macros})!=257: fail("Duplicate macro")
    if any(x["handler_definition_line"] is None for x in dispatch): fail("Missing runtime handler definition")
    direct=[x for x in macros if x["opcode_literals"]]
    fixed=[x for x in direct if x["classification"]=="FIXED_DIRECT_OPCODE"]
    helpers=[x for x in macros if x["classification"]=="NON_OPCODE_HELPER"]
    if len(direct)!=209 or len(fixed)!=177 or len(helpers)!=48:
        fail("Fixed/direct/conditional/helper semantic classification drift")
    if len([x for x in direct if x["classification"]=="CONDITIONAL_OR_DELEGATING_OPCODE"])!=32:
        fail("Dynamic macro classification drift")
    for item in dispatch:
        code=item["opcode"]
        expected=SECONDARY.get(code,item["handler"].removeprefix("ScrCmd_"))
        if item["macro"]!=expected: fail("Assembler macro to runtime handler mismatch: "+hex(code))
        if item["macro_classification"]=="FIXED_DIRECT_OPCODE":
            if item["fixed_encoded_bytes"] is None or item["fixed_encoded_bytes"]<1:
                fail("Unjustified fixed opcode width")
        elif item["fixed_encoded_bytes"] is not None:
            fail("Dynamic macro falsely assigned fixed width")
    if {x["opcode"] for x in dispatch if x["macro"]!=x["handler"].removeprefix("ScrCmd_")}!=set(SECONDARY):
        fail("Conditional alternate opcode mapping drift")
    return True

def negative_controls(index):
    cases=[
      ("false-approval",lambda d:d.update(independent_whole_file_approvals=1)),
      ("false-completion",lambda d:d.update(decision="PASS")),
      ("source-pin",lambda d:d["source_blobs"].update({"asm/macros/event.inc":"0"*40})),
      ("duplicate-dispatch",lambda d:d["dispatch"][1].update(opcode=0)),
      ("runtime-handler",lambda d:d["dispatch"][4].update(handler="ScrCmd_fake")),
      ("alternate-macro",lambda d:d["dispatch"][0x50].update(macro="applymovementat")),
      ("missing-handler",lambda d:d["dispatch"][7].update(handler_definition_line=None)),
      ("false-fixed-width",lambda d:d["dispatch"][0x5c].update(fixed_encoded_bytes=99)),
      ("missing-macro",lambda d:d["macros"].pop()),
    ]
    for name,change in cases:
        candidate=copy.deepcopy(index)
        change(candidate)
        try: validate_index(candidate)
        except ValueError: continue
        raise AssertionError("Fail-open event opcode index: "+name)
    return len(cases)

def main():
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path("upstream/pokefirered")
    sources=read_pinned(root)
    index=build_index(sources)
    validate_index(index)
    controls=negative_controls(index)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(index,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    summary={"schema":"xgba.phase1.field_script_opcode_semantic_summary.v1",
             "source_revision":PIN,"source_blobs_verified":len(BLOBS),
             "assembler_macros_mapped":257,"runtime_dispatch_opcodes":213,
             "runtime_handlers_resolved":213,"direct_opcode_macros":209,
             "conditional_alternate_opcodes":4,"fixed_width_direct_macros":177,
             "conditional_or_delegating_opcode_macros":32,"non_opcode_helpers":48,
             "alternate_opcode_macro_names":{hex(k):v for k,v in sorted(SECONDARY.items())},
             "negative_controls_passed":controls,
             "index_sha256":hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
             "independent_whole_file_approvals":0,"decision":"FAIL_INCOMPLETE"}
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Pinned field-script index: 257 macros, 213/213 runtime opcodes+handlers, 177 fixed direct widths, 32 dynamic direct, 48 helpers, 4 conditional opcode aliases, %d negative controls; 0 approvals; FAIL_INCOMPLETE" % controls)

if __name__=="__main__":
    try: main()
    except Exception as error:
        print("Pinned field-script opcode index FAILED:",error,file=sys.stderr)
        sys.exit(2)
