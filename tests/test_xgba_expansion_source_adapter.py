"""Source-safe regression tests for the RHH Emerald/FireRed/LeafGreen adapter."""
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import xgba_expansion_source_adapter as adapter

MAIN = (
    '#include "global.h"\n'
    'EWRAM_DATA unsigned char sTestBuffer[1];\n'
    'void AgbMain(void)\n'
    '{\n'
    '    InitHeap(gHeap, HEAP_SIZE);\n'
    '    gSoftResetDisabled = FALSE;\n'
    '}\n'
    'void AgbMainLoop(void)\n'
    '{\n'
    '    for (;;) {\n'
    '    ReadKeys();\n'
    '    }\n'
    '}\n'
)
MAKEFILE = (
    'GAME_VERSION ?= EMERALD\n'
    'GAME_VERSION := FIRERED\n'
    'GAME_VERSION := LEAFGREEN\n'
    'emerald: all\n'
    'firered: all\n'
    'leafgreen: all\n'
)


class ExpansionSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "include").mkdir()
        (self.root / "Makefile").write_text(MAKEFILE)
        (self.root / "src/main.c").write_text(MAIN)
        (self.root / "include/global.h").write_text("/* RHH global ABI */\n")

    def test_all_three_upstream_targets_checked(self):
        for target in adapter.TARGETS:
            with self.subTest(target=target):
                report = adapter.validate_source(self.root, target)
                self.assertEqual(report["target"], target)
                self.assertFalse(report["runtime_gameplay_verified"])
                self.assertEqual(report["guest_mmio_abi"], 1)

    def test_reversible_patch_restores_upstream_even_after_failure(self):
        file = self.root / "src/main.c"
        for target in adapter.TARGETS:
            with self.subTest(target=target):
                with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                    with adapter.patched_source(self.root, target):
                        patched = file.read_text()
                        self.assertEqual(patched.count("XgbaExpansionProbeBoot();"), 1)
                        self.assertEqual(patched.count("XgbaExpansionProbeTick();"), 1)
                        self.assertIn("XGBA_EXPANSION_RESOURCE_ID", patched)
                        self.assertIn("InitHeap(gHeap, XGBA_EXPANSION_HEAP_BYTES);", patched)
                        self.assertNotIn("InitHeap(gHeap, HEAP_SIZE);", patched)
                        self.assertIn("xgba_guest.h", patched)
                        raise RuntimeError("synthetic failure")
                self.assertEqual(file.read_text(), MAIN)

    def test_rejects_missing_game_target_or_build_matrix(self):
        with self.assertRaises(adapter.ExpansionDrift):
            adapter.validate_source(self.root, "ruby")
        (self.root / "Makefile").write_text(MAKEFILE.replace("firered: all", ""))
        with self.assertRaisesRegex(adapter.ExpansionDrift, "build matrix"):
            adapter.validate_source(self.root, "emerald")

    def test_rejects_source_drift_instead_of_wrong_hook(self):
        file = self.root / "src/main.c"
        file.write_text(MAIN.replace("InitHeap(gHeap, HEAP_SIZE);", "InitHeapEx();"))
        with self.assertRaisesRegex(adapter.ExpansionDrift, "main ABI drift"):
            adapter.validate_source(self.root, "firered")

    def test_rejects_double_patching(self):
        file = self.root / "src/main.c"
        with adapter.patched_source(self.root, "emerald"):
            with self.assertRaisesRegex(adapter.ExpansionDrift, "already patched"):
                adapter.validate_source(self.root, "emerald")
        self.assertEqual(file.read_text(), MAIN)

    def test_native_expansion_mode_owns_lcd_buffer_in_both_guards(self):
        # Regression: every expanded-engine variant previously segfaulted
        # (signal 11) when native LCD capture had no allocated video buffer.
        native = (adapter.ROOT / "integration/mgba/xgba_mgba_headless.c").read_text()
        self.assertEqual(native.count("r15_dir || r16_dir || expansion_dir || r24_dir"), 2)
        self.assertIn("if (video)\n        core->setVideoBuffer(core, video, 240);", native)
        header = (adapter.ROOT / "integration/mgba/xgba_expansion_native.h").read_text()
        self.assertIn('fail("RHH native mGBA framebuffer not attached")', header)

    def test_real_heap_tail_16k_page_contract(self):
        content = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        native = (adapter.ROOT / "integration/mgba/xgba_expansion_native.h").read_text()
        harness = (adapter.ROOT / "tools/xgba_expansion_native_acceptance.py").read_text()
        self.assertIn("#define XGBA_EXPANSION_PAGE_BYTES 0x4000u", content)
        self.assertIn("HEAP_SIZE - XGBA_EXPANSION_PAGE_BYTES", content)
        self.assertIn("XgbaExpansionPageAcquire", content)
        self.assertIn("XgbaExpansionPageReset", content)
        self.assertIn("gXgbaExpansionProof.page_resident = 0u;", content)
        self.assertIn("gXgbaExpansionProof.page_resident = length;", content)
        self.assertIn("return 0u; /* reject truncation/ambiguous source resource ID */", content)
        self.assertIn("uint8_t expected[16384];", native)
        self.assertIn("RHH original engine overwrote protected XGBA page", native)
        self.assertIn("PAGE_PAYLOAD = bytes(", harness)
        self.assertIn("range(16 * 1024)", harness)

    def test_public_runtime_page_api_contract(self):
        header = (adapter.ROOT / "integration/expansion/xgba_expansion_page.h").read_text()
        impl = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        for fn in ("XgbaExpansionPageAcquire", "XgbaExpansionPageRelease",
                   "XgbaExpansionPageData", "XgbaExpansionPageResidentBytes",
                   "XgbaExpansionPageGeneration"):
            self.assertIn(fn, header)
            self.assertIn(fn, impl)
        self.assertIn("return gXgbaExpansionProof.page_resident ? XGBA_EXPANSION_PAGE : NULL;", impl)
        self.assertIn("XgbaExpansionPageReset();\n        return 0u;", impl)
        self.assertIn("XgbaExpansionPageReset();\n        return 0u; /* reject truncation", impl)
        self.assertIn("XGBA_EXPANSION_PAGE_CAPACITY 16384u", header)
        patched = adapter.patched_main(
            MAIN, adapter.ROOT / "integration/fire_red/xgba_guest.h", impl)
        self.assertIn("xgba_expansion_page.h", patched)
        self.assertNotIn("__XGBA_PAGE_API__", patched)

    def test_rejects_injected_header_path(self):
        probe = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        with self.assertRaisesRegex(adapter.ExpansionDrift, "unsafe header path"):
            adapter.patched_main(MAIN, Path('/bad/"quote.h'), probe)


if __name__ == "__main__":
    unittest.main()
