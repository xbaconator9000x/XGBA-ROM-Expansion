#!/usr/bin/env python3
"""Pinned Phase 1 revision-10 linker/source-order semantic reconciliation.

Whole-file ordered source comparisons, not compiled ABI or independent approval.
This extends the v6 pending-review queue without modifying the source census.
"""
from __future__ import annotations

import collections
import copy
import csv
import difflib
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import phase1_script_variant_review as v6
import phase1_additive_review_scheduler as v2

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
ROOT = Path("upstream/pokefirered")
BLOBS = {
    "Makefile": "8b454dbd18eb0069fa5851d788697190890a5b37",
    "config.mk": "c07d31fc083fa341cca29c340e560ed107d5364a",
    "ld_script.ld": "9a4b45031e93c1e1da8186d8c697332710526048",
    "ld_script_rev10.ld": "4eb3bc2eec749437be5797202442188972ac0693",
    "ld_script_modern.ld": "e930243522bd21da40cc1a05de9a42b8ad409b46",
    "sym_bss.txt": "81e7e205162328e36fc705686a9a3c7e31f76971",
    "sym_bss_rev10.txt": "1a90ebb38dcfc592f7583f477889982f353f4019",
    "sym_common.txt": "9798689adf6f66580306c904b2678d7bc785bc82",
    "sym_common_rev10.txt": "ce4a446c3ab4484bc2087cf96723a17a9b47156d",
    "sym_ewram.txt": "cee4e8281efefd8a47ae5568192c4084e88c8d4c",
    "sym_ewram_rev10.txt": "cee4e8281efefd8a47ae5568192c4084e88c8d4c",
}
SECTIONS = ("ewram", "iwram", ".text", "script_data", "lib_text", ".rodata",
            "song_data", "lib_rodata", "multiboot_data", "gfx_data", "extra")
TIER = "A0G_PINNED_REV10_LINKER_ABI_ADDITIVE"
CANDIDATE = ("pret/pokefirered", "ld_script_rev10.ld")
TARGET = Path("audit-output/architecture_semantic_review_queue_additive_v7.csv.gz")
SUMMARY = Path("audit-output/architecture_semantic_review_priority_additive_v7.json")
EVIDENCE = Path("audit-output/rev10_linker_semantic_index_v7.json")
SECTION_RE = re.compile(r"^\s*([.\w]+)\s*(?:0x[0-9a-fA-F]+)?\s*(?:\(NOLOAD\))?\s*:")
REF_RE = re.compile(r"^\s*(?:INCLUDE\b|(?:src|data|sound)/|\*)")
MOVES = {
    ".text": ([], ["src/librfu_stwi.o(.text);", "src/librfu_rfu.o(.text);"]),
    "lib_text": (["src/librfu_stwi.o(.text);", "src/librfu_rfu.o(.text);"], []),
    ".rodata": ([], ["src/librfu_rfu.o(.rodata);"]),
    "lib_rodata": (["src/librfu_rfu.o(.rodata);"], []),
}
EDGES = [
    ("REV10_SELECTS_DISTINCT_LINKER", "Makefile", [370, 382], "ld_script_rev10.ld", [4, 9], "build_variant"),
    ("REV10_CONFIG_NAMES_SWITCH", "config.mk", [41, 53], "Makefile", [370, 382], "build_variant"),
    ("REV10_EWRAM_GENERATED_ORDER", "ld_script_rev10.ld", [18, 21], "sym_ewram_rev10.txt", [1, 137], "linker_generated_input"),
    ("REV10_BSS_GENERATED_ORDER", "ld_script_rev10.ld", [30, 33], "sym_bss_rev10.txt", [1, 38], "linker_generated_input"),
    ("REV10_COMMON_GENERATED_ORDER", "ld_script_rev10.ld", [38, 41], "sym_common_rev10.txt", [1, 56], "linker_generated_input"),
    ("REV10_RFU_TEXT_RELOCATION_ORDER", "ld_script_rev10.ld", [50, 75], "ld_script.ld", [50, 75], "ordered_section_difference"),
    ("REV10_RFU_RODATA_RELOCATION_ORDER", "ld_script_rev10.ld", [397, 412], "ld_script.ld", [397, 412], "ordered_section_difference"),
    ("REV10_COMMON_RFUS_AND_UNION_ROOM", "sym_common_rev10.txt", [1, 56], "sym_common.txt", [1, 55], "generated_symbol_order"),
    ("MODERN_WILDCARDS_NOT_REV10_LAYOUT", "ld_script_modern.ld", [40, 66], "ld_script_rev10.ld", [50, 75], "linker_variant_difference"),
    ("REV10_ROM_REGION_NOT_OUTPUT_PADDING", "Makefile", [393, 395], "ld_script_rev10.ld", [4, 9], "image_boundary"),
]

def fail(message):
    raise ValueError(message)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def verify_blobs(raws):
    if set(raws) != set(BLOBS):
        fail("Pinned linker/symbol source file set drift")
    for path, expected in BLOBS.items():
        if blob_sha(raws[path]) != expected:
            fail("Pinned source Git blob mismatch: " + path)

def read_sources():
    actual = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if actual != PIN:
        fail("Incorrect FireRed pinned revision")
    raw = {path: (ROOT / path).read_bytes() for path in BLOBS}
    verify_blobs(raw)
    return {path: data.decode("utf-8").splitlines() for path, data in raw.items()}

def require(lines, start, end, *needles):
    if not (1 <= start <= end <= len(lines)):
        fail("Invalid bounded source range")
    excerpt = "\n".join(lines[start - 1:end])
    if any(needle not in excerpt for needle in needles):
        fail("Source expression not present at pinned lines: " + repr(needles))
    return True

def sections(lines):
    out = {}
    current = None
    for n, line in enumerate(lines, 1):
        match = SECTION_RE.match(line)
        if match and match.group(1) in SECTIONS:
            current = match.group(1)
            if current in out:
                fail("Repeated linker section: " + current)
            out[current] = {"line": n, "refs": []}
        if current and REF_RE.match(line) and not line.lstrip().startswith(("/*", "//", "@")):
            out[current]["refs"].append({"line": n, "text": line.strip()})
    return out

def changed_hunks(a, b):
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    return [{"tag": tag, "original_lines": [i + 1, j],
             "revision10_lines": [k + 1, l],
             "original": a[i:j], "revision10": b[k:l]}
            for tag, i, j, k, l in matcher.get_opcodes() if tag != "equal"]

def source_index(source):
    make, config = source["Makefile"], source["config.mk"]
    require(make, 370, 382, "ifeq ($(GAME_REVISION),10)",
            "LD_SCRIPT := ld_script_rev10.ld",
            "sym_bss_rev10.ld", "sym_common_rev10.ld", "sym_ewram_rev10.ld",
            "LD_SCRIPT := ld_script_modern.ld")
    require(make, 355, 369, "sym_bss_rev10.ld", "sym_common_rev10.ld", "sym_ewram_rev10.ld")
    require(make, 393, 395, "--pad-to 0x9000000")
    require(config, 41, 53, "ifeq ($(GAME_REVISION),10)", "BUILD_NAME  := $(BUILD_NAME)_switch")
    original = sections(source["ld_script.ld"])
    revision = sections(source["ld_script_rev10.ld"])
    modern = sections(source["ld_script_modern.ld"])
    if tuple(original) != SECTIONS or tuple(revision) != SECTIONS:
        fail("Unexpected original/revision-10 ordered section layout")
    if not {".text", "script_data", ".rodata"}.issubset(modern):
        fail("Modern linker section boundary missing")
    for path in ("ld_script.ld", "ld_script_rev10.ld", "ld_script_modern.ld"):
        require(source[path], 4, 9, "ROM    (rx) : ORIGIN = 0x8000000, LENGTH = 32M")
    for path, section, include in (
        ("ld_script.ld", "ewram", "sym_ewram.ld"),
        ("ld_script.ld", "iwram", "sym_bss.ld"),
        ("ld_script.ld", "iwram", "sym_common.ld"),
        ("ld_script_rev10.ld", "ewram", "sym_ewram_rev10.ld"),
        ("ld_script_rev10.ld", "iwram", "sym_bss_rev10.ld"),
        ("ld_script_rev10.ld", "iwram", "sym_common_rev10.ld")):
        if not any(ref["text"] == 'INCLUDE "' + include + '"' for ref in
                   (original if path == "ld_script.ld" else revision)[section]["refs"]):
            fail("Missing exact linker symbol include: " + path + ":" + include)
    changes = {}
    for section in SECTIONS:
        a = [r["text"] for r in original[section]["refs"]]
        b = [r["text"] for r in revision[section]["refs"]]
        if section in ("ewram", "iwram"):
            b = [s.replace("_rev10.ld", ".ld") for s in b]
        removed, added = MOVES.get(section, ([], []))
        if ([s for s in a if s not in removed] !=
                [s for s in b if s not in added]):
            fail("Unexpected ordered object selection drift: " + section)
        if any(a.count(s) != 1 for s in removed) or any(b.count(s) != 1 for s in added):
            fail("Expected revision-10 object relocation missing: " + section)
        changes[section] = {"original_refs": len(a), "revision10_refs": len(b),
                            "removed_from_section": removed, "added_to_section": added}
    for stem, expected_added in (
        ("sym_bss", ['\t.include "src/librfu_stwi.o"', '\t.include "src/librfu_rfu.o"']),
        ("sym_common", ['\t.include "union_room.o"']),
        ("sym_ewram", [])):
        a = source[stem + ".txt"]
        b = source[stem + "_rev10.txt"]
        if [s for s in b if s not in a] != expected_added:
            fail("Unexpected revision-10 generated symbol additions: " + stem)
        if [s for s in a if s not in b]:
            fail("Unexpected revision-10 generated symbol removals: " + stem)
        if stem in ("sym_bss", "sym_ewram") and [s for s in b if s not in expected_added] != a:
            fail("Unexpected BSS/EWRAM generated symbol order")
    if (source["sym_common_rev10.txt"].index('\t.include "librfu_stwi.o"') >=
            source["sym_common_rev10.txt"].index('\t.include "text.o"') or
            source["sym_common.txt"].index('\t.include "librfu_stwi.o"') <=
            source["sym_common.txt"].index('\t.include "text.o"')):
        fail("RFU common-symbol order not as mapped")
    if source["sym_ewram.txt"] != source["sym_ewram_rev10.txt"]:
        fail("EWRAM symbol order unexpectedly differs")
    for _, producer, plines, consumer, clines, _ in EDGES:
        for path, bounds in ((producer, plines), (consumer, clines)):
            if not (1 <= bounds[0] <= bounds[1] <= len(source[path])):
                fail("Unanchored dependency endpoint: " + path)
    return {
        "schema": "xgba.phase1.rev10_linker_source_index.v1",
        "pinned_revision": PIN,
        "git_blobs": BLOBS,
        "source_file_count": len(BLOBS),
        "section_order_original": list(original),
        "section_order_revision10": list(revision),
        "section_order_modern": list(modern),
        "section_reference_differences": changes,
        "whole_file_ordered_diff_hunks": changed_hunks(source["ld_script.ld"], source["ld_script_rev10.ld"]),
        "symbol_order_differences": {
            stem: changed_hunks(source[stem + ".txt"], source[stem + "_rev10.txt"])
            for stem in ("sym_bss", "sym_common", "sym_ewram")},
        "cross_source_dependencies": [
            {"id": key, "producer": {"repository": "pret/pokefirered", "path": p,
                                     "lines": pl},
             "consumer": {"repository": "pret/pokefirered", "path": c, "lines": cl},
             "type": typ, "proof_level": "PINNED_SOURCE_INTERPRETATION_ONLY"}
            for key, p, pl, c, cl, typ in EDGES],
        "candidate": {"repository": CANDIDATE[0], "path": CANDIDATE[1],
                      "git_blob_sha1": BLOBS[CANDIDATE[1]], "independent_signoff": False,
                      "unresolved": ["compiled_revision10_section_symbol_relocation_identity",
                                     "generated_symbol_ram_lifetime_and_alignment",
                                     "editor_emulator_variant_roundtrip_and_runtime_compatibility"]},
        "independent_whole_file_approvals": 0,
        "decision": "FAIL_INCOMPLETE",
    }

def validate_queue(rows, original, prior, base, gate, index):
    if (prior.get("decision") != "FAIL_INCOMPLETE" or
        prior.get("total_candidates_pending") != 40 or
        prior.get("independent_whole_file_approvals") != 0 or
        prior.get("output_queue_sha256") != digest(v6.TARGET) or
        gate.get("decision") != "FAIL_INCOMPLETE" or
        gate.get("approved_semantic_dispositions") != 0 or
        base.get("candidate_file_count") != 29 or
        base.get("independent_review_approvals") != 0 or
        index.get("decision") != "FAIL_INCOMPLETE" or
        index.get("independent_whole_file_approvals") != 0 or
        index.get("candidate", {}).get("independent_signoff") is not False or
        index.get("candidate", {}).get("git_blob_sha1") != BLOBS[CANDIDATE[1]] or
        len(index.get("cross_source_dependencies", [])) != len(EDGES)):
        fail("Source index, prior queue, or independent-review gate drift")
    if len(rows) != 14834 or len(original) != 14834:
        fail("Truncated source census")
    before = {(r["repo"], r["path"]): r for r in original}
    after = {(r["repo"], r["path"]): r for r in rows}
    if len(before) != 14834 or len(after) != 14834 or set(before) != set(after):
        fail("Source identity missing or duplicated")
    if collections.Counter(r["priority"] for r in rows)["P0"] != 338:
        fail("Original P0 count drift")
    if collections.Counter(r["architecture_review_tier"] for r in rows) != prior["tier_counts"]:
        fail("Prior candidate tier count drift")
    for key, row in after.items():
        old = before[key]
        if any(row[f] != old[f] for f in
               ("repo", "path", "blob_sha", "priority", "machine_review_status")):
            fail("Original source or machine review status modified: " + repr(key))
    if (CANDIDATE not in after or after[CANDIDATE]["blob_sha"] != BLOBS[CANDIDATE[1]] or
        after[CANDIDATE]["curated_candidate_registry"] or
        after[CANDIDATE]["architecture_review_tier"] == TIER):
        fail("Revision-10 candidate not eligible or source hash changed")
    return after

def negative_controls(rows, original, prior, base, gate, index):
    mutations = [
        ("gate-approval", lambda a: a[4].update(approved_semantic_dispositions=1)),
        ("prior-approval", lambda a: a[2].update(independent_whole_file_approvals=1)),
        ("index-approval", lambda a: a[5].update(independent_whole_file_approvals=1)),
        ("candidate-signoff", lambda a: a[5]["candidate"].update(independent_signoff=True)),
        ("candidate-hash", lambda a: a[5]["candidate"].update(git_blob_sha1="0" * 40)),
        ("missing-edge", lambda a: a[5]["cross_source_dependencies"].pop()),
        ("prior-digest", lambda a: a[2].update(output_queue_sha256="0" * 64)),
        ("source-status", lambda a: a[0][0].update(machine_review_status="APPROVED")),
        ("missing-source", lambda a: a[0].pop()),
    ]
    for label, mutate in mutations:
        args = list(copy.deepcopy((rows, original, prior, base, gate, index)))
        mutate(args)
        try:
            validate_queue(*args)
        except ValueError:
            continue
        fail("Fail-open v7 negative control: " + label)
    return len(mutations)

def main():
    source = read_sources()
    index = source_index(source)
    v6.main()
    with gzip.open(v6.TARGET, "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with gzip.open(v2.SOURCE, "rt", encoding="utf-8", newline="") as stream:
        original = list(csv.DictReader(stream))
    prior = json.loads(v6.SUMMARY.read_text(encoding="utf-8"))
    base = json.loads(v2.BASE.read_text(encoding="utf-8"))
    gate = json.loads(v2.GATE.read_text(encoding="utf-8"))
    after = validate_queue(rows, original, prior, base, gate, index)
    negatives = negative_controls(rows, original, prior, base, gate, index)
    candidate = after[CANDIDATE]
    old_tier = candidate["architecture_review_tier"]
    candidate.update(architecture_review_tier=TIER,
                     architecture_review_reason="Pinned revision-10 linker and generated-symbol ordering; independent review pending",
                     curated_semantic_roles="revision10_linker_section_order,generated_ram_symbol_dependencies",
                     curated_candidate_registry="audit-output/rev10_linker_semantic_index_v7.json")
    expected = collections.Counter(prior["tier_counts"])
    expected[old_tier] -= 1
    expected[TIER] += 1
    counts = collections.Counter(r["architecture_review_tier"] for r in rows)
    if counts != expected or counts[TIER] != 1:
        fail("v7 review queue changed earlier candidate assignments")
    previous_order = list(dict.fromkeys(r["architecture_review_tier"] for r in rows
                                        if r["architecture_review_tier"] != TIER))
    if v6.TIER not in previous_order:
        fail("v6 review tier missing")
    pos = previous_order.index(v6.TIER) + 1
    ordered_tiers = previous_order[:pos] + [TIER] + previous_order[pos:]
    rank = {name: n for n, name in enumerate(ordered_tiers)}
    rows.sort(key=lambda row: (rank[row["architecture_review_tier"]],
                               row["repo"], row["path"]))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("wb") as file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=file, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    EVIDENCE.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "schema": "xgba.phase1.architecture_review_additive.v7",
        "source_queue_sha256": digest(v2.SOURCE),
        "stage6_queue_sha256": digest(v6.TARGET),
        "output_queue_sha256": digest(TARGET),
        "source_index_sha256": digest(EVIDENCE),
        "source_files_preserved": 14834,
        "original_P0_preserved": 338,
        "original_curated_pending": 29,
        "previous_candidates_pending": 40,
        "revision10_additive_pending": 1,
        "total_candidates_pending": 41,
        "exact_pinned_blobs_verified": len(BLOBS),
        "typed_dependencies": len(EDGES),
        "additional_negative_controls_passed": negatives,
        "tier_counts": dict(sorted(counts.items())),
        "independent_whole_file_approvals": 0,
        "phase1_mapping_complete": False,
        "decision": "FAIL_INCOMPLETE",
        "limitations": ["Full ordered source diff is not a compiled ABI proof",
                        "No independent whole-file semantic approval",
                        "No Phase 2 or runtime/editor compatibility certification"],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Phase 1 v7: %d pinned blobs, %d typed edges, %d negative controls; "
          "14,834 records, 338 P0, 41 pending, 0 approved; FAIL_INCOMPLETE" %
          (len(BLOBS), len(EDGES), negatives))

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Phase 1 v7 FAILED:", error, file=sys.stderr)
        sys.exit(2)
