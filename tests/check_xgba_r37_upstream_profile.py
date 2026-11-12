#!/usr/bin/env python3
"""Anchor R37 opcode numbers and critical operand lengths to pinned pret/pokeemerald.

No Nintendo binaries or extracted ROM bytes are required or published.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import xgba_r37_script_graph as r37

PIN='731ad5bfd6e6f265508d0efcca0ba42f9dcf5881'


def validate(source):
    root=Path(source)
    table=(root/'data/script_cmd_table.inc').read_text()
    macro=(root/'asm/macros/event.inc').read_text()
    entries={}
    for m in re.finditer(r'script_cmd_table_entry\s+SCR_OP_\w+\s+(ScrCmd_\w+)\s+@\s+0x([0-9a-fA-F]+)',table):
        n=int(m.group(2),16)
        if n in entries:raise ValueError('Duplicate original opcode')
        entries[n]=m.group(1)
    if len(entries)<220:raise ValueError('Incomplete pinned original command table')
    for n,spec in r37.SPECS.items():
        expected='ScrCmd_'+spec['name']
        if entries.get(n)!=expected:
            raise ValueError(f'R37 opcode 0x{n:02x} drifted: expected {expected}; original has {entries.get(n)}')
    macros={}
    lines=macro.splitlines()
    for i,line in enumerate(lines):
        found=re.match(r'\s*\.macro\s+(\w+)(?:\s|$)',line)
        if not found:continue
        key=found.group(1)
        if key not in macros:
            end=next((j for j in range(i+1,len(lines)) if '.endm' in lines[j]),None)
            if end is None:raise ValueError('Malformed macro source')
            macros[key]='\n'.join(lines[i:end+1])
    critical=('nop','nop1','end','return','call','goto','goto_if','call_if',
              'loadword','loadbyte','copylocal','setvar','addvar','subvar','copyvar',
              'setorcopyvar','compare_var_to_value','compare_var_to_var',
              'special','specialvar','delay','setflag','clearflag','checkflag',
              'additem','removeitem','checkitemspace','checkitem',
              'lockall','lock','releaseall','release','message')
    confirmed=[]
    for key in critical:
        spec=next((x for x in r37.SPECS.values() if x['name']==key),None)
        if spec is None or key not in macros:raise ValueError('Missing critical original macro '+key)
        # These critical macros have exactly one direct bytecode definition;
        # comments/branches which emit subsidiary macros are not included.
        emitted=re.findall(r'^\s*\.(byte|2byte|4byte)\s',macros[key],re.M)
        actual=sum({'byte':1,'2byte':2,'4byte':4}[x] for x in emitted)
        want=1+sum(r37.FORMATS[c][0] for c in spec['fmt'])
        if actual!=want:
            raise ValueError(f'Original macro {key}: {actual} emitted bytes vs R37 {want}')
        confirmed.append(key)
    return len(entries),len(r37.SPECS),len(confirmed)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',required=True)
    a=ap.parse_args()
    n,recognized,critical=validate(a.source)
    print(f'PASS_R37_UPSTREAM_EMERALD_OPCODE_PROFILE table_entries={n} supported={recognized} critical_macro_lengths={critical} pin={PIN}')

if __name__=='__main__':main()
