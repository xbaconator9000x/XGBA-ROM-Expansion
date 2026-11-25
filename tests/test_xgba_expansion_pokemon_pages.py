import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import xgba_expansion_pokemon_pages as pokemon  # noqa: E402
import xgba_expansion_trainer_pages as trainer  # noqa: E402
from xgba_expansion_map_pages import SourceAssetError  # noqa: E402

INFO = """
    [SPECIES_BULBASAUR] =
    {
        .frontPic = gMonFrontPic_Bulbasaur,
        .backPic = gMonBackPic_Bulbasaur,
    },
    [SPECIES_IVYSAUR] =
    {
        .frontPicFemale = gMonFrontPic_IvysaurF,
    },
"""


class PokemonPageGeneratorTests(unittest.TestCase):
    def test_species_block_is_bounded_to_one_species(self):
        block = pokemon.species_block(INFO, "BULBASAUR")
        self.assertIn("gMonBackPic_Bulbasaur", block)
        self.assertNotIn("Female", block)
        self.assertIn("frontPicFemale", pokemon.species_block(INFO, "IVYSAUR"))
        with self.assertRaises(SourceAssetError):
            pokemon.species_block(INFO, "MEW")

    def test_generator_reuses_private_publication_and_pins_source(self):
        self.assertIs(pokemon.private_create, trainer.private_create)
        self.assertIs(pokemon.pinned_asset, trainer.pinned_asset)
        text = (ROOT / "tools/xgba_expansion_pokemon_pages.py").read_text()
        for fragment in ("ROOT_TAG_SHA", "P_GBA_STYLE_SPECIES_GFX",
                         "PicFemale", 'identifier.startswith(RESOURCE_PREFIX)',
                         "private Pokemon provider write verification failed",
                         "output must be outside upstream source"):
            self.assertIn(fragment, text)
        self.assertLess(text.index("with private_create(data)"),
                        text.index("with private_create(manifest, text=True)"))

    def test_resource_ids_match_guest_bridge_format(self):
        self.assertEqual([(n, c) for n, c, _, _ in pokemon.SPECIES],
                         [(1, "BULBASAUR"), (74, "GEODUDE")])
        self.assertEqual(f"{pokemon.RESOURCE_PREFIX}f.{74:04x}", "rhh.mon.f.004a")
        self.assertEqual(pokemon.FRONT_SIZE[0] * pokemon.FRONT_SIZE[1] // 2, 4096)
        self.assertEqual(pokemon.BACK_SIZE[0] * pokemon.BACK_SIZE[1] // 2, 2048)
        bridge = (ROOT / "integration/expansion/xgba_expansion_pokemon_battle.inc").read_text()
        self.assertIn('"rhh.mon.f.0000"', bridge)
        self.assertIn("species != SPECIES_BULBASAUR && species != SPECIES_GEODUDE", bridge)


if __name__ == "__main__":
    unittest.main()
