import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import compiled_dependency_graph as graph


class CompiledDependencyGraphTests(unittest.TestCase):
    def test_paired_compiled_symbol_reference_is_a_candidate_edge(self):
        undefined = [("libmgba.a", "matrix.o", "U", "GBAMatrixWrite")]
        definitions = {"GBAMatrixWrite": [("libmgba.a", "matrix-provider.o", "T")]}
        sources = {
            "matrix.o": {"src/gba/memory.c"},
            "matrix-provider.o": {"src/gba/cart/matrix.c"},
        }

        candidates, unresolved = graph.classify_symbol_references(
            undefined, definitions, sources
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["referenced_symbol"], "GBAMatrixWrite")
        self.assertEqual(candidates[0]["consumer_source_candidate"], "src/gba/memory.c")
        self.assertEqual(candidates[0]["provider_source_candidate"], "src/gba/cart/matrix.c")
        self.assertEqual(candidates[0]["resolution"], "LINK_OBJECT_CODE_SYMBOL_CANDIDATE")
        self.assertEqual(unresolved, [])

    def test_unprovided_symbol_is_enumerated_instead_of_dropped(self):
        undefined = [("libmgba.a", "matrix.o", "U", "external_vfile_read")]

        candidates, unresolved = graph.classify_symbol_references(
            undefined, {}, {"matrix.o": {"src/gba/cart/matrix.c"}}
        )

        self.assertEqual(candidates, [])
        self.assertEqual(unresolved, [{
            "archive": "libmgba.a",
            "consumer_object": "matrix.o",
            "consumer_source_candidate": "src/gba/cart/matrix.c",
            "referenced_symbol": "external_vfile_read",
            "provider_count": 0,
            "reason_code": "NO_PROVIDER_IN_INSPECTED_STATIC_ARCHIVES",
        }])

    def test_missing_consumer_attribution_is_explicitly_unresolved(self):
        undefined = [("libmgba.a", "unknown.o", "U", "external_vfile_read")]
        definitions = {
            "external_vfile_read": [("libmgba.a", "vfs.o", "T")]
        }

        candidates, unresolved = graph.classify_symbol_references(
            undefined, definitions, {}
        )

        self.assertEqual(candidates, [])
        self.assertEqual(unresolved[0]["consumer_source_candidate"], "UNATTRIBUTED_OBJECT_SOURCE")
        self.assertEqual(unresolved[0]["reason_code"], "CONSUMER_SOURCE_ATTRIBUTION_MISSING")

    def test_missing_provider_source_attribution_is_not_called_a_candidate_edge(self):
        undefined = [("libmgba.a", "consumer.o", "U", "ambiguous_provider")]
        definitions = {
            "ambiguous_provider": [
                ("libmgba.a", "provider.o", "T")
            ]
        }

        candidates, unresolved = graph.classify_symbol_references(
            undefined, definitions, {"consumer.o": {"src/consumer.c"}}
        )

        self.assertEqual(candidates, [])
        self.assertEqual(
            unresolved[0]["reason_code"], "PROVIDER_SOURCE_ATTRIBUTION_MISSING"
        )

    def test_provider_overflow_is_reason_coded_not_silently_omitted(self):
        undefined = [("libmgba.a", "consumer.o", "U", "ambiguous")]
        definitions = {
            "ambiguous": [
                ("libmgba.a", f"provider-{index}.o", "T")
                for index in range(33)
            ]
        }

        candidates, unresolved = graph.classify_symbol_references(
            undefined, definitions, {"consumer.o": {"src/consumer.c"}}
        )

        self.assertEqual(candidates, [])
        self.assertEqual(unresolved[0]["provider_count"], 33)
        self.assertEqual(
            unresolved[0]["reason_code"], "PROVIDER_SET_EXCEEDS_ENUMERATION_LIMIT"
        )

    def test_symbol_evidence_order_is_deterministic(self):
        undefined = [
            ("libmgba.a", "z.o", "U", "symbol_z"),
            ("libmgba.a", "a.o", "U", "symbol_a"),
        ]
        sources = {"z.o": {"src/z.c"}, "a.o": {"src/a.c"}}

        first = graph.classify_symbol_references(undefined, {}, sources)
        second = graph.classify_symbol_references(list(reversed(undefined)), {}, sources)

        self.assertEqual(first, second)
        self.assertEqual([row["referenced_symbol"] for row in first[1]], ["symbol_a", "symbol_z"])


if __name__ == "__main__":
    unittest.main()
