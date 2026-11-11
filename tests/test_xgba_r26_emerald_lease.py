"""R26: original Emerald game-side 16KiB phase ownership generation proof.

Builds pinned original Emerald and patched native mGBA; executes four
double battles, three field returns and 16 game-generated lease-busy
refusals (eight map loads and eight opponent sources). This is a real
original-game test, not the portable header contract alone.
"""
import os
import json
from pathlib import Path
import test_xgba_r23_emerald_forced_phase_eviction as r23

class NativeEmeraldLeaseGenerations(r23.NativeEmeraldFourBattleForcedEviction):
    R26_LEASE_TEST=True
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "PASS_R26_ORIGINAL_EMERALD_LEASE_LIFETIMES" not in cls.log:
            raise AssertionError("Original Emerald R26 lifetime proof missing")
        cls.report["milestone"]="R26_ORIGINAL_EMERALD_EWRAM_PHASE_LEASES"
        cls.report["r26_guest_map_borrows"]=8
        cls.report["r26_guest_battle_borrows"]=8
        cls.report["r26_borrowed_phase_switch_refusals"]=16
        cls.report["r26_proves"]="Guest-side scoped borrow/switch refusal/release in actual four-battle Emerald"
        cls.report["r26_does_not_prove"]="Persistent renderer pointer lifetimes, async mid-beat DMA, three-map eviction"
        dest=os.environ.get("XGBA_R26_EVIDENCE_DIR")
        if dest:
            root=Path(dest)
            root.mkdir(parents=True,exist_ok=True)
            for image in cls.output.glob("*.png"):
                (root/image.name).write_bytes(image.read_bytes())
            (root/"proof.json").write_text(json.dumps(cls.report,indent=2,sort_keys=True)+"\n")

    def test_original_guest_denies_phase_switch_while_source_borrowed(self):
        self.assertIn("map_busy=8",self.log)
        self.assertIn("battle_busy=8",self.log)
    def test_original_guest_releases_each_scoped_map_and_sprite_borrow(self):
        self.assertIn("map_borrows=8",self.log)
        self.assertIn("battle_borrows=8",self.log)
        self.assertIn("remaining_pins=0",self.log)
    def test_original_guest_preserves_all_eight_real_phase_generations(self):
        self.assertIn("arena_epoch=8",self.log)
        self.assertEqual(self.values["arena_epoch"],8)
    def test_real_original_emerald_four_battle_and_map_composition(self):
        self.assertIn("original_battles=4",self.log)
        self.assertEqual(self.values["external_map_fetches"],8)
        self.assertEqual(self.values["external_sprite_fetches"],8)
    def test_eight_original_native_lcd_screens_and_json_machine_proof(self):
        self.assertEqual(len(list(self.output.glob("*.png"))),8)
