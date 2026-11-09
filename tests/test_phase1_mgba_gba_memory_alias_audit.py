import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import phase1_mgba_gba_memory_alias_audit as audit


class GBAMemoryAliasAuditTests(unittest.TestCase):
    def test_exact_pinned_source_identity_passes(self):
        data = b"pinned source\n"
        audit.verify_source_identity(data, audit._git_blob(data), audit._digest(data))

    def test_source_byte_mutation_fails_identity(self):
        original = b"address & (GBA_SIZE_EWRAM - 4)\n"
        changed = original.replace(b"- 4", b"- 3")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            audit.verify_source_identity(changed, audit._git_blob(original), audit._digest(original))

    def test_changed_alignment_mask_fails_anchor(self):
        original = b"address &= ~3;\n"
        audit.verify_anchor(original, 1, "address &= ~3;")
        changed = original.replace(b"~3", b"~1")
        with self.assertRaisesRegex(ValueError, "Missing pinned source anchor"):
            audit.verify_anchor(changed, 1, "address &= ~3;")

    def test_invalid_anchor_lines_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Missing pinned source anchor"):
            audit.verify_anchor(b"line\n", 0, "line")
        with self.assertRaisesRegex(ValueError, "Missing pinned source anchor"):
            audit.verify_anchor(b"line\n", 2, "line")

    def test_authoritative_gate_must_remain_incomplete(self):
        data = (ROOT / "semantic-snapshots/current/phase1_mapping_gate.json").read_bytes()
        audit.verify_gate(data)
        with self.assertRaisesRegex(ValueError, "gate snapshot changed"):
            audit.verify_gate(data + b"\n")

    def test_probe_uses_pinned_objects_and_real_allocator(self):
        source = (ROOT / "tests/phase1_mgba_memory_object_probe.c").read_text()
        self.assertIn("#include <mgba/internal/gba/video.h>", source)
        self.assertIn("#include <mgba/internal/arm/macros.h>", source)
        self.assertIn("anonymousMemoryMap(GBA_SIZE_VRAM)", source)
        self.assertIn("LOAD_32(biosWord, 0, hleBios)", source)
        verifier = (ROOT / "tools/phase1_mgba_gba_memory_alias_audit.py").read_text()
        self.assertIn('str(generated_include)', verifier)


if __name__ == "__main__":
    unittest.main()
