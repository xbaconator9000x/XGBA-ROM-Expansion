#!/usr/bin/env python3
"""Phase 1: execute the pinned Poryscript documented generated-.inc Make rule.

Uses original Porymap default map-script text, original Poryscript CLI and
documented Make rule, and GNU ARM assembler. No replacement script compiler,
upstream patch, full ROM build, editor GUI, or mGBA runtime is claimed.
"""
import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

PINS = {
    "porymap": ("26b919d7ff4b54152de010abd5bf344af2ebe116",
                {"src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13"}),
    "poryscript": ("c32481161c767b25a3425fa9f1f8729927ff3d55",
                   {"README.md": "c77e022eb86e74a41b184daac5953d14c72cacc3",
                    "LICENSE.md": "bc574ff56a7df993996053c7b2afec43e80bdd64"}),
    "firered": ("ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
                {"Makefile": "8b454dbd18eb0069fa5851d788697190890a5b37",
                 "tools/preproc/preproc.cpp": "20c2de51b635a5d59f2b4e1ecd93d8fc2748ebe1"}),
}
TARGET_LINE = "AUTO_GEN_TARGETS += $(patsubst %.pory,%.inc,$(shell find data/ -type f -name '*.pory'))"
RULE_LINE = "data/%.inc: data/%.pory; $(SCRIPT) -i $< -o $@ -fc tools/poryscript/font_config.json -cc tools/poryscript/command_config.json"

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def command(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)

def pin(root, name):
    commit, blobs = PINS[name]
    result = command(["git", "-C", str(root), "rev-parse", "HEAD"])
    require(result.returncode == 0 and result.stdout.strip() == commit, "upstream commit drift: " + name)
    out = {}
    for path, expected in blobs.items():
        blob = command(["git", "-C", str(root), "hash-object", path])
        require(blob.returncode == 0 and blob.stdout.strip() == expected, "upstream blob drift: " + name + "/" + path)
        out[path] = (root / path).read_text()
    return out

def contract(pm, ps, fr):
    require('return QString("mapscripts %1_MapScripts {}\\n").arg(mapName);' in pm,
            "pinned Porymap default Poryscript text changed")
    require('saveTextFile(fullPath + "/scripts" + this->getScriptFileExtension(projectConfig.usePoryScript), text);' in pm,
            "Porymap new-map script creation changed")
    require('return ".pory";' in pm, "Porymap .pory extension changed")
    save_start = pm.index("bool Project::saveMap(")
    save_end = pm.find("\n}\n", save_start)
    require(save_end > save_start, "Porymap saveMap boundary changed")
    save_body = pm[save_start:save_end]
    include_start = save_body.index("text = QString(")
    require('scripts.inc' in save_body[include_start:include_start + 120] and
            'appendTextFile(root + "/"' in save_body,
            "Porymap event_scripts.s include changed")
    require(ps.count(TARGET_LINE) == 1 and ps.count(RULE_LINE) == 1,
            "pinned documented Poryscript Make rule changed")
    require("generated: $(AUTO_GEN_TARGETS)" in ps, "Poryscript documented generated target changed")
    require("AUTO_GEN_TARGETS :=" in fr and "generated: $(AUTO_GEN_TARGETS)" in fr,
            "FireRed original generated target changed")
    require("poryscript" not in fr.lower() and ".pory" not in fr.lower(),
            "FireRed already has a Poryscript rule; review changed")
    return True

def negatives(pm, ps, fr):
    changes = (
        (0, 'mapscripts %1_MapScripts {}', 'script %1_MapScripts {}'),
        (0, 'return ".pory";', 'return ".inc";'),
        (0, 'scripts.inc', 'scripts.pory'),
        (1, TARGET_LINE, 'AUTO_GEN_TARGETS += missing-target'),
        (1, RULE_LINE, RULE_LINE.replace("-o $@", "-x $@")),
        (1, "generated: $(AUTO_GEN_TARGETS)", "generated:"),
        (2, "AUTO_GEN_TARGETS :=", "AUTO_GEN_TARGETS += "),
        (2, "generated: $(AUTO_GEN_TARGETS)", "generated:"),
    )
    for index, (which, old, new) in enumerate(changes):
        sources = [pm, ps, fr]
        require(old in sources[which], "missing mutation anchor " + str(index))
        if index == 2:
            start = sources[0].index("bool Project::saveMap(")
            before, after = sources[0][:start], sources[0][start:]
            include_start = after.index("text = QString(")
            prefix, include_tail = after[:include_start], after[include_start:]
            require(old in include_tail[:120], "missing saveMap include mutation anchor")
            sources[0] = before + prefix + include_tail.replace(old, new, 1)
        else:
            sources[which] = sources[which].replace(old, new, 1)
        try:
            contract(*sources)
        except ValueError:
            continue
        raise ValueError("source mutation escaped " + str(index))
    return len(changes)

def main():
    ap = argparse.ArgumentParser()
    for name in PINS:
        ap.add_argument("--" + name, required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    sources = {name: pin(getattr(args, name).resolve(), name) for name in PINS}
    pm = sources["porymap"]["src/project.cpp"]
    ps = sources["poryscript"]["README.md"]
    fr = sources["firered"]["Makefile"]
    contract(pm, ps, fr)
    require("case Directive::Include:" in sources["firered"]["tools/preproc/preproc.cpp"] and
            "GetGlobalLabel()" in sources["firered"]["tools/preproc/preproc.cpp"],
            "FireRed original include/global-label preprocessor contract changed")
    source_negative_count = negatives(pm, ps, fr)
    for exe in ("go", "make", "arm-none-eabi-as", "arm-none-eabi-nm"):
        require(shutil.which(exe) is not None, "missing original tool: " + exe)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        cli_dir = root / "tools/poryscript"
        cli_dir.mkdir(parents=True)
        cli = cli_dir / "poryscript"
        build = command(["go", "build", "-o", str(cli), "."], cwd=args.poryscript.resolve())
        require(build.returncode == 0, "pinned Poryscript build failed: " + build.stderr[-2000:])
        for filename in ("font_config.json", "command_config.json"):
            shutil.copyfile(args.poryscript.resolve() / filename, cli_dir / filename)
        maps = root / "data/maps/XGBAProbe"
        maps.mkdir(parents=True)
        source = maps / "scripts.pory"
        original = "mapscripts XGBAProbe_MapScripts {}\n"
        source.write_text(original)
        # The exact documented pattern rule is used, not a new compiler or exporter.
        makefile = "\n".join((
            "SCRIPT := tools/poryscript/poryscript",
            "AUTO_GEN_TARGETS :=",
            TARGET_LINE,
            "generated: $(AUTO_GEN_TARGETS)",
            "%.pory: ;",
            RULE_LINE,
            "",
        ))
        (root / "Makefile").write_text(makefile)
        generated = maps / "scripts.inc"
        first = command(["make", "-rR", "generated"], cwd=root)
        require(first.returncode == 0, "documented Make rule failed: " + first.stderr[-3000:])
        require(generated.is_file(), "Poryscript .inc target not generated")
        content = generated.read_bytes()
        require(len(content) > 0 and b"XGBAProbe_MapScripts" in content,
                "generated map script symbol missing")
        # Prove the existing FireRed include can consume the generated file.
        event = root / "data/event_scripts.s"
        event.write_text('.include "data/maps/XGBAProbe/scripts.inc"\n')
        obj = root / "event_scripts.o"
        # A direct GNU as invocation is deliberately not the FireRed pipeline:
        # Poryscript emits :: labels and the original preproc expands includes
        # and translates them before CPP and GNU ARM assembly.
        direct = command(["arm-none-eabi-as", "-mcpu=arm7tdmi", "-I", ".", "-o",
                          str(root / "direct.o"), str(event)], cwd=root)
        require(direct.returncode != 0, "direct GNU as unexpectedly accepted original :: labels")
        firered = args.firered.resolve()
        built_preproc = command(["make", "-C", str(firered / "tools/preproc"), "-j2"])
        require(built_preproc.returncode == 0,
                "original FireRed preproc build failed: " + built_preproc.stderr[-3000:])
        preproc = firered / "tools/preproc/preproc"
        require(preproc.is_file(), "original FireRed preproc binary missing")
        ch = firered / "charmap.txt"
        command_line = (" ".join(shlex.quote(str(x)) for x in (preproc, event, ch)) +
                        " | cc -E -I " + shlex.quote(str(firered / "include")) + " -" +
                        " | " + " ".join(shlex.quote(str(x)) for x in (preproc, "-ie", event, ch)) +
                        " | arm-none-eabi-as -mcpu=arm7tdmi --defsym FIRERED=1" +
                        " --defsym REVISION=0 --defsym ENGLISH=1 --defsym MODERN=0" +
                        " -o " + shlex.quote(str(obj)) + " -")
        assembled = command(["bash", "-o", "pipefail", "-c", command_line], cwd=root)
        require(assembled.returncode == 0,
                "original preproc/CPP/preproc/GNU ARM include consumption failed: " +
                assembled.stderr[-3000:])
        symbols = command(["arm-none-eabi-nm", str(obj)])
        require(symbols.returncode == 0 and "XGBAProbe_MapScripts" in symbols.stdout,
                "compiled event_scripts object missing generated symbol")
        dry = command(["make", "-rR", "-n", "generated"], cwd=root)
        require(dry.returncode == 0 and "poryscript -i" not in dry.stdout,
                "unchanged .pory unexpectedly regenerates")
        # Negative: without the documented rule, a fresh target must not build.
        (root / "Makefile").write_text("\n".join(makefile.splitlines()[:-2]) + "\n")
        generated.unlink()
        missing = command(["make", "-rR", "generated"], cwd=root)
        require(missing.returncode != 0, "missing .pory->.inc rule unexpectedly succeeded")
        (root / "Makefile").write_text(makefile)
        source.write_text("mapscripts Broken {\n")
        bad = command(["make", "-rR", "-B", "generated"], cwd=root)
        require(bad.returncode != 0, "malformed Poryscript source unexpectedly compiled")
        source.write_text(original)
        rebuilt = command(["make", "-rR", "-B", "generated"], cwd=root)
        require(rebuilt.returncode == 0 and generated.read_bytes() == content,
                "original Poryscript generation did not recover exact bytes")
        section_sha = hashlib.sha256(content).hexdigest()
        object_sha = hashlib.sha256(obj.read_bytes()).hexdigest()
    evidence = {
        "class": "PINNED_PORYMAP_PORYSCRIPT_NATIVE_GENERATED_INCLUDE_REUSE",
        "upstream_pins": {k: v[0] for k, v in PINS.items()},
        "source_blobs": {k: v[1] for k, v in PINS.items()},
        "poryscript_license": "MIT (retain copyright and permission notice)",
        "documented_make_rule_executed": True,
        "generated_inc_nonempty_and_symbol_present": True,
        "gnu_arm_consumed_generated_inc": True,
        "direct_gnu_as_without_original_preproc_rejected": True,
        "original_firered_preproc_built_and_reused": True,
        "no_change_make_dry_run_avoided_regeneration": True,
        "missing_rule_failed": True,
        "malformed_source_failed": True,
        "recovery_byte_identical": True,
        "generated_inc_sha256": section_sha,
        "gnu_arm_object_sha256": object_sha,
        "source_mutations_rejected": source_negative_count,
        "full_firered_rom_build_or_mgba_execution": False,
        "full_porymap_gui_new_map_executed": False,
        "upstream_modified": False,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    def validate(d):
        require(d["source_mutations_rejected"] == 8, "source negatives missing")
        for key in ("documented_make_rule_executed", "generated_inc_nonempty_and_symbol_present",
                    "gnu_arm_consumed_generated_inc", "direct_gnu_as_without_original_preproc_rejected",
                    "original_firered_preproc_built_and_reused", "no_change_make_dry_run_avoided_regeneration",
                    "missing_rule_failed", "malformed_source_failed", "recovery_byte_identical"):
            require(d[key] is True, "executable evidence missing: " + key)
        require(d["full_firered_rom_build_or_mgba_execution"] is False and
                d["full_porymap_gui_new_map_executed"] is False and
                d["upstream_modified"] is False, "scope overclaimed")
        require(d["independent_approvals"] == 0 and d["phase1_gate"] == "FAIL_INCOMPLETE",
                "false approval")
    validate(evidence)
    changes = [{"source_mutations_rejected": 7}, {"documented_make_rule_executed": False},
               {"generated_inc_nonempty_and_symbol_present": False},
               {"gnu_arm_consumed_generated_inc": False},
               {"direct_gnu_as_without_original_preproc_rejected": False},
               {"original_firered_preproc_built_and_reused": False},
               {"no_change_make_dry_run_avoided_regeneration": False},
               {"missing_rule_failed": False}, {"malformed_source_failed": False},
               {"recovery_byte_identical": False},
               {"full_firered_rom_build_or_mgba_execution": True},
               {"full_porymap_gui_new_map_executed": True},
               {"upstream_modified": True}, {"independent_approvals": 1},
               {"phase1_gate": "PASS"}]
    for i, change in enumerate(changes):
        try:
            validate({**evidence, **change})
        except ValueError:
            continue
        raise ValueError("evidence mutation escaped " + str(i))
    evidence["evidence_mutations_rejected"] = len(changes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()
