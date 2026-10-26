#!/usr/bin/env python3
"""Exact-pinned Poryscript-to-FireRed map-script and control-flow source contract.

Evidence is source-only; negative fixtures must fail, and no semantic approvals are issued.
"""
import argparse
import json
import subprocess
from pathlib import Path

PS_PIN = "c32481161c767b25a3425fa9f1f8729927ff3d55"
FR_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PS_BLOBS = {
    "emitter/chunk.go": "bb3a6514988eb2699022551d3dbfe2bdce260377",
    "emitter/branch.go": "9413b4699597e453c4ca8df4e1d6be9c68d250a2",
    "emitter/emitter.go": "d35843ef29929ead47351646d7a33dd5c692b850",
    "emitter/emitter_test.go": "4c3209166937384a0dc26fc83a0341a5dac48ca5",
    "main.go": "10db05ef1518460da78b0bd41f22bb091917a385",
}
FR_BLOBS = {
    "asm/macros/map.inc": "83ef472c926ce767c9133ab9bd6922280b38bb2d",
    "asm/macros/event.inc": "142ad979d7d3093244087a247fa2b4883424f77f",
    "src/script.c": "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
    "src/event_data.c": "da9391cf0ef74c1addf550def8616c81f16e89e3",
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def section(source, start, end):
    i = source.find(start)
    require(i >= 0, "missing function/macro start: " + start)
    j = source.find(end, i + len(start))
    require(j >= 0, "missing function/macro end: " + end)
    return source[i:j]


def ordered(source, *anchors):
    cursor = 0
    for anchor in anchors:
        i = source.find(anchor, cursor)
        require(i >= 0, "missing or reordered scoped semantic anchor: " + anchor)
        cursor = i + len(anchor)


def contract(ps, fr):
    emitter = ps["emitter/emitter.go"]
    chunk = ps["emitter/chunk.go"]
    branch = ps["emitter/branch.go"]
    tests = ps["emitter/emitter_test.go"]
    main = ps["main.go"]
    mapmacro = fr["asm/macros/map.inc"]
    event = fr["asm/macros/event.inc"]
    script = fr["src/script.c"]
    event_data = fr["src/event_data.c"]

    authored_map = section(emitter, "func (e *Emitter) emitMapScriptStatement(", "func (e *Emitter) emitScriptStatement(")
    ordered(authored_map,
            r"\tmap_script %s, %s\n",
            r"\t.byte 0\n\n",
            r"\tmap_script_2 %s, %s, %s\n",
            r"\t.2byte 0\n\n")
    native_map = section(mapmacro, ".macro map_script type:req, script:req", "@ Defines an object event")
    ordered(native_map,
            ".macro map_script type:req, script:req",
            r".byte \type", r".4byte \script",
            ".macro map_script_2 var:req, compare:req, script:req",
            r".2byte \var", r".2byte \compare", r".4byte \script")

    label = section(chunk, "func (c *chunk) getLabel(", "func (c *chunk) renderLabel(")
    ordered(label, "if c.id == 0 {", "return scriptName",
            'return fmt.Sprintf("%s_%d", scriptName, c.id)')
    render_label = section(chunk, "func (c *chunk) renderLabel(", "func (c *chunk) renderStatements(")
    ordered(render_label, "if isMainEntryPoint && isGlobal {",
            r'%s::\n', r'%s:\n')
    statements = section(chunk, "func (c *chunk) renderStatements(", "func (c *chunk) renderBranching(")
    ordered(statements, "if _, ok := chunkLabels[labelStmt.Name.Value]; ok {",
            "if _, ok := textLabels[labelStmt.Name.Value]; ok {",
            "return fmt.Errorf(")
    branching = section(chunk, "func (c *chunk) renderBranching(", "func (c *chunk) getTerminatorCommand(")
    ordered(branching, "if c.branchBehavior != nil {",
            "if c.returnID == -1 {", "c.getTerminatorCommand()",
            "} else if c.returnID != nextChunkID {", "registerJumpChunk(c.returnID)")
    terminator = section(chunk, "func (c *chunk) getTerminatorCommand(", "func (c *chunk) splitChunkForBranch(")
    ordered(terminator, "if c.useEndTerminator {", 'return "end"', 'return "return"')
    splitting = section(chunk, "func (c *chunk) splitChunkForBranch(", "func (c *chunk) isLastStatement(")
    ordered(splitting, "if c.isLastStatement(statementIndex) {",
            "returnID = c.returnID", "*chunkCounter++",
            "c.createPostLogicChunk(*chunkCounter, statementIndex)",
            "c.returnID = newChunk.id")
    post = section(chunk, "func (c *chunk) createPostLogicChunk(", "func renderCommandStatement(")
    ordered(post, "returnID:   c.returnID,", "statements: c.statements[lastStatementIndex+1:]")
    commands = section(chunk, "func renderCommandStatement(", "func renderLabelStatement(")
    ordered(commands, "commandStmt.Name.Value", 'strings.Join(commandStmt.Args, ", ")')
    labels = chunk[chunk.index("func renderLabelStatement("):]
    ordered(labels, "if labelStmt.IsGlobal {", r'%s::\n', r'%s:\n')

    var_branch = section(branch, "func renderVarComparison(", "func renderDefeatedComparison(")
    ordered(var_branch, 'compareCommand := "compare"',
            "if dest.operatorExpression.ComparisonValueType == ast.StrictValueComparison {",
            'compareCommand = "compare_var_to_value"',
            "case token.EQ:", r"\tgoto_if_eq %s_%d\n")
    native_compare = section(event, ".macro compare var:req, arg:req", ".macro callnative")
    ordered(native_compare, "VARS_START", "SPECIAL_VARS_START",
            r"compare_var_to_var \var, \arg", r"compare_var_to_value \var, \arg")
    switch_branch = section(branch, "func (s *switchBranch) renderBranchConditions(", "func (s *switchBranch) getTailChunkID(")
    ordered(switch_branch, r"\tswitch %s\n", r"\tcase %s, %s_%d\n")
    native_switch = section(event, ".macro switch var:req", "YES = 1")
    ordered(native_switch, ".macro switch var:req",
            r"copyvar VAR_0x8000, \var",
            ".macro case condition:req, dest:req",
            r"compare VAR_0x8000, \condition", r"goto_if_eq \dest")
    require(".macro goto_if_eq a:req, b, c" in event
            and "trycompare goto_if, 1" in event,
            "FireRed conditional branch macro changed")

    render_chunks = section(emitter, "func (e *Emitter) renderChunks(", "func optimizeChunkOrder(")
    ordered(render_chunks, "chunkIDs = optimizeChunkOrder(chunks)",
            "sort.Ints(chunkIDs)",
            "chunk.renderStatements(", "chunk.renderBranching(",
            "if chunkID == 0 || jumpChunks[chunkID] {")
    require('flag.Bool("optimize", true' in main and 'flag.Bool("lm", true' in main,
            "Poryscript command-line defaults changed")
    first_test = section(tests, "func TestEmit1(", "func TestEmitDoWhile(")
    ordered(first_test, "expectedUnoptimized :=", "expectedOptimized :=",
            'e := New(program, false, false, "")',
            'e = New(program, true, false, "")')


    # Native consumer confirms both distinct sentinel widths and record strides.
    header_reader = section(script, "static u8 *MapHeaderGetScriptTable(", "static void MapHeaderRunScriptType(")
    ordered(header_reader, "const u8 *mapScripts = gMapHeader.mapScripts;",
            "if (mapScripts == NULL)", "if (*mapScripts == 0)",
            "if (*mapScripts == tag)", "return T2_READ_PTR(mapScripts);",
            "mapScripts += 5;")
    table_reader = section(script, "static u8 *MapHeaderCheckScriptTable(", "void RunOnLoadMapScript(")
    ordered(table_reader, "varIndex1 = T1_READ_16(ptr);",
            "if (!varIndex1)", "ptr += 2;",
            "varIndex2 = T1_READ_16(ptr);", "ptr += 2;",
            "if (VarGet(varIndex1) == VarGet(varIndex2))",
            "return T2_READ_PTR(ptr);", "ptr += 4;")
    pointer = section(event_data, "u16 *GetVarPointer(", "static bool8 IsFlagOrVarStoredInQuestLog(")
    ordered(pointer, "if (idx < VARS_START)", "return NULL;",
            "if (idx < SPECIAL_VARS_START)",
            "return &gSaveBlock1Ptr->vars[idx - VARS_START];",
            "return gSpecialVars[idx - SPECIAL_VARS_START];")
    get = section(event_data, "u16 VarGet(", "bool8 VarSet(")
    ordered(get, "GetVarPointer(idx);", "if (ptr == NULL)",
            "return idx;", "return *ptr;")

    return {
        "map_script_entry": "Poryscript_type_plus_label_to_FireRed_1byte_type_4byte_pointer",
        "map_script_table": "Poryscript_var_compare_label_to_FireRed_2byte_var_2byte_compare_4byte_pointer",
        "map_script_terminators": "one_byte_type_zero_and_two_byte_table_var_zero",
        "native_consumer": "five_byte_tag_pointer_scan_and_eight_byte_var_compare_pointer_scan",
        "varget": "returns_immediate_id_when_GetVarPointer_is_null_else_dereferenced_value",
        "comparison": "strict_value_uses_explicit_compare_var_to_value_otherwise_range_sensitive_compare",
        "switch_scratch": "FireRed_switch_macro_writes_VAR_0x8000_and_case_reads_it",
        "chunk_labels": "generated_suffixes_and_optimization_dependent_fallthrough",
        "implicit_termination": "return_unless_explicit_terminal_end",
        "runtime_or_editor_certified": False,
        "whole_file_independent_review": False,
    }


def negative_controls(ps, fr):
    # Each fixture mutates only a disposable in-memory copy of a verified pinned file.
    cases = [
        ("ps", "emitter/emitter.go", r"\t.byte 0\n\n", r"\t.2byte 0\n\n"),
        ("ps", "emitter/emitter.go", r"\t.2byte 0\n\n", r"\t.byte 0\n\n"),
        ("ps", "emitter/emitter.go", r"\tmap_script_2 %s, %s, %s\n", r"\tmap_script_2 %s, %s\n"),
        ("fr", "asm/macros/map.inc", r".4byte \script", r".2byte \script"),
        ("fr", "asm/macros/map.inc", r".2byte \compare", r".byte \compare"),
        ("ps", "emitter/chunk.go", "if c.id == 0 {", "if c.id == 1 {"),
        ("ps", "emitter/chunk.go", 'return "end"', 'return "return"'),
        ("ps", "emitter/chunk.go", 'return "return"', 'return "end"'),
        ("ps", "emitter/chunk.go", "if _, ok := textLabels[labelStmt.Name.Value]; ok {", "if false {"),
        ("ps", "emitter/branch.go", 'compareCommand = "compare_var_to_value"', 'compareCommand = "compare_var_to_var"'),
        ("ps", "emitter/branch.go", r"\tswitch %s\n", r"\tcall %s\n"),
        ("fr", "asm/macros/event.inc", r"copyvar VAR_0x8000, \var", r"copyvar VAR_0x8001, \var"),
        ("fr", "asm/macros/event.inc", r"compare VAR_0x8000, \condition", r"compare VAR_0x8001, \condition"),
        ("fr", "asm/macros/event.inc", r"compare_var_to_var \var, \arg", r"compare_var_to_value \var, \arg"),
        ("ps", "emitter/emitter.go", "chunkIDs = optimizeChunkOrder(chunks)", "chunkIDs = nil"),
        ("ps", "main.go", 'flag.Bool("optimize", true', 'flag.Bool("optimize", false'),
        ("ps", "emitter/emitter_test.go", 'e = New(program, true, false, "")', 'e = New(program, false, false, "")'),

        ("fr", "src/script.c", "mapScripts += 5;", "mapScripts += 6;"),
        ("fr", "src/script.c", "if (*mapScripts == 0)", "if (*mapScripts == 1)"),
        ("fr", "src/script.c", "varIndex1 = T1_READ_16(ptr);", "varIndex1 = T1_READ_8(ptr);"),
        ("fr", "src/script.c", "if (!varIndex1)", "if (!varIndex2)"),
        ("fr", "src/script.c", "if (VarGet(varIndex1) == VarGet(varIndex2))", "if (varIndex1 == varIndex2)"),
        ("fr", "src/event_data.c", "return idx;", "return 0;"),
        ("fr", "src/event_data.c", "return gSpecialVars[idx - SPECIAL_VARS_START];", "return gSpecialVars[0];"),
    ]
    for n, (which, path, old, new) in enumerate(cases, 1):
        source = ps if which == "ps" else fr
        require(old in source[path], "missing mutation fixture " + str(n))
        altered = dict(source)
        altered[path] = source[path].replace(old, new, 1)
        try:
            contract(altered if which == "ps" else ps,
                     altered if which == "fr" else fr)
        except RuntimeError:
            continue
        raise RuntimeError("fail-closed mutation escaped source contract: " + str(n))
    return len(cases)


def load(root, pin, blobs):
    root = root.resolve()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args],
                                       text=True, stderr=subprocess.PIPE).strip()
    require(git("rev-parse", "HEAD") == pin, "wrong pinned upstream commit: " + str(root))
    sources = {}
    for path, expected in blobs.items():
        require((root / path).is_file(), "missing upstream source " + path)
        require(git("hash-object", path) == expected, "wrong upstream Git blob " + path)
        sources[path] = (root / path).read_text(encoding="utf-8")
    return sources


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poryscript", required=True, type=Path)
    ap.add_argument("--firered", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    ps = load(args.poryscript, PS_PIN, PS_BLOBS)
    fr = load(args.firered, FR_PIN, FR_BLOBS)
    facts = contract(ps, fr)
    negatives = negative_controls(ps, fr)
    result = {
        "class": "PINNED_PORYSCRIPT_FIRERED_MAP_SCRIPT_SOURCE_CANDIDATE",
        "poryscript_commit": PS_PIN,
        "firered_commit": FR_PIN,
        "poryscript_blobs": PS_BLOBS,
        "firered_blobs": FR_BLOBS,
        "facts": facts,
        "negative_controls_passed": negatives,
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "not_proven": [
            "assembled_script_bytecode_equivalence",
            "switch_scratch_safety_for_all_authored_scripts",
            "source_reconstruction_from_compiled_bytecode",
            "editor_roundtrip_or_runtime_compatibility",
            "independent_review_of_any_file",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(f"PINNED_PORYSCRIPT_FIRERED_SOURCE_PASS negative_controls={negatives}")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()
