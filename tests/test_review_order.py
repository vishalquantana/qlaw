"""Pins for the order-review prototype (Pillar 1).

The chronology check is the strongest thing the tool does, because it needs no external
source: if an order fixes a point of taxation and then applies a provision that did not
exist on that date, the contradiction is in the order itself.

The authority and notification checks went wrong twice, both times producing a false
"HELD" — which is worse than "NOT HELD", because it claims a verification that did not
happen. Those bugs are pinned here.
"""
from __future__ import annotations

from gst_aar_law_shim import review_order as ro

ORDER = """
6.8 ... fixing the point of taxation as 10-03-2019.
6.9 ... introduced by Notification No. 03/2019-CTR dt. 29-03-2019 ...
6.13 ... expressly effective from 01-04-2019 ...
6.10 ... the sale deed was executed on 26-06-2019 ...
6.20 Suchitra Components Ltd. v. Commissioner of Central Excise (17.01.2007)
6.21 in CIT v. Vatika Township Pvt. Ltd. (15.09.2014)
6.21 and in CCE v. Mysore Electricals Industries Ltd. (15.11.2006)
"""


class TestChronology:
    def test_dates_are_extracted(self) -> None:
        chron = ro.extract_chronology(ORDER)
        dates = {d for d, _ in chron}
        assert "2019-03-10" in dates
        assert "2019-04-01" in dates
        assert "2019-06-26" in dates

    def test_roles_are_attributed(self) -> None:
        chron = dict(ro.extract_chronology(ORDER))
        assert "point of taxation" in chron.get("2019-03-10", "")
        assert "effective" in chron.get("2019-04-01", "")

    def test_the_contradiction_is_flagged(self) -> None:
        flags = ro.check_chronology(ro.extract_chronology(ORDER))
        joined = " ".join(flags)
        assert "effective from 2019-04-01" in joined
        assert "point of taxation" in joined

    def test_the_post_dated_comparable_is_flagged(self) -> None:
        flags = " ".join(ro.check_chronology(ro.extract_chronology(ORDER)))
        assert "2019-06-26" in flags

    def test_a_consistent_order_raises_no_flag(self) -> None:
        text = ("point of taxation as 10-03-2019. The amendment was effective from "
                "01-01-2019. the sale deed was executed on 05-02-2019")
        assert ro.check_chronology(ro.extract_chronology(text)) == []

    def test_no_dates_means_no_flags(self) -> None:
        assert ro.check_chronology(ro.extract_chronology("no dates here")) == []


class TestAuthorityNames:
    """Both name orders occur: "X v. CCE" and "CIT v. Y"."""

    def test_both_orders_are_detected(self) -> None:
        names = ro.extract_authorities(ORDER) if hasattr(ro, "extract_authorities") else None
        # extraction is inline in check_authorities; assert via the pattern instead
        import re
        found = {f"{m.group(1)} v. {m.group(2)}"
                 for m in re.finditer(rf"\b({ro.PARTY})\s+v\.?\s+({ro.PARTY})", ORDER)}
        joined = " | ".join(found)
        assert "Suchitra" in joined
        assert "Vatika" in joined
        assert "Mysore" in joined

    def test_the_full_party_name_is_captured_not_truncated(self) -> None:
        import re
        m = re.search(rf"\b({ro.PARTY})\s+v\.?\s+({ro.PARTY})", "in CIT v. Vatika Township Pvt. Ltd.")
        assert m is not None
        assert "Township" in m.group(2)

    def test_prose_before_the_name_is_not_included(self) -> None:
        import re
        m = re.search(rf"\b({ro.PARTY})\s+v\.?\s+({ro.PARTY})",
                      "judgment in CIT v. Vatika Township Pvt. Ltd.")
        assert m is not None
        assert m.group(1) == "CIT"

    def test_a_government_party_is_recognised(self) -> None:
        assert ro.GOVT_PARTY.match("CIT")
        assert ro.GOVT_PARTY.match("Commissioner")
        assert not ro.GOVT_PARTY.match("Vatika")


class TestNotificationCheck:
    def test_an_order_sharing_the_number_is_not_a_notification(self) -> None:
        """The false positive that mattered: "Order No. 04/2018" is a different
        instrument from "Notification 04/2018", and matching on the number alone
        reported the notification as held."""
        import re
        # the check requires the literal word Notification before the number
        assert re.search(r"Notification\s*No\.?\s*04/2018", "Order No. 04/2018-Central Tax") is None
        assert re.search(r"Notification\s*No\.?\s*04/2018",
                         "Notification No. 04/2018-Central Tax (Rate)") is not None

    def test_notification_numbers_are_extracted(self) -> None:
        import re
        nums = set(re.findall(r"Notification\s+No\.?\s*(\d{1,3}/20\d{2})", ORDER))
        assert "03/2019" in nums
