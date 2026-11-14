"""R84 ensure a real Emerald foreign-source game may not overwrite native Flash."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class NativeFlashSaveContract(unittest.TestCase):
 def test_original_source_patch_refuses_core_and_incremental_saves(self):
  patch=(ROOT/"tools/xgba_r17_emerald_patch.py").read_text()
  native=(ROOT/"integration/emerald/xgba_r80_native_source_warp.inc").read_text()
  self.assertIn('saving=e/"src/save.c"',patch)
  self.assertIn('u8 HandleSavingData(u8 saveType)',patch)
  self.assertIn('u8 TrySavingData(u8 saveType)',patch)
  self.assertIn('gSaveAttemptStatus = SAVE_STATUS_ERROR;',patch)
  for name in ("LinkFullSave_Init","LinkFullSave_WriteSector",
      "LinkFullSave_ReplaceLastSector","LinkFullSave_SetLastSectorSignature",
      "WriteSaveBlock2","WriteSaveBlock1Sector"):
   self.assertIn(name,patch)
  self.assertIn('anchor+"\\n    if (!XgbaR84NativeSaveAllowed()) return TRUE;"',patch)
  self.assertIn("if(sXgbaR80Route.phase!=0u ||",native)
  self.assertIn("sXgbaR48PendingFlyWorld!=0xffu",native)
  self.assertIn("(sXgbaR50Ready && sXgbaR50World!=0u)",native)
 def test_never_advertise_foreign_flash_persistence(self):
  doc=(ROOT/"docs/R84_ORIGINAL_WORLD_FLASH_WRITE_REFUSAL.md").read_text()
  self.assertIn("not a persistent original-source-world save",doc)
if __name__=="__main__":unittest.main()
