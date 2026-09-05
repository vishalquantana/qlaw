def test_diff_listings_finds_new_urls():
    from gst_aar_law_shim import check_daily as cd

    old = [{"source_url": "https://cbic-gst.gov.in/pdf/a.pdf"}]
    new = old + [{"source_url": "https://cbic-gst.gov.in/pdf/b.pdf"}]
    assert cd.diff_listings(old, new) == [
        {"source_url": "https://cbic-gst.gov.in/pdf/b.pdf"}]


def test_diff_listings_accepts_pdf_url_rows_and_skips_keyless():
    from gst_aar_law_shim import check_daily as cd

    old = [{"pdf_url": "https://cbic-gst.gov.in/pdf/a.pdf"}]
    new = [
        {"pdf_url": "https://cbic-gst.gov.in/pdf/a.pdf"},  # already seen via pdf_url
        {"pdf_url": "https://cbic-gst.gov.in/pdf/b.pdf"},  # new via pdf_url
        {"date": "2026-09-01"},  # missing both keys → skipped, no KeyError
        {"source_url": "https://cbic-gst.gov.in/pdf/c.pdf"},
    ]
    assert cd.diff_listings(old, new) == [
        {"pdf_url": "https://cbic-gst.gov.in/pdf/b.pdf"},
        {"source_url": "https://cbic-gst.gov.in/pdf/c.pdf"},
    ]


def test_main_tolerates_nondict_jsonl_line(tmp_path, monkeypatch, capsys):
    import json

    from gst_aar_law_shim import check_daily as cd

    changes = tmp_path / "changes.jsonl"
    changes.write_text(
        json.dumps(42) + "\n"
        + json.dumps({"source_url": "https://cbic-gst.gov.in/pdf/a.pdf"}) + "\n"
    )
    monkeypatch.setattr(cd, "CHANGES", changes)
    monkeypatch.setattr(cd, "disk_ok", lambda: True)
    cd.main()  # must not raise on the non-dict (int) line
    out = capsys.readouterr().out
    assert "known changes: 1" in out


def test_main_rejects_bad_since(monkeypatch):
    import pytest

    from gst_aar_law_shim import check_daily as cd

    monkeypatch.setattr(cd, "disk_ok", lambda: True)
    with pytest.raises(SystemExit) as ei:
        cd.main(since="09/01/2026")
    assert "--since must be YYYY-MM-DD" in str(ei.value)


def test_main_apply_prints_pending_no_writes(monkeypatch, capsys):
    from gst_aar_law_shim import check_daily as cd

    monkeypatch.setattr(cd, "disk_ok", lambda: True)
    cd.main(apply=True)  # exit 0, no writes
    assert "apply: harvester wiring pending, no writes performed" in capsys.readouterr().out
