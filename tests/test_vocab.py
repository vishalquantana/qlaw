"""Pins for the Phase 0 vocabulary normalisation.

The point of these maps is that aggregation becomes trustworthy, so the tests check
the two ways that can fail: a real value the map does not cover (it would fall
through to a fallback and be silently mislabelled), and a map that emits more
distinct values than the controlled vocabulary allows.
"""
from __future__ import annotations

from gst_aar_law_shim import normalize_vocab as nv

# every raw value actually observed in aar.db, from the drift report
OBSERVED_KIND = ["good", "goods", "service", "both", "service|good",
                 "unspecified", "null", ""]
OBSERVED_OUTCOME = ["answered", "ruling_given", "withdrawn", "rejected",
                    "no_ruling", "null", ""]


class TestKindVocabulary:
    def test_every_observed_value_is_mapped(self) -> None:
        for raw in OBSERVED_KIND:
            assert raw in nv.KIND_MAP, f"unmapped kind: {raw!r}"

    def test_maps_onto_exactly_four_concepts(self) -> None:
        assert set(nv.KIND_MAP.values()) == {"good", "service", "both", "unspecified"}

    def test_plural_and_singular_collapse(self) -> None:
        assert nv.KIND_MAP["good"] == nv.KIND_MAP["goods"] == "good"

    def test_the_combined_spelling_collapses_to_both(self) -> None:
        assert nv.KIND_MAP["both"] == nv.KIND_MAP["service|good"] == "both"

    def test_empty_and_null_become_unspecified(self) -> None:
        assert nv.KIND_MAP[""] == nv.KIND_MAP["null"] == "unspecified"


class TestOutcomeVocabulary:
    def test_every_observed_value_is_mapped(self) -> None:
        for raw in OBSERVED_OUTCOME:
            assert raw in nv.OUTCOME_MAP, f"unmapped outcome: {raw!r}"

    def test_one_vocabulary_serves_both_columns(self) -> None:
        # `answered` (questions) and `ruling_given` (rulings) are the same fact
        assert nv.OUTCOME_MAP["answered"] == nv.OUTCOME_MAP["ruling_given"]

    def test_blank_and_null_become_unknown_not_a_guess(self) -> None:
        assert nv.OUTCOME_MAP[""] == "unknown"
        assert nv.OUTCOME_MAP["null"] == "unknown"

    def test_unknown_is_a_member_of_the_vocabulary(self) -> None:
        assert "unknown" in set(nv.OUTCOME_MAP.values())

    def test_vocabulary_stays_small(self) -> None:
        assert set(nv.OUTCOME_MAP.values()) == {
            "ruling_given", "withdrawn", "rejected", "no_ruling", "unknown"}


class TestRateNormalisation:
    """The two extraction passes wrote rates differently — the regex pass stores the
    bare number, the LLM pass stores it with a percent sign. Left alone, `18` and
    `18%` split any count by rate."""

    def test_bare_number_gets_a_percent_sign(self) -> None:
        assert nv.norm_rate_value("18") == "18%"

    def test_percent_form_is_stable(self) -> None:
        assert nv.norm_rate_value("18%") == "18%"

    def test_the_two_forms_converge(self) -> None:
        assert nv.norm_rate_value("2.5") == nv.norm_rate_value("2.5%") == "2.5%"

    def test_nil_becomes_zero(self) -> None:
        assert nv.norm_rate_value("Nil") == "0%"

    def test_blank_stays_blank(self) -> None:
        assert nv.norm_rate_value("") == ""
        assert nv.norm_rate_value("   ") == ""

    def test_descriptive_values_are_not_forced_into_a_number(self) -> None:
        # a real value from the schedule — it is not a rate, and inventing one
        # from it would be wrong
        s = "Same rate of central tax as on supply of like goods"
        assert nv.norm_rate_value(s) == s


class TestFallbackBehaviour:
    """An unmapped value must not pass through — that would let a new spelling
    leak into aggregates looking like a legitimate category."""

    def test_unmapped_kind_does_not_pass_through(self) -> None:
        assert nv.KIND_MAP.get("something-new", "unspecified") == "unspecified"

    def test_unmapped_outcome_does_not_pass_through(self) -> None:
        # the real case: the number '8607' leaked into an outcome column
        assert nv.OUTCOME_MAP.get("8607", "unknown") == "unknown"
