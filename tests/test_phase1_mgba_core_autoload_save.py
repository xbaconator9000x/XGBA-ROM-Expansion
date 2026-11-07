import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "phase1_mgba_core_autoload_save",
    ROOT / "tools/phase1_mgba_core_autoload_save.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

GOOD = "\n".join(runner.EXPECTED_LINES) + "\nPHASE1_AUTOLOAD_DONE\n"
PINNED_SOURCES = {
    "src/core/core.c": """bool mCoreAutoloadSave(struct mCore* core) {
\tif (!core->dirs.save) {
\t\treturn false;
\t}
\tint savePlayerId = 0;
\tchar sav[16] = ".sav";
\tmCoreConfigGetIntValue(&core->config, "savePlayerId", &savePlayerId);
\tif (savePlayerId > 1) {
\t\tsnprintf(sav, sizeof(sav), ".sa%i", savePlayerId);
\t}
\treturn core->loadSave(core, mDirectorySetOpenSuffix(&core->dirs, core->dirs.save, sav, O_CREAT | O_RDWR));
}""",
    "src/core/directories.c": """struct VFile* mDirectorySetOpenSuffix(struct mDirectorySet* dirs, struct VDir* dir, const char* suffix, int mode) {
\tif (!dir) {
\t\treturn NULL;
\t}
\tchar name[PATH_MAX + 1] = "";
\tsnprintf(name, sizeof(name) - 1, "%s%s", dirs->baseName, suffix);
\treturn dir->openFile(dir, name, mode);
}""",
    "src/util/vfs/vfs-dirent.c": """struct VDir* VDirOpen(const char* path) {
\tDIR* de = opendir(path);
\tif (!de) {
\t\treturn 0;
\t}
\tstruct VDirDE* vd = malloc(sizeof(struct VDirDE));
\tif (!vd) {
\t\tclosedir(de);
\t\treturn 0;
\t}
\tvd->d.openFile = _vdOpenFile;
\treturn &vd->d;
}

struct VFile* _vdOpenFile(struct VDir* vd, const char* path, int mode) {
\tstruct VDirDE* vdde = (struct VDirDE*) vd;
\tif (!path) {
\t\treturn 0;
\t}
\tconst char* dir = vdde->path;
\tchar* combined = malloc(sizeof(char) * (strlen(path) + strlen(dir) + 2));
\tsprintf(combined, "%s%s%s", dir, PATH_SEP, path);
\tstruct VFile* file = VFileOpen(combined, mode);
\tfree(combined);
\treturn file;
}""",
    "src/gba/core.c": """static bool _GBACoreLoadSave(struct mCore* core, struct VFile* vf) {
\treturn GBALoadSave(core->board, vf);
}""",
    "src/gba/gba.c": """bool GBALoadSave(struct GBA* gba, struct VFile* sav) {
\tenum GBASavedataType type = gba->memory.savedata.type;
\tGBASavedataDeinit(&gba->memory.savedata);
\tGBASavedataInit(&gba->memory.savedata, sav);
\tif (type != GBA_SAVEDATA_AUTODETECT) {
\t\tGBASavedataForceType(&gba->memory.savedata, type);
\t}
\treturn sav;
}""",
}


class TestCoreAutoloadSave(unittest.TestCase):
    def test_positive_caller_matrix(self):
        result = runner.parse_output(GOOD)
        self.assertTrue(result["successful_autoload"]["caller_return"])
        failed = result["injected_allocation_failure"]
        self.assertFalse(failed["caller_return"])
        self.assertEqual(failed["save_callbacks"], 1)
        self.assertEqual(failed["null_save_callbacks"], 1)
        self.assertTrue(failed["leaked_fd_open_after_callback"])
        retry = result["retry_after_allocation_failure"]
        self.assertFalse(retry["failure_return"])
        self.assertTrue(retry["retry_return"])
        self.assertTrue(retry["leaked_first_fd_open"])
        self.assertTrue(retry["retry_fd_closed"])
        self.assertEqual(
            result["missing_save_directory_control"]["target_open_attempts"], 0
        )

    def test_seven_output_mutations_are_rejected(self):
        self.assertEqual(runner.reject_output_mutations(GOOD), 7)

    def test_nine_pinned_source_mutations_are_rejected(self):
        self.assertEqual(runner.reject_source_mutations(PINNED_SOURCES), 9)

    def test_receipt_pins_scope_and_nonapproval(self):
        path = ROOT / runner.RECEIPT
        receipt = runner.verify_receipt(path)
        self.assertEqual(receipt["overall"], "FAIL_INCOMPLETE")
        self.assertEqual(receipt["independent_approvals"], 0)
        self.assertEqual(len(receipt["source_records"]), 18)
        self.assertTrue(receipt["prior_witness_nonoverlap"]["distinct_caller_body"])
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            receipt["source_records"][0]["full_source_sha256"] = "0" * 64
            json.dump(receipt, temp)
            temp.flush()
            with self.assertRaises(ValueError):
                runner.verify_receipt(Path(temp.name))
        receipt = runner.verify_receipt(path)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp:
            receipt["native_sdl_frontend_executed"] = True
            json.dump(receipt, temp)
            temp.flush()
            with self.assertRaises(ValueError):
                runner.verify_receipt(Path(temp.name))

    def test_host_fixture_and_frontend_limits_are_explicit(self):
        receipt = runner.verify_receipt(ROOT / runner.RECEIPT)
        self.assertTrue(receipt["host_allocator_fault_injection"])
        self.assertTrue(receipt["save_callback_is_test_fixture"])
        self.assertFalse(receipt["natural_os_allocation_failure_observed"])
        self.assertFalse(receipt["real_gba_savedata_callback_executed"])
        self.assertFalse(receipt["native_sdl_frontend_executed"])
        self.assertFalse(receipt["native_qt_frontend_executed"])
        self.assertFalse(receipt["durable_persistence_tested"])
        self.assertFalse(receipt["physical_flash_tested"])

    def test_previous_caller_receipt_is_preserved_and_distinct(self):
        record = runner.verify_prior_inventory(ROOT)
        self.assertEqual(record["previous_caller"], "mCoreLoadSaveFile")
        self.assertEqual(record["current_caller"], "mCoreAutoloadSave")
        self.assertTrue(record["distinct_caller_body"])

    def test_harness_hash(self):
        harness = (
            ROOT / "tests/phase1_mgba_core_autoload_save.c"
        ).read_bytes()
        self.assertEqual(hashlib.sha256(harness).hexdigest(),
                         runner.HARNESS_SHA256)

    def test_missing_terminal_is_rejected(self):
        with self.assertRaises(ValueError):
            runner.parse_output(GOOD.removesuffix("PHASE1_AUTOLOAD_DONE\n"))


if __name__ == "__main__":
    unittest.main()
