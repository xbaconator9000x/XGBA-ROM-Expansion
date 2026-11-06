import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ENTRYPOINT = WORKFLOWS / "phase1-pr-checks.yml"
CHILDREN = {
    "phase1-census.yml",
    "phase1-curated-core-four.yml",
    "phase1-curated-final-six.yml",
    "phase1-curated-four-source.yml",
    "phase1-curated-handoff-index.yml",
    "phase1-curated-interop-four.yml",
    "phase1-curated-six-source.yml",
    "phase1-fuchsia-tutor-static.yml",
    "phase1-next-p0-packet.yml",
    "phase1-original-machine-dossier-bytes.yml",
    "phase1-remaining-p0-eight-abi-decoder.yml",
    "phase1-remaining-p0-eight-arm.yml",
    "phase1-remaining-p0-eight-cart-editor.yml",
    "phase1-remaining-p0-eight-cheats-config.yml",
    "phase1-remaining-p0-eight-crossboundary.yml",
    "phase1-remaining-p0-eight-gb-cpu.yml",
    "phase1-remaining-p0-eight-gb-debugger.yml",
    "phase1-remaining-p0-eight-gba-runtime.yml",
    "phase1-remaining-p0-eight-interop.yml",
    "phase1-remaining-p0-eight-porymap.yml",
    "phase1-remaining-p0-eight.yml",
    "phase1-remaining-p0-four-firered-map.yml",
    "phase1-remaining-p0-four-libretro-qt.yml",
    "phase1-remaining-p0-four-python-qt.yml",
    "phase1-remaining-p0-handoff-index.yml",
    "phase1-remaining-p0-six-qt-go-libretro.yml",
    "phase1-remaining-p0-six.yml",
    "phase1-second-packet-firered-next.yml",
    "phase1-second-packet-firered-sevii.yml",
    "phase1-second-packet-firered.yml",
    "phase1-second-packet-fuchsia-indigo.yml",
    "phase1-second-packet-handoff-index.yml",
    "phase1-second-packet-league-mansion.yml",
    "phase1-second-packet-navel-oneisland.yml",
    "phase1-second-packet-pallet-pewter.yml",
    "phase1-second-packet-qt-wii.yml",
    "phase1-third-machine-dossier-sha.yml",
    "phase1-third-p0-packet.yml",
    "phase1-third-packet-firered.yml",
    "phase1-third-packet-handoff-index.yml",
    "phase1-third-packet-routes.yml",
}


class Phase1CiEntrypointTests(unittest.TestCase):
    def test_entrypoint_calls_every_expected_workflow_once(self):
        source = ENTRYPOINT.read_text()
        calls = re.findall(r"(?m)^    uses: \./\.github/workflows/([^/\n]+)$", source)
        self.assertEqual(len(calls), len(CHILDREN))
        self.assertEqual(set(calls), CHILDREN)

    def test_children_are_reusable_without_duplicate_triggers(self):
        for name in sorted(CHILDREN):
            with self.subTest(workflow=name):
                source = (WORKFLOWS / name).read_text()
                trigger_block = source.split("permissions:", 1)[0]
                if name == "phase1-census.yml":
                    self.assertIn("  workflow_call:\n", trigger_block)
                    self.assertIn("  workflow_dispatch:\n", trigger_block)
                    self.assertIn("  push:\n", trigger_block)
                    self.assertIn("ref: ${{ github.event.pull_request.head.sha || github.sha }}", source)
                    self.assertIn("test_phase1_mapping_gate.py", source)
                else:
                    self.assertEqual(
                        trigger_block,
                        "name: " + source.splitlines()[0][6:] + "\non:\n  workflow_call:\n",
                    )
                self.assertIn("permissions:\n  contents: read", source)
                self.assertNotIn("contents: write", source)

    def test_entrypoint_is_read_only_and_targets_stacked_base(self):
        source = ENTRYPOINT.read_text()
        self.assertIn("pull_request:\n    branches:\n      - phase1/firered-layout-writers-20261026", source)
        self.assertIn("permissions:\n  contents: read", source)
        self.assertNotIn("contents: write", source)


if __name__ == "__main__":
    unittest.main()
