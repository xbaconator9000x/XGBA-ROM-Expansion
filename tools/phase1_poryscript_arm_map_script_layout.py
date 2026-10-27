#!/usr/bin/env python3
"""Pinned FireRed map-script macro layout in a standalone ARMv4T Clang object.

Not a linked FireRed build, original agbcc proof, or runtime/semantic approval.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PINNED_BLOB = '83ef472c926ce767c9133ab9bd6922280b38bb2d'
EXPECTED = bytes.fromhex('01 34 12 00 08 02 78 56 00 08 00 01 40 34 12 bc 9a 00 08 00 80 01 00 f0 de 00 08 00 00')


def macros_from_source(data):
    actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if actual != PINNED_BLOB:
        raise ValueError('Not the exact pinned FireRed asm/macros/map.inc blob')
    source = data.decode('utf-8')
    macros = []
    for name in ('map_script', 'map_script_2'):
        match = re.search(r'(?m)^\s*\.macro ' + name + r'\s+[^\n]*\n(?:.*\n)*?\s*\.endm\s*$', source)
        if not match:
            raise ValueError('Missing pinned macro ' + name)
        macros.append(match.group(0))
    return '\n'.join(macros)


def assemble(macros, clang='clang', readelf='readelf'):
    assembly = ('.syntax unified\n' + macros + '\n'
                '.section .rodata.map_script_test,"a",%progbits\n'
                'map_script_test:\n'
                'map_script 1, 0x08001234\n'
                'map_script 2, 0x08005678\n'
                '.byte 0\n'
                'map_script_table_test:\n'
                'map_script_2 0x4001, 0x1234, 0x08009abc\n'
                'map_script_2 0x8000, 0x0001, 0x0800def0\n'
                '.2byte 0\n')
    with tempfile.TemporaryDirectory() as tmp:
        src, obj = Path(tmp) / 'witness.s', Path(tmp) / 'witness.o'
        src.write_text(assembly)
        subprocess.run([clang, '-target', 'armv4t-none-eabi', '-c', str(src), '-o', str(obj)],
                       check=True, capture_output=True, text=True)
        dump = subprocess.check_output([readelf, '-x', '.rodata.map_script_test', str(obj)], text=True)
        version = subprocess.check_output([clang, '--version'], text=True).splitlines()[0]
    pieces = []
    for line in dump.splitlines():
        if not line.lstrip().startswith('0x'):
            continue
        words = line.split()
        for word in words[1:]:
            if re.fullmatch(r'[0-9a-fA-F]{2,8}', word) and len(word) % 2 == 0:
                pieces.append(bytes.fromhex(word))
            else:
                break
    return b''.join(pieces), version


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    macros = macros_from_source(a.source.read_bytes())
    observed, compiler = assemble(macros)
    if observed != EXPECTED:
        raise ValueError(f'ARM map-script layout mismatch: observed={observed.hex()} expected={EXPECTED.hex()}')
    try:
        changed, _ = assemble(macros.replace(r'.4byte \script', r'.2byte \script', 1))
    except subprocess.CalledProcessError:
        changed = None  # ARM assembler rejected truncated absolute pointer
    if changed == EXPECTED:
        raise ValueError('Negative pointer-width mutation escaped')
    report = {'schema': 'xgba-poryscript-arm-map-script-layout-v1',
              'source_repo': 'pret/pokefirered', 'source_commit': 'ce6406d8c2eaf46d543c8a2606de0c3cb1951982',
              'source_path': 'asm/macros/map.inc', 'source_git_blob_sha1': PINNED_BLOB,
              'compiler': compiler, 'target': 'armv4t-none-eabi',
              'section_bytes': len(observed), 'map_script_entries_plus_terminator': 11,
              'map_script_2_entries_plus_terminator': 18,
              'section_sha256': hashlib.sha256(observed).hexdigest(),
              'negative_pointer_width_mutation_rejected': True,
              'not_proven': ['original agbcc or GNU as equivalence', 'full FireRed linked ROM',
                             'Poryscript generated output round-trip', 'emulator execution',
                             'independent semantic approval'],
              'independent_approvals': 0, 'phase1_gate': 'FAIL_INCOMPLETE'}
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
