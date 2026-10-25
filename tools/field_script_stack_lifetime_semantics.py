#!/usr/bin/env python3
"""Pinned FireRed script-pointer stack control-flow semantics.

Source-level consumer/producer observation only, not a compiled runtime proof
or whole-file independent semantic disposition.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={
    "include/script.h":"ce10c87266a8019eeefaaf787f43b291e7a58624",
    "src/script.c":"d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
    "src/scrcmd.c":"97b695ee2f6fca80a3b78f52f6a444f696fe5814",
}
EXPECTED_COMMANDS={
    "ScrCmd_call":"ScriptCall(ctx, scrptr)",
    "ScrCmd_call_if":"ScriptCall(ctx, scrptr)",
    "ScrCmd_vcall":"ScriptCall(ctx, scrptr - sAddressOffset)",
    "ScrCmd_vcall_if":"ScriptCall(ctx, scrptr)",
    "ScrCmd_callstd":"ScriptCall(ctx, *script)",
    "ScrCmd_callstd_if":"ScriptCall(ctx, *script)",
}

class SourceContractFailure(RuntimeError):
    pass

def blob_sha(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def function_body(src,name):
    # Function extraction narrowly scoped to pinned source and simple C bodies.
    # Brace-balanced; anchors are also pinned to exact source blob SHA.
    pattern=(r"(?m)^[ \t]*(?:static[ \t]+)?"\n             r"(?:(?:bool8|u8|u16|u32|s8|s16|s32|int|void)[ \t]+|const[ \t]+u8[ \t]*\\*[ \t]*)"\n             +re.escape(name)+r"\s*\([^;]*?\)\s*\{")
    matches=list(re.finditer(pattern,src))
    if len(matches)!=1:raise SourceContractFailure("Missing/nonunique C definition "+name)
    m=matches[0]
    start=src.index("{",m.start())
    depth=0
    for i in range(start,len(src)):
        if src[i]=="{":depth+=1
        if src[i]=="}":
            depth-=1
            if not depth:
                return src[start+1:i],src.count("\n",0,m.start())+1,src.count("\n",0,i)+1
    raise SourceContractFailure("Unbalanced pinned function "+name)

def assert_in_order(body, tokens, label):
    at=0
    for token in tokens:
        pos=body.find(token,at)
        if pos<0:raise SourceContractFailure("Missing or reordered "+label+" :: "+token)
        at=pos+len(token)

def evaluate(header,script,commands):
    if not re.search(r"const u8\s*\*stack\s*\[\s*20\s*\]\s*;",header):
        raise SourceContractFailure("Unexpected script stack ABI")
    if not re.search(r"\bu8\s+stackDepth\s*;",header):
        raise SourceContractFailure("Unexpected stack depth ABI")
    push,a,b=function_body(script,"ScriptPush")
    assert_in_order(push,(
        "ctx->stackDepth + 1 >= (int)ARRAY_COUNT(ctx->stack)",
        "return 1;",
        "ctx->stack[ctx->stackDepth] = ptr;",
        "ctx->stackDepth++;",
        "return 0;"),"push boundary")
    call,cs,ce=function_body(script,"ScriptCall")
    assert_in_order(call,("ScriptPush(ctx, ctx->scriptPtr);",
                          "ctx->scriptPtr = ptr;"),"call failure path")
    if re.search(r"\bif\s*\([^)]*ScriptPush|return\s+ScriptPush",call):
        raise SourceContractFailure("ScriptCall now checks push result")
    pop,ps,pe=function_body(script,"ScriptPop")
    assert_in_order(pop,("if (ctx->stackDepth == 0)","return NULL;",
                         "ctx->stackDepth--;","return ctx->stack[ctx->stackDepth];"),"pop underflow")
    ret,rs,re_=function_body(script,"ScriptReturn")
    assert_in_order(ret,("ctx->scriptPtr = ScriptPop(ctx);",),"return")
    read,ws,we=function_body(script,"ScriptReadWord")
    if len(re.findall(r"\*\(ctx->scriptPtr\+\+\)",read))!=4:
        raise SourceContractFailure("Script pointer four-byte reader changed")
    if re.search(r"ScriptReadWord",read):
        raise SourceContractFailure("Unexpected recursive ScriptReadWord")
    runner,runner_s,runner_e=function_body(script,"RunScriptCommand")
    assert_in_order(runner,(
        "if (ctx->scriptPtr == NULL)",
        "cmdCode = *(ctx->scriptPtr);",
        "ctx->scriptPtr++;",
        "cmdFunc = &ctx->cmdTable[cmdCode];",
        "if (cmdFunc >= ctx->cmdTableEnd)"),"dispatch")
    discovered={}
    for func,call_token in EXPECTED_COMMANDS.items():
        body,start,end=function_body(commands,func)
        if call_token not in body:
            raise SourceContractFailure("Indirect call path changed "+func)
        discovered[func]={"source_start_line":start,"source_end_line":end}
    push_max=19 # depth 0 to 19; guard stops the 20th push.
    return {
        "semantic_status":"SOURCE_PINNED_CANDIDATE_NOT_INDEPENDENTLY_APPROVED",
        "script_stack_slots":20,
        "script_max_successful_nested_pushes_at_depth_zero":push_max,
        "attempted_20th_nested_call_does_not_push_return_address":True,
        "ScriptCall_ignores_failed_ScriptPush":True,
        "ScriptCall_changes_PC_after_failed_push":True,
        "return_underflow_produces_NULL_scriptPtr":True,
        "RunScriptCommand_detects_NULL_on_next_dispatch":True,
        "word_operand_reads":4,
        "call_commands_using_ScriptCall":discovered,
        "source_function_line_ranges":{
          "ScriptPush":[a,b],"ScriptCall":[cs,ce],"ScriptPop":[ps,pe],
          "ScriptReturn":[rs,re_],"ScriptReadWord":[ws,we],
          "RunScriptCommand":[runner_s,runner_e]
        },
        "runtime_behavior_tested":False,
        "safe_bank_remapping_implemented":False,
        "independent_whole_file_approvals":0,
        "phase1_mapping_complete":False,
        "extension_requirements":[
            "Pin each active script PC and return address to exact resource identity for its entire lifetime",
            "Do not relocate code resources while script frame has a live pointer into them",
            "New expansion interpreter must not inherit silent call-return loss on stack overflow",
            "Preserve bytecode opcode/operand ABI for unmodified native scripts",
            "Ensure async wait and native callbacks cannot outlive invalidated backing resources"
        ]
    }

def self_test(header,script,cmds):
    result=evaluate(header,script,cmds)
    if len(result["call_commands_using_ScriptCall"])!=6:
        raise SourceContractFailure("Incomplete cross-opcode call graph")
    negatives=[
        (header.replace("stack[20]","stack[21]"),script,cmds),
        (header,script.replace("ctx->stackDepth + 1 >= (int)ARRAY_COUNT(ctx->stack)",
                                     "ctx->stackDepth >= (int)ARRAY_COUNT(ctx->stack)"),cmds),
        (header,script.replace("ScriptPush(ctx, ctx->scriptPtr);",
                                   "if (ScriptPush(ctx, ctx->scriptPtr)) return;"),cmds),
        (header,script.replace("ScriptPush(ctx, ctx->scriptPtr);\n    ctx->scriptPtr = ptr;","ScriptPush(ctx, ctx->scriptPtr);\n    ctx->scriptPtr = NULL;"),cmds),
        (header,script.replace("cmdCode = *(ctx->scriptPtr);",
                               "cmdCode = 0;"),cmds),
        (header,script.replace("ctx->scriptPtr = ScriptPop(ctx);",
                               "ctx->scriptPtr = NULL;"),cmds),
        (header,script,cmds.replace("ScriptCall(ctx, scrptr - sAddressOffset);",
                                   "ScriptJump(ctx, scrptr - sAddressOffset);")),
    ]
    for i,case in enumerate(negatives,1):
        try:evaluate(*case)
        except SourceContractFailure:continue
        raise SourceContractFailure("Negative source mutation undetected: "+str(i))
    result["selftest_source_mutations_correctly_rejected"]=len(negatives)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("upstream/pokefirered"))
    p.add_argument("--out",type=Path,default=Path("audit-output/field_script_stack_lifetime_contract.json"))
    a=p.parse_args()
    if subprocess.check_output(["git","-C",str(a.root),"rev-parse","HEAD"],text=True).strip()!=PIN:
        raise SourceContractFailure("Pinned source revision mismatch")
    inputs={}
    for path,sha in BLOBS.items():
        data=(a.root/path).read_bytes()
        if blob_sha(data)!=sha:raise SourceContractFailure("Git source blob drift "+path)
        inputs[path]=data.decode("utf-8","surrogateescape")
    result=self_test(inputs["include/script.h"],inputs["src/script.c"],inputs["src/scrcmd.c"])
    result["pinned_revision"]=PIN
    result["pinned_git_blob_sha1"]=BLOBS
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Pinned FireRed script stack, pointer call paths, 7 source mutation controls: PASS; runtime and review gates PENDING")
if __name__=="__main__":main()
