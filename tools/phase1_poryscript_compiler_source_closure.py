#!/usr/bin/env python3
"""Inventory the pinned Poryscript compiler source closure without approving it."""
import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

PINS = {
    "poryscript": "c32481161c767b25a3425fa9f1f8729927ff3d55",
    "porymap": "26b919d7ff4b54152de010abd5bf344af2ebe116",
    "firered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
}

NEW_FILES = {
    "main.go": "CLI orchestration from source input through generated assembly output",
    "lexer/lexer.go": "Poryscript tokens, including mapscripts and source positions",
    "parser/parser.go": "Poryscript syntax and AST construction",
    "parser/parse_error.go": "Parser diagnostic source ranges",
    "parser/formattext.go": "Text replacement, formatting, and width diagnostics",
    "ast/ast.go": "Program, script, map-script, and statement representation",
    "token/token.go": "Token types and mapscripts keyword mapping",
    "emitter/emitter.go": "AST-to-assembler emission and chunk scheduling",
    "emitter/branch.go": "Branch and comparison assembler emission",
}

REUSED_FILES = {
    "emitter/chunk.go": {
        "candidate": "docs/phase1-disposition-candidates/0009-poryscript-chunk.md",
        "role": "Previously inventoried emitter control-flow helper; not new coverage",
    },
}

CONTEXT_FILES = {
    "poryscript": {
        "go.mod": "Compiler module and dependency declaration",
        "font_config.json": "Compiler text/font configuration consumed by the parser",
        "command_config.json": "Compiler command mapping configuration",
    },
    "porymap": {
        "src/project.cpp": "Existing Porymap writer evidence: .pory creation and scripts.inc reference",
    },
    "firered": {
        "Makefile": "Existing generated-target evidence; stock build has no .pory rule",
        "data/event_scripts.s": "Existing assembly include consumer",
        "tools/mapjson/mapjson.cpp": "Existing independent map-JSON-to-assembly producer",
        "map_data_rules.mk": "Existing mapjson build-rule evidence",
        "asm/macros/map.inc": "Existing native assembly consumer of generated map records",
        "data/maps/map_groups.json": "Existing mapjson input, distinct from Poryscript output",
    },
}

PRIOR_DOSSIERS = {
    "docs/phase1-review-readiness/porymap-native-generated-inc-20261029.md":
        "Previously executed Poryscript include/compiler consumer boundary",
    "docs/phase1-review-readiness/porymap-poryscript-generated-inc-20261029.md":
        "Previously inspected Porymap/Poryscript generation contract",
    "docs/phase1-review-readiness/porymap-cross-file-transaction-rollback-20261105.md":
        "Reused Porymap serialization boundary",
    "docs/phase1-disposition-candidates/0009-poryscript-chunk.md":
        "Previously inventoried emitter chunk helper",
    "docs/phase1-disposition-candidates/0032-firered-mapjson-generator.md":
        "Previously inventoried FireRed mapjson producer",
}

CONTRACTS = {
    "main.go": (
        "github.com/huderlem/poryscript/lexer",
        "github.com/huderlem/poryscript/parser",
        "github.com/huderlem/poryscript/emitter",
        "lexer.New(input)",
        "parser.New(",
        "parser.ParseProgram()",
        "emitter.New(program",
        "emitter.Emit()",
        "writeOutput(result",
    ),
    "lexer/lexer.go": (
        "func New(input string) *Lexer",
        "func (l *Lexer) NextToken() token.Token",
        "token.GetIdentType(tok.Literal)",
        "token.Token",
    ),
    "parser/parser.go": (
        "func New(",
        "func (p *Parser) ParseProgram()",
        "ast.Program",
        "token.MAPSCRIPTS",
        "lexer.Lexer",
    ),
    "parser/parse_error.go": (
        "func NewParseError(",
        "func NewRangeParseError(",
        "func (e ParseError) Error() string",
    ),
    "parser/formattext.go": (
        "func (fc *FontConfig) FormatText(",
        "func (fc *FontConfig) ApplyTextReplacementsWithOffsets(",
        "func (fc *FontConfig) ValidateLineWidths(",
    ),
    "ast/ast.go": (
        "type Program struct",
        "type ScriptStatement struct",
        "type MapScriptsStatement struct",
        "Token token.Token",
    ),
    "token/token.go": (
        'MAPSCRIPTS = "MAPSCRIPTS"',
        'var keywords = map[string]Type{',
        '"mapscripts": MAPSCRIPTS',
        "func GetIdentType(ident string) Type",
    ),
    "emitter/emitter.go": (
        "type Emitter struct",
        "func New(",
        "func (e *Emitter) Emit()",
        "*ast.Program",
        "chunk",
    ),
    "emitter/branch.go": (
        "type brancher interface",
        "func renderBranchComparison(",
        "token.DEFEATED",
    ),
}

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def git(root, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    require(result.returncode == 0, "git command failed: " + " ".join(args))
    return result.stdout.strip()

def pinned_file(root, name, path):
    expected = git(root, "rev-parse", PINS[name] + ":" + path)
    actual = git(root, "hash-object", "--", path)
    require(actual == expected, "working-tree source differs from pinned blob: " + name + "/" + path)
    data = (root / path).read_bytes()
    return {
        "repository": name,
        "commit": PINS[name],
        "path": path,
        "git_blob": actual,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "lines": len(data.splitlines()),
    }, data.decode("utf-8")

def verify_source_contract(sources):
    for path, required in CONTRACTS.items():
        text = sources[path]
        for anchor in required:
            require(anchor in text, "source contract changed: " + path + ": " + anchor)
    require("type MapScriptsStatement struct" in sources["ast/ast.go"],
            "map script AST contract changed")
    require("MAPSCRIPTS = \"MAPSCRIPTS\"" in sources["token/token.go"],
            "mapscripts token contract changed")
    return True

def verify_context_contract(context_sources):
    mapjson = context_sources["firered/tools/mapjson/mapjson.cpp"]
    for anchor in ("Json::parse", "generate_groups_text", "process_groups"):
        require(anchor in mapjson, "mapjson source contract changed: " + anchor)
    for marker in ("poryscript", ".pory", "scripts.inc"):
        require(marker not in mapjson.lower(),
                "mapjson unexpectedly references Poryscript output: " + marker)
    return True

def source_negatives(sources):
    mutations = (
        ("main.go", "emitter.New(program", "emitter.New(nil"),
        ("lexer/lexer.go", "token.GetIdentType(tok.Literal)", "token.IDENT"),
        ("parser/parser.go", "token.MAPSCRIPTS", "token.MAP"),
        ("parser/parse_error.go", "NewRangeParseError(", "RangeParseError("),
        ("parser/formattext.go", "FormatText(", "FormatTextChanged("),
        ("ast/ast.go", "type MapScriptsStatement struct", "type MapScriptStatement struct"),
        ("token/token.go", '"mapscripts": MAPSCRIPTS', '"mapscripts": IDENT'),
        ("emitter/emitter.go", "func (e *Emitter) Emit()", "func (e *Emitter) EmitChanged()"),
        ("emitter/branch.go", "type brancher interface", "type brancher struct"),
    )
    for index, (path, old, new) in enumerate(mutations):
        require(old in sources[path], "missing source mutation anchor " + str(index))
        changed = dict(sources)
        changed[path] = sources[path].replace(old, new)
        try:
            verify_source_contract(changed)
        except ValueError:
            continue
        raise ValueError("source mutation escaped " + str(index))
    return len(mutations)

def context_source_negatives(context_sources):
    path = "firered/tools/mapjson/mapjson.cpp"
    changed = dict(context_sources)
    changed[path] += "\n// scripts.inc\n"
    try:
        verify_context_contract(changed)
    except ValueError:
        return 1
    raise ValueError("mapjson direct-consumer negative escaped")

def validate_evidence(evidence):
    require(evidence["upstream_pins"] == PINS, "upstream pin changed")
    require(evidence["new_source_file_count"] == len(NEW_FILES), "new source count changed")
    require(evidence["reused_file_count"] == len(REUSED_FILES), "reused source count changed")
    require(evidence["context_file_count"] == sum(map(len, CONTEXT_FILES.values())),
            "context source count changed")
    require(len(evidence["files"]) == 20, "source matrix row count changed")
    require(len({row["repository"] + "/" + row["path"] for row in evidence["files"]}) == 20,
            "duplicate source matrix row")
    require(evidence["source_mutations_rejected"] == len(NEW_FILES) + 1,
            "source negative controls missing")
    require(evidence["context_mutations_rejected"] == 1,
            "mapjson boundary negative control missing")
    require(evidence["evidence_mutations_rejected"] == 14,
            "evidence negative controls missing")
    require(evidence["evidence_status"] == "NEEDS_EVIDENCE", "evidence status overclaimed")
    require(evidence["independent_approvals"] == 0, "approval count overclaimed")
    require(evidence["phase1_gate"] == "FAIL_INCOMPLETE", "gate overclaimed")
    require(evidence["direct_poryscript_to_mapjson_edge"] is False,
            "Poryscript/mapjson relationship overclaimed")
    require(evidence["native_rom_or_gameplay_execution"] is False,
            "runtime execution overclaimed")
    require(evidence["whole_file_independent_approval"] is False,
            "independent review overclaimed")
    for row in evidence["files"]:
        require(row["sha256"] and len(row["sha256"]) == 64, "invalid source SHA-256")
        require(row["disposition"] == "NEEDS_EVIDENCE", "file disposition overclaimed")
    require(evidence["dossier_sha256"] and len(evidence["dossier_sha256"]) == 64,
            "invalid dossier SHA-256")
    require(len(evidence["prior_dossiers"]) == len(PRIOR_DOSSIERS),
            "prior dossier inventory changed")
    for row in evidence["prior_dossiers"]:
        require(row["sha256"] and len(row["sha256"]) == 64, "invalid prior dossier SHA-256")

def evidence_negatives(evidence):
    mutations = (
        {"upstream_pins": {}},
        {"new_source_file_count": 8},
        {"reused_file_count": 0},
        {"context_file_count": 0},
        {"source_mutations_rejected": 8},
        {"context_mutations_rejected": 0},
        {"evidence_status": "PASSED"},
        {"independent_approvals": 1},
        {"phase1_gate": "PASS"},
        {"direct_poryscript_to_mapjson_edge": True},
        {"native_rom_or_gameplay_execution": True},
        {"whole_file_independent_approval": True},
        {"dossier_sha256": ""},
        {"prior_dossiers": []},
    )
    for index, mutation in enumerate(mutations):
        try:
            validate_evidence({**evidence, **mutation})
        except ValueError:
            continue
        raise ValueError("evidence mutation escaped " + str(index))
    return len(mutations)

def make_archive(paths, destination):
    tar_bytes = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes, mode="w") as archive:
        for path, archive_name in paths:
            data = path.read_bytes()
            info = tarfile.TarInfo(archive_name)
            info.size = len(data)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(tar_bytes.getvalue())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porymap", required=True, type=Path)
    ap.add_argument("--poryscript", required=True, type=Path)
    ap.add_argument("--firered", required=True, type=Path)
    ap.add_argument("--dossier", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--archive", required=True, type=Path)
    args = ap.parse_args()
    roots = {
        "porymap": args.porymap.resolve(),
        "poryscript": args.poryscript.resolve(),
        "firered": args.firered.resolve(),
    }
    for name, root in roots.items():
        require(git(root, "rev-parse", "HEAD") == PINS[name], "upstream commit drift: " + name)

    file_rows = []
    sources = {}
    context_sources = {}
    for path in NEW_FILES:
        row, sources[path] = pinned_file(roots["poryscript"], "poryscript", path)
        row.update({"role": NEW_FILES[path], "coverage": "new_inventory",
                    "disposition": "NEEDS_EVIDENCE"})
        file_rows.append(row)
    for path, metadata in REUSED_FILES.items():
        row, _ = pinned_file(roots["poryscript"], "poryscript", path)
        row.update({"role": metadata["role"], "coverage": "reused_existing_candidate",
                    "candidate": metadata["candidate"], "disposition": "NEEDS_EVIDENCE"})
        file_rows.append(row)
    for owner, paths in CONTEXT_FILES.items():
        for path, role in paths.items():
            row, text = pinned_file(roots[owner], owner, path)
            context_sources[owner + "/" + path] = text
            row.update({"role": role, "coverage": "reused_prior_evidence",
                        "disposition": "NEEDS_EVIDENCE"})
            file_rows.append(row)

    verify_source_contract(sources)
    source_negative_count = source_negatives(sources)
    verify_context_contract(context_sources)
    context_negative_count = context_source_negatives(context_sources)
    license_row, license_text = pinned_file(
        roots["poryscript"], "poryscript", "LICENSE.md")
    require("MIT License" in license_text and "Permission is hereby granted" in license_text,
            "pinned Poryscript MIT notice changed")
    porymap_license, porymap_license_text = pinned_file(
        roots["porymap"], "porymap", "LICENSE.md")
    require("GNU LESSER GENERAL PUBLIC LICENSE" in porymap_license_text,
            "pinned Porymap license notice changed")
    firered_root_licenses = git(roots["firered"], "ls-tree", "--name-only", "HEAD", "--",
                                "LICENSE", "LICENSE.md", "COPYING", "COPYING.md").splitlines()
    require(not firered_root_licenses, "FireRed root license inventory changed")

    dossier_bytes = args.dossier.read_bytes()
    dossier_sha = hashlib.sha256(dossier_bytes).hexdigest()
    prior_dossiers = []
    for path, role in PRIOR_DOSSIERS.items():
        data = Path(path).read_bytes()
        prior_dossiers.append({
            "path": path,
            "role": role,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "lines": len(data.splitlines()),
        })
    evidence = {
        "class": "PINNED_PORYSCRIPT_COMPILER_SOURCE_CLOSURE",
        "upstream_pins": PINS,
        "files": file_rows,
        "new_source_file_count": len(NEW_FILES),
        "reused_file_count": len(REUSED_FILES),
        "context_file_count": sum(map(len, CONTEXT_FILES.values())),
        "license_evidence": {
            "poryscript": {"path": "LICENSE.md", **license_row,
                           "license_text_observed": "MIT License"},
            "porymap": {"path": "LICENSE.md", **porymap_license,
                        "license_text_observed": "GNU LESSER GENERAL PUBLIC LICENSE"},
            "firered": {
                "root_license_files": firered_root_licenses,
                "interpretation": "No listed root notice; no legal or redistribution conclusion",
            },
        },
        "producer_consumer_finding": {
            "porymap_creates_pory_and_references_scripts_inc": True,
            "poryscript_compiler_closure_emits_assembly_text": True,
            "firered_event_scripts_includes_generated_assembly": True,
            "mapjson_consumes_map_json_as_a_separate_producer": True,
            "direct_poryscript_to_mapjson_edge": False,
            "interpretation": "The mapjson and script-include outputs converge in the build; mapjson does not consume Poryscript output.",
        },
        "prior_dossiers": prior_dossiers,
        "direct_poryscript_to_mapjson_edge": False,
        "dossier_sha256": dossier_sha,
        "source_mutations_rejected": source_negative_count + context_negative_count,
        "context_mutations_rejected": context_negative_count,
        "evidence_mutations_rejected": 14,
        "evidence_status": "NEEDS_EVIDENCE",
        "whole_file_independent_approval": False,
        "native_rom_or_gameplay_execution": False,
        "upstream_modified": False,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    validate_evidence(evidence)
    evidence["evidence_mutations_rejected"] = evidence_negatives(evidence)
    validate_evidence(evidence)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    make_archive(
        ((args.dossier, "poryscript-compiler-source-closure.md"),
         (args.output, "poryscript-compiler-source-closure.json")),
        args.archive,
    )
    archive_sha = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    args.archive.with_suffix(args.archive.suffix + ".sha256").write_text(
        archive_sha + "  " + args.archive.name + "\n")
    print(json.dumps({**evidence, "archive_sha256": archive_sha}, sort_keys=True))

if __name__ == "__main__":
    main()
