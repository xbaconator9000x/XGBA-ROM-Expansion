#!/usr/bin/env python3
"""Reuse existing pinned CLI and GNU ARM table compiler, export its 32 bytes."""
import argparse
import hashlib
import subprocess
import tempfile
from pathlib import Path
from verify_poryscript_actual_cli_arm_table import (
    PORY, EXPECTED_LINKED, macro, compile_assembly, validate, PS_PIN, FR_PIN
)
def need(ok,msg):
    if not ok: raise ValueError(msg)
def git(root,*args):
    return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--poryscript",type=Path,required=True)
    p.add_argument("--firered",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    ps=a.poryscript.resolve(); fr=a.firered.resolve()
    need(git(ps,"rev-parse","HEAD")==PS_PIN,"Poryscript pin")
    need(git(fr,"rev-parse","HEAD")==FR_PIN,"FireRed pin")
    need(git(fr,"hash-object","asm/macros/map.inc")==
         "83ef472c926ce767c9133ab9bd6922280b38bb2d","map macro blob")
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        (root/"input.pory").write_text(PORY)
        subprocess.run(["go","build","-o",str(root/"poryscript"),"."],cwd=ps,check=True)
        emitted=subprocess.check_output([
            str(root/"poryscript"),"-cc","","-fc","","-lm=false",
            "-optimize=true","-i",str(root/"input.pory")],cwd=ps,text=True)
        src=(fr/"asm/macros/map.inc").read_text()
        preamble="\n".join([
            ".syntax unified",macro(src,"map_script"),macro(src,"map_script_2"),
            ".equ MAP_SCRIPT_ON_TRANSITION, 3",
            ".equ MAP_SCRIPT_ON_FRAME_TABLE, 2",
            '.section .rodata,"a",%progbits',""])
        subprocess.run(["make","-C",str(fr/"tools/preproc"),"-j2"],check=True)
        result=compile_assembly(preamble+emitted,root,
                                fr/"tools/preproc/preproc",fr/"charmap.txt")
        validate(result)
        need(result["linked"]==EXPECTED_LINKED,"CLI table bytes drift")
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_bytes(result["linked"])
        print("PINNED_CLI_TABLE_EXPORT_PASS sha256="+hashlib.sha256(result["linked"]).hexdigest())
if __name__=="__main__":
    main()
