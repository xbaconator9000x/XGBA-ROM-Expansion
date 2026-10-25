#!/usr/bin/env python3
"""Phase 1 v6: exact pinned script opcode and modern linker variant semantic candidates; fail-closed."""
from __future__ import annotations
import collections, copy, csv, gzip, hashlib, io, json, subprocess, sys
from pathlib import Path
import phase1_crossrepo_authoring_abi_review as v5
import phase1_additive_review_scheduler as v2

PACKET=Path("semantic-snapshots/curated/script_variant_abi_additive_2026-10-26.json")
TARGET=Path("audit-output/architecture_semantic_review_queue_additive_v6.csv.gz")
SUMMARY=Path("audit-output/architecture_semantic_review_priority_additive_v6.json")
EVIDENCE=Path("audit-output/script_variant_abi_source_evidence.json")
TIER="A0F_PINNED_SCRIPT_VARIANT_ABI_ADDITIVE"
PINS=json.loads(r'''{"pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982","huderlem/poryscript":"c32481161c767b25a3425fa9f1f8729927ff3d55"}''')
BLOBS=json.loads(r'''{"pret/pokefirered/Makefile":"8b454dbd18eb0069fa5851d788697190890a5b37","pret/pokefirered/ld_script.ld":"9a4b45031e93c1e1da8186d8c697332710526048","pret/pokefirered/ld_script_modern.ld":"e930243522bd21da40cc1a05de9a42b8ad409b46","pret/pokefirered/asm/macros/event.inc":"142ad979d7d3093244087a247fa2b4883424f77f","pret/pokefirered/src/scrcmd.c":"97b695ee2f6fca80a3b78f52f6a444f696fe5814","pret/pokefirered/src/script.c":"d0433bdda062b138e53d1a1d3184b4566ad7d9dc","huderlem/poryscript/emitter/chunk.go":"bb3a6514988eb2699022551d3dbfe2bdce260377"}''')
CHECKS=json.loads(r'''[{"id":"MAKE_COMPILER_VARIANTS","repository":"pret/pokefirered","path":"Makefile","start":80,"end":93,"needles":["CC1 := tools/agbcc/bin/agbcc","MODERNCC := $(PREFIX)gcc","-mabi=apcs-gnu"]},{"id":"MAKE_LINK_VARIANTS","repository":"pret/pokefirered","path":"Makefile","start":370,"end":382,"needles":["ifeq ($(MODERN),0)","LD_SCRIPT := ld_script.ld","LD_SCRIPT := ld_script_modern.ld"]},{"id":"MAKE_IMAGE_PADDING","repository":"pret/pokefirered","path":"Makefile","start":393,"end":395,"needles":["$(OBJCOPY) -O binary","--pad-to 0x9000000"]},{"id":"LINK_ORIGINAL_REGION","repository":"pret/pokefirered","path":"ld_script.ld","start":4,"end":9,"needles":["ROM    (rx) : ORIGIN = 0x8000000, LENGTH = 32M"]},{"id":"LINK_MODERN_REGION","repository":"pret/pokefirered","path":"ld_script_modern.ld","start":4,"end":9,"needles":["ROM    (rx) : ORIGIN = 0x8000000, LENGTH = 32M"]},{"id":"LINK_MODERN_WILDCARDS","repository":"pret/pokefirered","path":"ld_script_modern.ld","start":40,"end":66,"needles":["*(.text*)","*(script_data)","*(.rodata*)"]},{"id":"EVENT_CALL_WORD","repository":"pret/pokefirered","path":"asm/macros/event.inc","start":21,"end":25,"needles":[".macro call destination:req",".byte 0x04",".4byte \\destination"]},{"id":"EVENT_GOTO_WORD","repository":"pret/pokefirered","path":"asm/macros/event.inc","start":27,"end":31,"needles":[".macro goto destination:req",".byte 0x05",".4byte \\destination"]},{"id":"EVENT_CONDITIONAL_WORD","repository":"pret/pokefirered","path":"asm/macros/event.inc","start":33,"end":45,"needles":[".macro goto_if condition:req",".macro call_if condition:req",".4byte \\destination"]},{"id":"EVENT_TERMINATORS","repository":"pret/pokefirered","path":"asm/macros/event.inc","start":11,"end":19,"needles":[".macro end",".byte 0x02",".macro return",".byte 0x03"]},{"id":"EVENT_LOADWORD","repository":"pret/pokefirered","path":"asm/macros/event.inc","start":103,"end":108,"needles":[".macro loadword destIndex:req, value:req",".4byte \\value"]},{"id":"EVENT_SETVAR","repository":"pret/pokefirered","path":"asm/macros/event.inc","start":152,"end":157,"needles":[".macro setvar destination:req, value:req",".2byte \\destination",".2byte \\value"]},{"id":"PSCRIPT_CHUNK_GOTO","repository":"huderlem/poryscript","path":"emitter/chunk.go","start":67,"end":80,"needles":["registerJumpChunk(c.returnID)","goto %s_%d"]},{"id":"PSCRIPT_CHUNK_TERMINATOR","repository":"huderlem/poryscript","path":"emitter/chunk.go","start":73,"end":92,"needles":["return \"end\"","return \"return\""]},{"id":"SCRCMD_CALL_CONSUMER","repository":"pret/pokefirered","path":"src/scrcmd.c","start":146,"end":150,"needles":["ScrCmd_call(","ScriptReadWord(ctx)","ScriptCall(ctx, scrptr)"]},{"id":"SCRCMD_GOTO_CONSUMER","repository":"pret/pokefirered","path":"src/scrcmd.c","start":133,"end":137,"needles":["ScrCmd_goto(","ScriptReadWord(ctx)","ScriptJump(ctx, scrptr)"]},{"id":"SCRCMD_CONDITIONAL_CONSUMER","repository":"pret/pokefirered","path":"src/scrcmd.c","start":153,"end":168,"needles":["ScrCmd_goto_if(","ScrCmd_call_if(","ScriptReadByte(ctx)","ScriptReadWord(ctx)"]},{"id":"SCRCMD_SETVAR_CONSUMER","repository":"pret/pokefirered","path":"src/scrcmd.c","start":336,"end":340,"needles":["GetVarPointer(ScriptReadHalfword(ctx))","*varPtr = ScriptReadHalfword(ctx)"]},{"id":"SCRIPT_WORD_READER","repository":"pret/pokefirered","path":"src/script.c","start":188,"end":195,"needles":["value0 = *(ctx->scriptPtr++)","value3 = *(ctx->scriptPtr++)","return (((((value3 << 8)"]},{"id":"SCRIPT_DISPATCH_BOUNDS","repository":"pret/pokefirered","path":"src/script.c","start":124,"end":134,"needles":["cmdFunc = &ctx->cmdTable[cmdCode]","if (cmdFunc >= ctx->cmdTableEnd)"]}]''')
EDGES=json.loads(r'''[{"id":"MODERN_SELECTS_DISTINCT_LINKER","producer":{"repository":"pret/pokefirered","path":"Makefile","start":370,"end":382},"consumer":{"repository":"pret/pokefirered","path":"ld_script_modern.ld","start":4,"end":9},"type":"build_variant","meaning":"The MODERN build selects ld_script_modern.ld rather than the original linker script; shared ROM origin/extent does not imply identical section placement.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"ORIGINAL_SELECTS_ORIGINAL_LINKER","producer":{"repository":"pret/pokefirered","path":"Makefile","start":370,"end":382},"consumer":{"repository":"pret/pokefirered","path":"ld_script.ld","start":4,"end":9},"type":"build_variant","meaning":"The non-modern, non-revision-10 build selects ld_script.ld; revision 10 is a separate unreviewed linker path.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"ROM_OUTPUT_PAD_IS_NOT_CAPACITY","producer":{"repository":"pret/pokefirered","path":"Makefile","start":393,"end":395},"consumer":{"repository":"pret/pokefirered","path":"ld_script_modern.ld","start":4,"end":9},"type":"image_boundary","meaning":"The Makefile pads binary output to address 0x09000000 (16 MiB from ROM origin), while the modern linker reserves a 32 MiB ROM region; these are different bounds.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"MODERN_WILDCARD_SECTION_ABI","producer":{"repository":"pret/pokefirered","path":"Makefile","start":80,"end":93},"consumer":{"repository":"pret/pokefirered","path":"ld_script_modern.ld","start":40,"end":66},"type":"linker_abi","meaning":"The modern compiler branch and modern linker wildcard sections form a distinct output path; compiled layout and relocation identity require separate proof.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"PSCRIPT_GOTO_TO_EVENT_OPCODE","producer":{"repository":"huderlem/poryscript","path":"emitter/chunk.go","start":67,"end":80},"consumer":{"repository":"pret/pokefirered","path":"asm/macros/event.inc","start":27,"end":31},"type":"script_encoding","meaning":"Poryscript emits a goto label reference which the native event macro encodes as opcode 0x05 followed by a 32-bit address.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"PSCRIPT_TERMINATORS_TO_EVENT_OPCODES","producer":{"repository":"huderlem/poryscript","path":"emitter/chunk.go","start":73,"end":92},"consumer":{"repository":"pret/pokefirered","path":"asm/macros/event.inc","start":11,"end":19},"type":"script_encoding","meaning":"Poryscript distinguishes end from return; FireRed encodes these as different single-byte opcodes, affecting control-flow lifetime.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"EVENT_CALL_TO_RUNTIME_POINTER","producer":{"repository":"pret/pokefirered","path":"asm/macros/event.inc","start":21,"end":25},"consumer":{"repository":"pret/pokefirered","path":"src/scrcmd.c","start":146,"end":150},"type":"runtime_dispatch","meaning":"The event call macro writes a four-byte destination consumed by ScrCmd_call through ScriptReadWord and ScriptCall.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"EVENT_GOTO_TO_RUNTIME_POINTER","producer":{"repository":"pret/pokefirered","path":"asm/macros/event.inc","start":27,"end":31},"consumer":{"repository":"pret/pokefirered","path":"src/scrcmd.c","start":133,"end":137},"type":"runtime_dispatch","meaning":"The event goto macro writes a four-byte destination consumed by ScrCmd_goto through ScriptReadWord and ScriptJump.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"EVENT_CONDITIONAL_TO_RUNTIME","producer":{"repository":"pret/pokefirered","path":"asm/macros/event.inc","start":33,"end":45},"consumer":{"repository":"pret/pokefirered","path":"src/scrcmd.c","start":153,"end":168},"type":"runtime_dispatch","meaning":"Conditional event branches encode a byte condition and four-byte destination, matched by the runtime read sequence.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"EVENT_WORD_TO_LITTLE_ENDIAN_READER","producer":{"repository":"pret/pokefirered","path":"asm/macros/event.inc","start":103,"end":108},"consumer":{"repository":"pret/pokefirered","path":"src/script.c","start":188,"end":195},"type":"operand_abi","meaning":"The four-byte loadword payload is read byte-by-byte little-endian by the native ScriptReadWord routine.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"EVENT_SETVAR_TO_HALFWORD_CONSUMER","producer":{"repository":"pret/pokefirered","path":"asm/macros/event.inc","start":152,"end":157},"consumer":{"repository":"pret/pokefirered","path":"src/scrcmd.c","start":336,"end":340},"type":"operand_abi","meaning":"The event setvar macro emits two halfwords consumed by consecutive ScriptReadHalfword calls in ScrCmd_setvar.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"},{"id":"RUNTIME_DISPATCH_BOUNDARY_REVIEW","producer":{"repository":"pret/pokefirered","path":"src/scrcmd.c","start":133,"end":137},"consumer":{"repository":"pret/pokefirered","path":"src/script.c","start":124,"end":134},"type":"runtime_bounds","meaning":"Script command dispatch indexes a command table using an opcode byte before checking its resulting function pointer against cmdTableEnd; this remains a source-level bounds review obligation.","proof_level":"PINNED_SOURCE_INTERPRETATION_ONLY"}]''')
CANDIDATES=json.loads(r'''[{"repository":"pret/pokefirered","path":"asm/macros/event.inc","git_blob_sha1":"142ad979d7d3093244087a247fa2b4883424f77f","source_lines":[1,1858],"semantic_roles":["field_script_opcode_assembler_widths","Poryscript_label_and_control_flow_consumer","direct_runtime_script_pointer_abi"],"unresolved":["whole_file_opcode_width_and_argument_semantics","compiled_script_pointer_relocation_bounds_and_executable_ranges","untrusted_bytecode_dispatch_validation_and_return_stack_safety"],"independent_signoff":false},{"repository":"pret/pokefirered","path":"ld_script_modern.ld","git_blob_sha1":"e930243522bd21da40cc1a05de9a42b8ad409b46","source_lines":[1,101],"semantic_roles":["modern_compiler_linker_section_layout","native_rom_region_vs_image_output_boundary","compiled_variant_relocation_identity"],"unresolved":["original_vs_modern_section_symbol_and_relocation_differences","revision_10_linker_variant_not_in_this_packet","compiled_image_hash_and_editor_adapter_compatibility"],"independent_signoff":false}]''')
ROOTS={"pret/pokefirered":Path("upstream/pokefirered"),"huderlem/poryscript":Path("upstream/poryscript")}

def fail(reason): raise ValueError(reason)
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def blob_sha(raw): return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def validate_packet(doc):
    if (doc.get("schema")!="xgba.phase1.script_variant_abi_additive.v1"
        or doc.get("pinned_revisions")!=PINS or doc.get("source_blobs")!=BLOBS
        or doc.get("source_checks")!=CHECKS or doc.get("cross_source_contracts")!=EDGES
        or doc.get("candidates")!=CANDIDATES or doc.get("original_curated_count_preserved")!=29
        or doc.get("previous_candidates_pending")!=38 or doc.get("additional_source_files")!=2
        or doc.get("independent_whole_file_approvals")!=0
        or doc.get("phase1_mapping_complete") is not False):
        fail("Packet source contracts, candidate identity, review or dependency drift")
    keys=[(c["repository"],c["path"]) for c in doc["candidates"]]
    if len(set(keys))!=2 or any(c["independent_signoff"] is not False for c in doc["candidates"]):
        fail("Duplicate or falsely signed candidate")
    checked={(c["repository"],c["path"],c["start"],c["end"]) for c in CHECKS}
    for edge in EDGES:
        for side in ("producer","consumer"):
            endpoint=edge[side]
            if (endpoint["repository"],endpoint["path"],endpoint["start"],endpoint["end"]) not in checked:
                fail("Unanchored edge: "+edge["id"])
        if edge["proof_level"]!="PINNED_SOURCE_INTERPRETATION_ONLY":
            fail("Edge claims review approval")
    return True

def verify_sources():
    for repo,root in ROOTS.items():
        actual=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
        if actual!=PINS[repo]: fail("Incorrect pinned source revision: "+repo)
    source={}
    for key,expected in BLOBS.items():
        repo,path=key.split("/",2)[:2],None
        # owner/repo/path, retaining all path components after the repository name
        owner,repository,relative=key.split("/",2)
        repo=owner+"/"+repository
        raw=(ROOTS[repo]/relative).read_bytes()
        if blob_sha(raw)!=expected: fail("Git blob mismatch: "+key)
        source[key]=raw.decode("utf-8").splitlines()
    evidence=[]
    for check in CHECKS:
        key=check["repository"]+"/"+check["path"]
        lines=source[key]
        if check["start"]<1 or check["end"]>len(lines): fail("Source line range drift: "+check["id"])
        excerpt="\n".join(lines[check["start"]-1:check["end"]])
        if any(needle not in excerpt for needle in check["needles"]):
            fail("Bounded source expression drift: "+check["id"])
        evidence.append({"contract_id":check["id"],"repository":check["repository"],
                         "path":check["path"],"lines":[check["start"],check["end"]],
                         "git_blob_sha1":BLOBS[key]})
    return evidence

def validate_state(doc,rows,original,base,gate,previous):
    validate_packet(doc)
    if (previous.get("decision")!="FAIL_INCOMPLETE" or previous.get("total_candidates_pending")!=38
        or previous.get("independent_whole_file_approvals")!=0
        or previous.get("output_queue_sha256")!=digest(v5.OUT)
        or previous.get("source_queue_sha256")!=digest(v2.SOURCE)
        or gate.get("decision")!="FAIL_INCOMPLETE" or gate.get("approved_semantic_dispositions")!=0
        or base.get("candidate_file_count")!=29 or base.get("independent_review_approvals")!=0
        or any(c.get("independent_whole_file_signoff") is not False for c in base["candidate_files"])):
        fail("Original gate, v5 provenance or independent approval drift")
    if len(rows)!=14834 or len(original)!=14834: fail("Census truncated")
    index={(r["repo"],r["path"]):r for r in rows}
    orig={(r["repo"],r["path"]):r for r in original}
    if len(index)!=14834 or len(orig)!=14834 or set(index)!=set(orig):
        fail("Source identity missing or duplicated")
    if collections.Counter(r["priority"] for r in rows)["P0"]!=338:
        fail("Original P0 count changed")
    prior=collections.Counter(r["architecture_review_tier"] for r in rows)
    if dict(prior)!=previous["tier_counts"]: fail("Earlier semantic candidate tiers drift")
    for key,row in index.items():
        old=orig[key]
        if any(row[f]!=old[f] for f in ("repo","path","blob_sha","priority","machine_review_status")):
            fail("Original source identity or review status drift: "+str(key))
        if row["source_queue_priority_preserved"]!=old["priority"] or row["source_queue_machine_review_status_preserved"]!=old["machine_review_status"]:
            fail("Original provenance drift")
    for c in CANDIDATES:
        key=(c["repository"],c["path"])
        if key not in index or index[key]["blob_sha"]!=c["git_blob_sha1"]:
            fail("New candidate not in pinned source census")
        if index[key]["curated_candidate_registry"] or index[key]["architecture_review_tier"]==TIER:
            fail("New candidate already curated")
        if any((b["repository"],b["source_path"])==key for b in base["candidate_files"]):
            fail("Original curated candidate double-counted")
    return index

def negative_controls(doc,rows,original,base,gate,previous):
    cases=[
      ("packet-approval",lambda d,r,o,b,g,p:d.update(independent_whole_file_approvals=1)),
      ("candidate-signoff",lambda d,r,o,b,g,p:d["candidates"][0].update(independent_signoff=True)),
      ("candidate-blob",lambda d,r,o,b,g,p:d["candidates"][0].update(git_blob_sha1="0"*40)),
      ("edge-endpoint",lambda d,r,o,b,g,p:d["cross_source_contracts"][0]["consumer"].update(start=1)),
      ("edge-proof",lambda d,r,o,b,g,p:d["cross_source_contracts"][0].update(proof_level="APPROVED")),
      ("v5-digest",lambda d,r,o,b,g,p:p.update(output_queue_sha256="0"*64)),
      ("gate-approval",lambda d,r,o,b,g,p:g.update(approved_semantic_dispositions=1)),
      ("original-signoff",lambda d,r,o,b,g,p:b["candidate_files"][0].update(independent_whole_file_signoff=True)),
      ("source-status",lambda d,r,o,b,g,p:r[0].update(machine_review_status="APPROVED")),
      ("missing-edge",lambda d,r,o,b,g,p:d["cross_source_contracts"].pop()),
    ]
    for label,change in cases:
        args=copy.deepcopy((doc,rows,original,base,gate,previous))
        change(*args)
        try: validate_state(*args)
        except ValueError: continue
        raise AssertionError("Fail-open v6 negative control: "+label)
    return len(cases)

def main():
    doc=json.loads(PACKET.read_text(encoding="utf-8"))
    validate_packet(doc)
    sources=verify_sources()
    v5.main()
    with gzip.open(v5.OUT,"rt",encoding="utf-8",newline="") as stream:
        rows=list(csv.DictReader(stream))
    with gzip.open(v2.SOURCE,"rt",encoding="utf-8",newline="") as stream:
        original=list(csv.DictReader(stream))
    base=json.loads(v2.BASE.read_text(encoding="utf-8"))
    gate=json.loads(v2.GATE.read_text(encoding="utf-8"))
    previous=json.loads(v5.SUMMARY.read_text(encoding="utf-8"))
    validate_state(doc,rows,original,base,gate,previous)
    negative=negative_controls(doc,rows,original,base,gate,previous)
    new={(c["repository"],c["path"]):c for c in CANDIDATES}
    expected_counts=collections.Counter(previous["tier_counts"])
    for row in rows:
        key=(row["repo"],row["path"])
        if key in new:
            expected_counts[row["architecture_review_tier"]]-=1
            row.update(architecture_review_tier=TIER,
                       architecture_review_reason="Pinned field-script opcode and modern linker ABI; independent review pending",
                       curated_semantic_roles=",".join(new[key]["semantic_roles"]),
                       curated_candidate_registry=str(PACKET))
    tiers=[v2.ORIGINAL_TIER,v2.EXTRA_TIER,"A0C_PINNED_MGBA_EEPROM_SAVESTATE_ADDITIVE",
           "A0D_PINNED_MGBA_CPU_MATRIX_ABI_ADDITIVE",v5.TIER,TIER,
           "A1_ARCHITECTURE_CRITICAL_P0","A2_OTHER_P0","A3_P0_GAMEPLAY_SCRIPT_FIXTURE",
           "A4_P1_QUEUE","A5_P2_QUEUE","A6_P3_QUEUE"]
    rank={name:i for i,name in enumerate(tiers)}
    counts=collections.Counter(r["architecture_review_tier"] for r in rows)
    if (len(rows)!=14834 or counts[TIER]!=2 or
        any(name not in rank for name in counts) or
        counts!=collections.Counter(dict(expected_counts, **{TIER:2}))):
        fail("New review tier damaged prior assignments")
    rows.sort(key=lambda row:(rank[row["architecture_review_tier"]],row["repo"],row["path"]))
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    with TARGET.open("wb") as file:
        with gzip.GzipFile(filename="",mode="wb",fileobj=file,mtime=0) as zipped:
            with io.TextIOWrapper(zipped,encoding="utf-8",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
                writer.writeheader();writer.writerows(rows)
    result={"schema":"xgba.phase1.architecture_review_additive.v6",
            "source_queue_sha256":digest(v2.SOURCE),
            "stage5_queue_sha256":digest(v5.OUT),
            "source_packet_sha256":digest(PACKET),
            "output_queue_sha256":digest(TARGET),
            "source_files_preserved":14834,"original_P0_preserved":338,
            "original_curated_pending":29,"previous_additive_pending":9,
            "script_variant_additive_pending":2,"total_candidates_pending":40,
            "source_contracts_verified":len(sources),
            "cross_source_dependencies":len(EDGES),
            "additional_negative_controls_passed":negative,
            "tier_counts":dict(sorted(counts.items())),
            "independent_whole_file_approvals":0,"phase1_mapping_complete":False,
            "decision":"FAIL_INCOMPLETE",
            "limitations":["Exact pinned source interpretation, not independent whole-file approval",
                           "Compiler/linker variant identity and executable pointer bounds remain uncertified",
                           "No Phase 2 implementation or original source census mutation"]}
    SUMMARY.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    EVIDENCE.write_text(json.dumps({"schema":"xgba.phase1.script_variant_abi_source.v1",
      "pinned_revisions":PINS,"verified_blobs":len(BLOBS),
      "verified_source_contracts":sources,"cross_source_contracts":EDGES,
      "independent_whole_file_approvals":0,"decision":"FAIL_INCOMPLETE"},
      indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Phase 1 v6: %d pinned blobs; %d expressions; %d typed edges; %d negative controls; 14,834 rows; 40 pending; 0 approved; FAIL_INCOMPLETE" %
          (len(BLOBS),len(sources),len(EDGES),negative))

if __name__=="__main__":
    try: main()
    except Exception as error:
        print("Phase 1 v6 FAILED:",error,file=sys.stderr)
        sys.exit(2)
