#!/usr/bin/env python3
"""Phase 1 pinned FireRed root-build contract; no ROM build or approval."""
import argparse
import hashlib
import re
import subprocess
from pathlib import Path

PIN = 'ce6406d8c2eaf46d543c8a2606de0c3cb1951982'
BLOBS = {
    'Makefile': '8b454dbd18eb0069fa5851d788697190890a5b37',
    'config.mk': 'c07d31fc083fa341cca29c340e560ed107d5364a',
    'make_tools.mk': 'd7b9315ad7beb37116793d8f805160679d3b4001',
    'ld_script.ld': '9a4b45031e93c1e1da8186d8c697332710526048',
    'ld_script_rev10.ld': '4eb3bc2eec749437be5797202442188972ac0693',
    'ld_script_modern.ld': 'e930243522bd21da40cc1a05de9a42b8ad409b46',
}
def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args]).strip()
def blob_hash(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
def read_sources(root):
    assert git(root, 'rev-parse', 'HEAD').decode() == PIN, 'pinned checkout changed'
    out = {}
    for path, expected in BLOBS.items():
        assert git(root, 'rev-parse', 'HEAD:' + path).decode() == expected, path + ': tree identity changed'
        data = subprocess.check_output(['git', '-C', str(root), 'cat-file', 'blob', expected])
        assert blob_hash(data) == expected, path + ': content identity changed'
        out[path] = data.decode('utf-8')
    return out
def has(text, expression):
    assert re.search(expression, text, re.M), 'missing source contract: ' + expression
def verify_contract(files):
    m, cfg, tools = files['Makefile'], files['config.mk'], files['make_tools.mk']
    for pattern in [r'^include config\.mk$', r'^ROM := poke\$\(BUILD_NAME\)\.gba$',
                    r'^ELF := \$\(ROM:\.gba=\.elf\)$', r'^ifeq \(\$\(MODERN\),0\)$',
                    r'^  CC1 := tools/agbcc/bin/agbcc\$\(EXE\)$',
                    r'^  MODERNCC := \$\(PREFIX\)gcc$', r'^include make_tools\.mk$',
                    r'^include map_data_rules\.mk$',
                    r'^\$\(ELF\): \$\(LD_SCRIPT\) \$\(LD_SCRIPT_DEPS\) \$\(OBJS\)$',
                    r'^\$\(ROM\): \$\(ELF\)$',
                    r'^\s*\$\(OBJCOPY\) -O binary --gap-fill 0xFF --pad-to 0x9000000 \$< \$@$']:
        has(m, pattern)
    for pattern in [r'^GAME_VERSION\s+\?= FIRERED$', r'^GAME_REVISION \?= 0$',
                    r'^MODERN\s+\?= 0$', r'^COMPARE\s+\?= 0$',
                    r'^  GAME_CODE\s+:= BPR$', r'^  GAME_CODE\s+:= BPG$',
                    r'^  GAME_CODE\s+:= \$\(GAME_CODE\)E$']:
        has(cfg, pattern)
    has(tools, r'^TOOL_NAMES := bin2c gbafix gbagfx jsonproc mapjson mid2agb preproc ramscrgen rsfont scaninc wav2agb$')
    has(m, r'ifeq \(\$\(MODERN\),0\)\nifeq \(\$\(GAME_REVISION\),10\)\nLD_SCRIPT := ld_script_rev10\.ld')
    has(m, r'else\nLD_SCRIPT := ld_script\.ld')
    has(m, r'else\nLD_SCRIPT := ld_script_modern\.ld')
    for path in ('ld_script.ld', 'ld_script_rev10.ld', 'ld_script_modern.ld'):
        has(files[path], r'^\s*ROM\s+\(rx\)\s*:\s*ORIGIN = 0x8000000, LENGTH = 32M$')
    has(m, r'^\s*\$\(FIX\) \$@ -t"\$\(TITLE\)" -c\$\(GAME_CODE\) -m\$\(MAKER_CODE\) -r\$\(GAME_REVISION\) --silent$')
    pad_to = int(re.search(r'--pad-to (0x[0-9a-fA-F]+)', m).group(1), 16)
    origin = int(re.search(r'ORIGIN = (0x[0-9a-fA-F]+)', files['ld_script_modern.ld']).group(1), 16)
    assert pad_to - origin == 16 * 1024 * 1024
    return {'pad_target': hex(pad_to), 'rom_origin': hex(origin),
            'minimum_binary_span_from_pad': pad_to - origin,
            'linker_rom_region_bytes': 32 * 1024 * 1024}
def negative_controls(files):
    mutations = [
        ('Makefile', '--pad-to 0x9000000', '--pad-to 0xA000000'),
        ('Makefile', 'LD_SCRIPT := ld_script_modern.ld', 'LD_SCRIPT := ld_script_rev10.ld'),
        ('Makefile', 'include map_data_rules.mk', 'include map_data_rules_DISABLED.mk'),
        ('config.mk', 'MODERN        ?= 0', 'MODERN        ?= 1'),
        ('ld_script_modern.ld', 'LENGTH = 32M', 'LENGTH = 64M'),
    ]
    for path, before, after in mutations:
        assert before in files[path], 'invalid negative fixture: ' + path
        altered = dict(files)
        altered[path] = altered[path].replace(before, after, 1)
        try:
            verify_contract(altered)
        except AssertionError:
            continue
        raise AssertionError('negative fixture accepted: ' + path + ' ' + before)
    assert blob_hash(b'changed') != BLOBS['Makefile']
    return len(mutations) + 1
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--firered', type=Path, required=True)
    args = p.parse_args()
    files = read_sources(args.firered)
    result = verify_contract(files)
    n = negative_controls(files)
    print('PASS: 6 pinned Git blobs, build contracts, %d negative controls; %s' % (n, result))
    print('NOT PROVEN: ELF layout, ROM output length, emulator behavior, expanded memory, independent review')
if __name__ == '__main__':
    main()
