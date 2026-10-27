#!/usr/bin/env python3
"""Phase 1 source-backed, mock-VFile C witness. NOT mGBA runtime certification."""
import argparse
import hashlib
import importlib.util
import re
import subprocess
import tempfile
from pathlib import Path

MEMORY_H = 'include/mgba/internal/gba/memory.h'
MEMORY_BLOB = '0aad912613e726560d06bbdbf6061986e69e5842'
NAMES = ('GBA_SIZE_FLASH512', 'GBA_SIZE_FLASH1M', 'GBA_SIZE_EEPROM512', 'GBA_SIZE_EEPROM')
FUNCTIONS = ('GBASavedataInitFlash', 'GBASavedataInitEEPROM')


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def read_constants(data):
    if blob_sha(data) != MEMORY_BLOB:
        raise ValueError('Pinned memory.h Git blob identity mismatch')
    s = data.decode('utf-8')
    values = {}
    for name in NAMES:
        matches = re.findall(r'^\s*' + re.escape(name) + r'\s*=\s*(0x[0-9a-fA-F]+|[0-9]+)\s*,', s, re.M)
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous memory constant: ' + name)
        values[name] = int(matches[0], 0)
    if values != dict(GBA_SIZE_FLASH512=65536, GBA_SIZE_FLASH1M=131072,
                      GBA_SIZE_EEPROM512=512, GBA_SIZE_EEPROM=8192):
        raise ValueError('Unexpected save memory dimensions')
    return values


def extract_function(source, name):
    pattern = r'(?m)^void\s+' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{'
    matches = list(re.finditer(pattern, source))
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous function body: ' + name)
    start = matches[0].start()
    brace = source.find('{', matches[0].start(), matches[0].end())
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise ValueError('Unbalanced function body: ' + name)


def source_bodies(data):
    s = data.decode('utf-8')
    bodies = [extract_function(s, name) for name in FUNCTIONS]
    anchors = (
        'if (end < flashSize)',
        'if (end < GBA_SIZE_FLASH512)',
        'memset(&savedata->data[end], 0xFF, flashSize - end);',
        'if (end < eepromSize)',
        'if (end < GBA_SIZE_EEPROM512)',
        'memset(&savedata->data[end], 0xFF, GBA_SIZE_EEPROM512 - end);',
    )
    joined = '\n'.join(bodies)
    if any(joined.count(anchor) != 1 for anchor in anchors):
        raise ValueError('Source branch/erasure anchor drift')
    return bodies


PRELUDE = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>

enum { GBA_SAVEDATA_AUTODETECT, GBA_SAVEDATA_FLASH512, GBA_SAVEDATA_FLASH1M,
       GBA_SAVEDATA_EEPROM512, GBA_SAVEDATA_EEPROM };
#define mLOG(...) ((void)0)
#define mCALLBACKS_INVOKE(...) ((void)0)
struct VFile {
    off_t (*size)(struct VFile*);
    void (*truncate)(struct VFile*, size_t);
    void* (*map)(struct VFile*, size_t, int);
};
struct GBASavedata {
    int type;
    struct VFile* vf;
    uint8_t* data;
    uint8_t* currentBank;
    int mapMode;
    void* p;
};
static uint8_t anonymous[131072];
static void* anonymousMemoryMap(size_t size) {
    assert(size <= sizeof(anonymous));
    memset(anonymous, 0, size);
    return anonymous;
}
struct MockFile {
    struct VFile vf;
    uint8_t data[131072];
    off_t length;
    int truncations;
};
static off_t mock_size(struct VFile* vf) {
    return ((struct MockFile*)vf)->length;
}
static void mock_truncate(struct VFile* vf, size_t length) {
    struct MockFile* m = (struct MockFile*)vf;
    assert(length <= sizeof(m->data));
    if ((off_t)length > m->length) {
        memset(m->data + m->length, 0, length - (size_t)m->length);
    }
    m->length = (off_t)length;
    m->truncations++;
}
static void* mock_map(struct VFile* vf, size_t length, int mode) {
    struct MockFile* m = (struct MockFile*)vf;
    (void)mode;
    assert(length <= sizeof(m->data));
    return m->data;
}
static void setup(struct MockFile* m, size_t length) {
    assert(length <= sizeof(m->data));
    memset(m, 0, sizeof(*m));
    m->vf.size = mock_size;
    m->vf.truncate = mock_truncate;
    m->vf.map = mock_map;
    m->length = (off_t)length;
    memset(m->data, 0xA5, length);
}
static void expect_range(const uint8_t* data, size_t lo, size_t hi, uint8_t value) {
    for (size_t i = lo; i < hi; ++i) assert(data[i] == value);
}
'''

TESTS = r'''
int main(void) {
    struct MockFile f;
    struct GBASavedata s;
    memset(&s, 0, sizeof(s));
    setup(&f, GBA_SIZE_FLASH512);
    s.vf = &f.vf; s.type = GBA_SAVEDATA_FLASH1M;
    GBASavedataInitFlash(&s);
    assert(f.length == GBA_SIZE_FLASH1M && f.truncations == 1);
    expect_range(f.data, 0, GBA_SIZE_FLASH512, 0xA5);
    expect_range(f.data, GBA_SIZE_FLASH512, GBA_SIZE_FLASH1M, 0x00);
    puts("FLASH1M existing-64KiB: grown upper bank remains mock-backend zero, not explicitly 0xFF");

    setup(&f, 0); memset(&s, 0, sizeof(s));
    s.vf = &f.vf; s.type = GBA_SAVEDATA_FLASH1M;
    GBASavedataInitFlash(&s);
    expect_range(f.data, 0, GBA_SIZE_FLASH1M, 0xFF);
    puts("FLASH1M empty file: entire requested range explicitly 0xFF");

    setup(&f, GBA_SIZE_EEPROM512); memset(&s, 0, sizeof(s));
    s.vf = &f.vf; s.type = GBA_SAVEDATA_EEPROM;
    GBASavedataInitEEPROM(&s);
    assert(f.length == GBA_SIZE_EEPROM && f.truncations == 1);
    expect_range(f.data, 0, GBA_SIZE_EEPROM512, 0xA5);
    expect_range(f.data, GBA_SIZE_EEPROM512, GBA_SIZE_EEPROM, 0x00);
    puts("EEPROM8KiB existing-512B: grown upper range remains mock-backend zero");

    setup(&f, 0); memset(&s, 0, sizeof(s));
    s.vf = &f.vf; s.type = GBA_SAVEDATA_EEPROM;
    GBASavedataInitEEPROM(&s);
    expect_range(f.data, 0, GBA_SIZE_EEPROM512, 0xFF);
    expect_range(f.data, GBA_SIZE_EEPROM512, GBA_SIZE_EEPROM, 0x00);
    puts("EEPROM8KiB empty file: only first 512 bytes explicitly 0xFF");

    memset(&s, 0, sizeof(s)); s.type = GBA_SAVEDATA_EEPROM;
    GBASavedataInitEEPROM(&s);
    expect_range(s.data, 0, GBA_SIZE_EEPROM512, 0xFF);
    expect_range(s.data, GBA_SIZE_EEPROM512, GBA_SIZE_EEPROM, 0x00);
    puts("EEPROM8KiB anonymous zero-map: only first 512 bytes explicitly 0xFF");

    setup(&f, 0); memset(&s, 0, sizeof(s));
    s.vf = &f.vf; s.type = GBA_SAVEDATA_EEPROM512;
    GBASavedataInitEEPROM(&s);
    expect_range(f.data, 0, GBA_SIZE_EEPROM512, 0xFF);
    puts("EEPROM512 empty file: entire requested 512-byte range explicitly 0xFF");
    return 0;
}
'''


def compile_witness(bodies, constants, compiler='cc'):
    constants_c = '\n'.join(f'#define {name} {value}' for name, value in constants.items())
    code = PRELUDE + '\n' + constants_c + '\n' + '\n\n'.join(bodies) + '\n' + TESTS
    with tempfile.TemporaryDirectory(prefix='xgba-phase1-savedata-') as directory:
        source = Path(directory) / 'witness.c'
        binary = Path(directory) / 'witness'
        source.write_text(code)
        subprocess.run([compiler, '-std=c11', '-O0', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', str(source), '-o', str(binary)], check=True)
        return subprocess.check_output([str(binary)], text=True)


def negative_controls(data):
    count = 0
    for old, new in (
        (b'if (end < GBA_SIZE_EEPROM512)', b'if (end <= GBA_SIZE_EEPROM512)'),
        (b'if (end < GBA_SIZE_FLASH512)', b'if (end <= GBA_SIZE_FLASH512)'),
        (b'memset(&savedata->data[end], 0xFF, GBA_SIZE_EEPROM512 - end);',
         b'memset(&savedata->data[end], 0, GBA_SIZE_EEPROM512 - end);'),
    ):
        assert data.count(old) == 1
        try:
            source_bodies(data.replace(old, new, 1))
        except ValueError:
            count += 1
        else:
            raise AssertionError('Mutation passed fail-closed source anchors')
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--compiler', default='cc')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('savedata_checker', Path(__file__).with_name('phase1_mgba_savedata_handoff_verify.py'))
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    pinned = checker.verify_checkout(args.checkout)
    memory = subprocess.check_output(['git', '-C', str(args.checkout), 'cat-file', 'blob', MEMORY_BLOB])
    tree_sha = subprocess.check_output(['git', '-C', str(args.checkout), 'rev-parse', 'HEAD:' + MEMORY_H], text=True).strip()
    if tree_sha != MEMORY_BLOB:
        raise ValueError('Pinned tree memory.h identity mismatch')
    constants = read_constants(memory)
    data = pinned['src/gba/savedata.c']
    bodies = source_bodies(data)
    print(compile_witness(bodies, constants, args.compiler), end='')
    print(f'PASS: six mock-VFile witnesses, {negative_controls(data)} mutation controls; zero independent approvals')


if __name__ == '__main__':
    main()
