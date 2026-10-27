#!/usr/bin/env python3
"""Pinned FireRed dive-script fallback: source call-chain and authored-input audit.

Read-only and fail-closed. This proves a callable source path, not runtime
reachability for a particular map or a Qt/editor/ROM-byte result.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "types": ("include/constants/map_scripts.h", "1353de360cf1e00b6efbb26ec59c4822c99b59bf"),
    "script": ("src/script.c", "d0433bdda062b138e53d1a1d3184b4566ad7d9dc"),
    "overworld": ("src/overworld.c", "339014da46ae8543143edc99ab72bf7496203a0d"),
    "avatar": ("src/field_control_avatar.c", "b1b6465941133b927505be92d189a7c283e4722f"),
    "scrcmd": ("src/scrcmd.c", "97b695ee2f6fca80a3b78f52f6a444f696fe5814"),
    "eventmacro": ("asm/macros/event.inc", "142ad979d7d3093244087a247fa2b4883424f77f"),
    "cmdtable": ("data/script_cmd_table.inc", "c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1"),
}
CHECKS = {
    "reserved_type": ("types", "#define MAP_SCRIPT_ON_DIVE_WARP            6 // Unused"),
    "type6_reader": ("script", "MapHeaderRunScriptType(MAP_SCRIPT_ON_DIVE_WARP);"),
    "type6_wrapper": ("script", "void RunOnDiveWarpMapScript(void)"),
    "native_connection_first": ("overworld", "const struct MapConnection *connection = GetMapConnection(dir);"),
    "fallback_calls_script": ("overworld", "RunOnDiveWarpMapScript();"),
    "fallback_checks_dummy": ("overworld", "if (IsDummyWarp(&sFixedDiveWarp))"),
    "fallback_uses_destination": ("overworld", "SetWarpDestinationToDiveWarp();"),
    "reset_fixed_warp": ("overworld", "sFixedDiveWarp = sDummyWarpData;"),
    "emerge_entry": ("avatar", "if (SetDiveWarpEmerge(position->x - MAP_OFFSET, position->y - MAP_OFFSET))"),
    "dive_entry": ("avatar", "if (SetDiveWarpDive(position->x - MAP_OFFSET, position->y - MAP_OFFSET))"),
    "script_writes_warp": ("scrcmd", "SetFixedDiveWarp(mapGroup, mapNum, warpId, x, y);"),
    "script_command": ("scrcmd", "bool8 ScrCmd_setdivewarp(struct ScriptContext * ctx)"),
    "asm_opcode": ("eventmacro", ".macro setdivewarp map:req, a, b, c"),
    "dispatch_opcode": ("cmdtable", ".4byte ScrCmd_setdivewarp                    @ 0x40"),
}

def verify(s: dict[str, str]) -> None:
    for name, (key, needle) in CHECKS.items():
        if needle not in s[key]:
            raise ValueError("Missing pinned semantic anchor: " + name)
    w = s["overworld"]
    start = w.index("static bool8 SetDiveWarp(u8 dir, u16 x, u16 y)")
    stop = w.index("bool8 SetDiveWarpEmerge(", start)
    branch = w[start:stop]
    ordered = ["GetMapConnection(dir)", "if (connection != NULL)", "SetWarpDestination(",
               "else", "RunOnDiveWarpMapScript();", "if (IsDummyWarp(&sFixedDiveWarp))",
               "SetWarpDestinationToDiveWarp();"]
    pos = -1
    for item in ordered:
        nxt = branch.find(item, pos + 1)
        if nxt < 0:
            raise ValueError("Dive connection-first fallback ordering changed: " + item)
        pos = nxt
    script = s["script"]
    a = script.index("void RunOnDiveWarpMapScript(void)")
    b = script.index("bool8 TryRunOnFrameMapScript(void)", a)
    if "MapHeaderRunScriptType(MAP_SCRIPT_ON_DIVE_WARP);" not in script[a:b]:
        raise ValueError("Type-6 wrapper no longer dispatches")
    cmd = s["scrcmd"]
    a = cmd.index("bool8 ScrCmd_setdivewarp(struct ScriptContext * ctx)")
    b = cmd.index("bool8 ScrCmd_setholewarp(", a)
    if "SetFixedDiveWarp(mapGroup, mapNum, warpId, x, y);" not in cmd[a:b]:
        raise ValueError("Script command no longer sets fixed warp")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--firered", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("phase1-evidence/firered-dive-fallback.json"))
    args = ap.parse_args()
    root = args.firered
    def git(*a):
        return subprocess.check_output(["git", "-C", str(root), *a], text=True).strip()
    if git("rev-parse", "HEAD") != PIN:
        raise ValueError("Wrong FireRed pinned commit")
    sources = {}
    for key, (path, sha) in BLOBS.items():
        actual = git("hash-object", path)
        if actual != sha:
            raise ValueError(f"Wrong pinned Git blob {path}: {actual}")
        sources[key] = (root / path).read_text(encoding="utf-8")
    verify(sources)
    negative = []
    for name, (key, needle) in CHECKS.items():
        mutated = dict(sources)
        mutated[key] = mutated[key].replace(needle, "", 1)
        try:
            verify(mutated)
        except ValueError:
            negative.append(name)
        else:
            raise AssertionError("Mutation not rejected: " + name)

    # Exact pinned authored symbolic references, not proof of absence of
    # raw numeric type-6 tables or of runtime reachability.
    authored = sorted((root / "data/maps").glob("*/scripts.inc"))
    symbolic = [str(p.relative_to(root)) for p in authored
                if "MAP_SCRIPT_ON_DIVE_WARP" in p.read_text(encoding="utf-8")]
    if symbolic:
        raise ValueError("Authored type-6 symbolic scripts need new disposition: " + repr(symbolic))
    result = {
        "status": "SOURCE_CALL_CHAIN_ONLY_NOT_APPROVED",
        "pin": PIN,
        "blob_count": len(BLOBS),
        "anchors": len(CHECKS),
        "negative_controls_passed": len(negative),
        "authored_map_scripts_scanned": len(authored),
        "symbolic_type6_authored_files": symbolic,
        "type6_fallback_source_callable": True,
        "type6_current_authored_runtime_reachability": "NOT_PROVEN",
        "compiled_or_runtime_executed": False,
        "independent_approvals": 0,
        "phase1": "FAIL_INCOMPLETE",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
