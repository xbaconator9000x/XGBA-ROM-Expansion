"""R47 no-silent-omissions gate: full original world NPC/script coverage."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import xgba_r47_full_content_gate as gate


def original_fixture():
    sources={}
    for name,b in gate.BASELINE.items():
        source={
            "rom_sha256":b["sha256"],
            "original_bytes":b["bytes"],
            "structurally_valid_populated_maps":b["populated_maps"],
            "original_numeric_map_slots":b["map_slots"],
            "original_zero_pointer_slots_preserved":b["null_map_slots"],
            "event_counts":{
                k:b[k] for k in ("objects","warps","coord_events",
                                 "bg_events","script_maps","connections")
            },
        }
        sources[name]=source
    return {"sources":sources}


def progress_fixture():
    result={}
    for source,b in gate.BASELINE.items():
        result[source]={
            **{key:b[key] for key in ("objects","warps","coord_events",
                                     "bg_events","script_maps","populated_maps")},
            **{key:"unassessed" for key in gate.COVERAGE_CLASSES},
        }
    return result


class TestCompleteThreeRomScope(unittest.TestCase):
    def test_preserved_full_three_original_sources(self):
        record=gate.validate_original_inventory(original_fixture())
        self.assertEqual(record["totals"]["objects"],17089)
        self.assertEqual(record["totals"]["warps"],7146)
        self.assertEqual(record["totals"]["coord_events"],2340)
        self.assertEqual(record["totals"]["bg_events"],4697)
        self.assertEqual(record["totals"]["populated_maps"],2856)
        self.assertEqual(record["totals"]["script_maps"],2856)
        self.assertFalse(record["actual_foreign_NPC_dialogue_executed"])
        self.assertFalse(record["full_integrated_gameplay_verified"])
        gate.validate_progress_report(progress_fixture(),record)
    def test_cannot_drop_rocket_or_heart_soul(self):
        for source in ("emerald","rocket","heart_soul"):
            fixture=original_fixture()
            del fixture["sources"][source]
            with self.subTest(source=source),self.assertRaises(gate.IncompleteThreeRomIntegration):
                gate.validate_original_inventory(fixture)
    def test_rejects_disappeared_npcs_and_scripts(self):
        for key in ("objects","warps","coord_events","bg_events","script_maps","connections"):
            fixture=original_fixture()
            fixture["sources"]["rocket"]["event_counts"][key]-=1
            with self.subTest(key=key),self.assertRaises(gate.IncompleteThreeRomIntegration):
                gate.validate_original_inventory(fixture)
    def test_rejects_wrong_game_sha_or_removed_hns_map_holes(self):
        fixture=original_fixture()
        fixture["sources"]["heart_soul"]["rom_sha256"]="0"*64
        with self.assertRaises(gate.IncompleteThreeRomIntegration):
            gate.validate_original_inventory(fixture)
        fixture=original_fixture()
        fixture["sources"]["heart_soul"]["original_zero_pointer_slots_preserved"]=0
        with self.assertRaises(gate.IncompleteThreeRomIntegration):
            gate.validate_original_inventory(fixture)
    def test_rejects_silent_drop_from_coverage_even_if_maps_pass(self):
        original=gate.validate_original_inventory(original_fixture())
        for key in ("objects","warps","coord_events","bg_events","script_maps"):
            coverage=progress_fixture()
            coverage["rocket"][key]-=1
            with self.subTest(key=key),self.assertRaises(gate.IncompleteThreeRomIntegration):
                gate.validate_progress_report(coverage,original)
        coverage=progress_fixture()
        del coverage["rocket"]["dialogue_text"]
        with self.assertRaises(gate.IncompleteThreeRomIntegration):
            gate.validate_progress_report(coverage,original)
    def test_unsupported_data_must_be_retained_and_accounted_for(self):
        original=gate.validate_original_inventory(original_fixture())
        coverage=progress_fixture()
        coverage["heart_soul"]["native_engine_callbacks"]="unsupported_retained"
        gate.validate_progress_report(coverage,original)
        coverage["heart_soul"]["native_engine_callbacks"]="omitted"
        with self.assertRaises(gate.IncompleteThreeRomIntegration):
            gate.validate_progress_report(coverage,original)
        coverage["heart_soul"]["native_engine_callbacks"]="native_test_passed"
        with self.assertRaises(gate.IncompleteThreeRomIntegration):
            gate.validate_progress_report(coverage,original)
    def test_rejects_false_or_partial_original_report(self):
        for wrong in (None,{}, {"sources":{}},
                      {"sources":None},
                      {"sources":{"emerald":{},"rocket":{},"heart_soul":{}}}):
            with self.subTest(wrong=wrong),self.assertRaises(gate.IncompleteThreeRomIntegration):
                gate.validate_original_inventory(wrong)


if __name__=="__main__":
    unittest.main()
