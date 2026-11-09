"""Pins for the industry-guide generator.

The behaviour that matters is the exclusion of the Advance Ruling chapter. Sections
95–106 are cited in essentially every ruling because they are the Authority's own
basis for hearing the case — s.97 is the application, s.98 the procedure on receipt.
Counting them produces a guide about AAR procedure rather than about the industry,
and it looks entirely plausible until you read the output.
"""
from __future__ import annotations

from gst_aar_law_shim import industry_guide as ig


class TestSubstantiveFilter:
    def test_aar_chapter_is_excluded(self) -> None:
        for s in ("CGST s.97", "SGST s.98", "CGST s.98(4)", "SGST s.96",
                  "IGST s.95", "UTGST s.106"):
            assert not ig.substantive(s), s

    def test_real_provisions_are_kept(self) -> None:
        for s in ("SGST s.7", "CGST s.16", "SGST s.17(5)", "CGST s.15",
                  "SGST s.2(30)", "CGST s.9"):
            assert ig.substantive(s), s

    def test_the_boundary_is_exact(self) -> None:
        # 94 and 107 sit either side of the chapter and must both be kept
        assert ig.substantive("CGST s.94")
        assert ig.substantive("CGST s.107")
        assert not ig.substantive("CGST s.95")
        assert not ig.substantive("CGST s.106")

    def test_non_citations_are_rejected(self) -> None:
        assert not ig.substantive("")
        assert not ig.substantive("Schedule II")
        assert not ig.substantive("Circular 51/25/2018")


class TestProvisionNormalisation:
    """The State Acts mirror the Central Act, so the same section must not be
    counted once per Act."""

    def test_prefix_is_dropped(self) -> None:
        assert ig.norm_provision("CGST s.16") == "s.16"
        assert ig.norm_provision("SGST s.16") == "s.16"
        assert ig.norm_provision("IGST s.16") == "s.16"
        assert ig.norm_provision("UTGST s.16") == "s.16"

    def test_all_four_collapse_to_one(self) -> None:
        forms = ["CGST s.17(5)", "SGST s.17(5)", "IGST s.17(5)", "UTGST s.17(5)"]
        assert len({ig.norm_provision(f) for f in forms}) == 1

    def test_sub_clauses_are_preserved(self) -> None:
        # s.16 and s.16(1) are different citations and must stay distinct
        assert ig.norm_provision("SGST s.16") != ig.norm_provision("SGST s.16(1)")

    def test_a_non_citation_passes_through(self) -> None:
        assert ig.norm_provision("Schedule II") == "Schedule II"


class TestGloss:
    def test_known_provisions_have_a_plain_language_note(self) -> None:
        for s in ("s.7", "s.16", "s.17(5)", "s.15"):
            assert ig.gloss(s), s

    def test_the_glosses_are_readable_prose(self) -> None:
        # they are shown to a reader, so they must not be bare section numbers
        for s, text in ig.PROVISION_NOTE.items():
            assert len(text) > 15, s
            assert not text.strip().startswith("s."), s

    def test_an_unknown_provision_returns_empty_not_a_guess(self) -> None:
        assert ig.gloss("s.999") == ""
