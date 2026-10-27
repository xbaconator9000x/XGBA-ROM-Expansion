#!/usr/bin/env python3
"""Negative and positive controls for binary-aware machine triage."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location("triage",Path(__file__).with_name("phase1_bulk_triage.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
png=b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+b'\x00'*8+b' EEPROM SaveSector'
gba=b'\x00'*192+b'EEPROM\x00SaveSector\x00'
for name,data,kind in [('image.png',png,'image_png'),('game.gba',gba,'compiled_rom'),('map.bin',b'\x00EEPROM\x00','opaque_binary'),('bad.png',b'not a png EEPROM','unknown_binary'),('unknown.dat',b'\x00EEPROM','unknown_binary')]:
    result=m.typed_structure(name,data)
    assert result['file_kind']==kind,(name,result['file_kind'])
    assert result['source_lines'] is None and not result['risk_flags_line_anchors']
    assert result['whole_blob_sha256']==m.digest(data)
text=b'#include "gba.h"\n#ifdef SAVE\nEEPROM\n#endif\n'
r=m.typed_structure('source.h',text)
assert r['file_kind']=='text_source'
assert r['source_lines']==4 and r['includes'][0]['include']=='gba.h'
assert r['risk_flags_line_anchors']['save_state']==[3]
assert r['conditional_directive_lines']==[2,4]
print('PASS: binary-kind suppression, unknown fail-closed, text anchors, hashes')
