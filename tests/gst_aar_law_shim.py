"""Test-only shim: expose gst-aar/law/law_db.py as `law_db`."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "law_db", Path(__file__).parent.parent / "gst-aar" / "law" / "law_db.py")
law_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(law_db)

_api_spec = importlib.util.spec_from_file_location(
    "harvest_cbic_api",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_cbic_api.py")
harvest_cbic_api = importlib.util.module_from_spec(_api_spec)
_api_spec.loader.exec_module(harvest_cbic_api)

_flat_spec = importlib.util.spec_from_file_location(
    "harvest_cbic_flat",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_cbic_flat.py")
harvest_cbic_flat = importlib.util.module_from_spec(_flat_spec)
_flat_spec.loader.exec_module(harvest_cbic_flat)

_cg_spec = importlib.util.spec_from_file_location(
    "harvest_council_gazette",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_council_gazette.py")
harvest_council_gazette = importlib.util.module_from_spec(_cg_spec)
_cg_spec.loader.exec_module(harvest_council_gazette)

_cd_spec = importlib.util.spec_from_file_location(
    "check_daily",
    Path(__file__).parent.parent / "gst-aar" / "law" / "check_daily.py")
check_daily = importlib.util.module_from_spec(_cd_spec)
_cd_spec.loader.exec_module(check_daily)

_el_spec = importlib.util.spec_from_file_location(
    "embed_law",
    Path(__file__).parent.parent / "gst-aar" / "law" / "embed_law.py")
embed_law = importlib.util.module_from_spec(_el_spec)
_el_spec.loader.exec_module(embed_law)

_lo_spec = importlib.util.spec_from_file_location(
    "law_ontology",
    Path(__file__).parent.parent / "gst-aar" / "law" / "law_ontology.py")
law_ontology = importlib.util.module_from_spec(_lo_spec)
_lo_spec.loader.exec_module(law_ontology)

_sd_spec = importlib.util.spec_from_file_location(
    "status_dashboard",
    Path(__file__).parent.parent / "gst-aar" / "law" / "status_dashboard.py")
status_dashboard = importlib.util.module_from_spec(_sd_spec)
_sd_spec.loader.exec_module(status_dashboard)

_tg_spec = importlib.util.spec_from_file_location(
    "harvest_tgct",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_tgct.py")
harvest_tgct = importlib.util.module_from_spec(_tg_spec)
_tg_spec.loader.exec_module(harvest_tgct)

_wb_spec = importlib.util.spec_from_file_location(
    "harvest_wb",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_wb.py")
harvest_wb = importlib.util.module_from_spec(_wb_spec)
_wb_spec.loader.exec_module(harvest_wb)

_hs_spec = importlib.util.spec_from_file_location(
    "_https",
    Path(__file__).parent.parent / "gst-aar" / "law" / "_https.py")
_https = importlib.util.module_from_spec(_hs_spec)
_hs_spec.loader.exec_module(_https)

_od_spec = importlib.util.spec_from_file_location(
    "harvest_od",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_od.py")
harvest_od = importlib.util.module_from_spec(_od_spec)
_od_spec.loader.exec_module(harvest_od)

_mh_spec = importlib.util.spec_from_file_location(
    "harvest_mh",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_mh.py")
harvest_mh = importlib.util.module_from_spec(_mh_spec)
_mh_spec.loader.exec_module(harvest_mh)

_as_spec = importlib.util.spec_from_file_location(
    "harvest_as",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_as.py")
harvest_as = importlib.util.module_from_spec(_as_spec)
_as_spec.loader.exec_module(harvest_as)

_br_spec = importlib.util.spec_from_file_location(
    "harvest_br",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_br.py")
harvest_br = importlib.util.module_from_spec(_br_spec)
_br_spec.loader.exec_module(harvest_br)

_pb_spec = importlib.util.spec_from_file_location(
    "harvest_pb",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_pb.py")
harvest_pb = importlib.util.module_from_spec(_pb_spec)
_pb_spec.loader.exec_module(harvest_pb)

_cg_spec = importlib.util.spec_from_file_location(
    "harvest_cg",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_cg.py")
harvest_cg = importlib.util.module_from_spec(_cg_spec)
_cg_spec.loader.exec_module(harvest_cg)

_dl_spec = importlib.util.spec_from_file_location(
    "harvest_dl",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_dl.py")
harvest_dl = importlib.util.module_from_spec(_dl_spec)
_dl_spec.loader.exec_module(harvest_dl)

_kl_spec = importlib.util.spec_from_file_location(
    "harvest_kl",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_kl.py")
harvest_kl = importlib.util.module_from_spec(_kl_spec)
_kl_spec.loader.exec_module(harvest_kl)

_ka_spec = importlib.util.spec_from_file_location(
    "harvest_ka",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_ka.py")
harvest_ka = importlib.util.module_from_spec(_ka_spec)
_ka_spec.loader.exec_module(harvest_ka)

_up_spec = importlib.util.spec_from_file_location(
    "harvest_up",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_up.py")
harvest_up = importlib.util.module_from_spec(_up_spec)
_up_spec.loader.exec_module(harvest_up)

_tn_spec = importlib.util.spec_from_file_location(
    "harvest_tn",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_tn.py")
harvest_tn = importlib.util.module_from_spec(_tn_spec)
_tn_spec.loader.exec_module(harvest_tn)

_hr_spec = importlib.util.spec_from_file_location(
    "harvest_hr",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_hr.py")
harvest_hr = importlib.util.module_from_spec(_hr_spec)
_hr_spec.loader.exec_module(harvest_hr)

_gj_spec = importlib.util.spec_from_file_location(
    "harvest_gj",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_gj.py")
harvest_gj = importlib.util.module_from_spec(_gj_spec)
_gj_spec.loader.exec_module(harvest_gj)

_rj_spec = importlib.util.spec_from_file_location(
    "harvest_rj",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_rj.py")
harvest_rj = importlib.util.module_from_spec(_rj_spec)
_rj_spec.loader.exec_module(harvest_rj)

_ap_spec = importlib.util.spec_from_file_location(
    "harvest_ap",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_ap.py")
harvest_ap = importlib.util.module_from_spec(_ap_spec)
_ap_spec.loader.exec_module(harvest_ap)

_rx_spec = importlib.util.spec_from_file_location(
    "reindex_fts",
    Path(__file__).parent.parent / "gst-aar" / "law" / "reindex_fts.py")
reindex_fts = importlib.util.module_from_spec(_rx_spec)
_rx_spec.loader.exec_module(reindex_fts)

_thr_spec = importlib.util.spec_from_file_location(
    "_throttle",
    Path(__file__).parent.parent / "gst-aar" / "law" / "_throttle.py")
_throttle = importlib.util.module_from_spec(_thr_spec)
_thr_spec.loader.exec_module(_throttle)

_ic_spec = importlib.util.spec_from_file_location(
    "harvest_indiacode",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_indiacode.py")
harvest_indiacode = importlib.util.module_from_spec(_ic_spec)
_ic_spec.loader.exec_module(harvest_indiacode)

_gr_spec = importlib.util.spec_from_file_location(
    "harvest_gst_rates",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_gst_rates.py")
harvest_gst_rates = importlib.util.module_from_spec(_gr_spec)
_gr_spec.loader.exec_module(harvest_gst_rates)

_is_spec = importlib.util.spec_from_file_location(
    "harvest_indiacode_states",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_indiacode_states.py")
harvest_indiacode_states = importlib.util.module_from_spec(_is_spec)
_is_spec.loader.exec_module(harvest_indiacode_states)

_rc_spec = importlib.util.spec_from_file_location(
    "rechunk_stale",
    Path(__file__).parent.parent / "gst-aar" / "law" / "rechunk_stale.py")
rechunk_stale = importlib.util.module_from_spec(_rc_spec)
_rc_spec.loader.exec_module(rechunk_stale)

_ls_spec = importlib.util.spec_from_file_location(
    "law_search",
    Path(__file__).parent.parent / "gst-aar" / "law" / "law_search.py")
law_search = importlib.util.module_from_spec(_ls_spec)
_ls_spec.loader.exec_module(law_search)

_cr_spec = importlib.util.spec_from_file_location(
    "harvest_cgst_rules",
    Path(__file__).parent.parent / "gst-aar" / "law" / "harvest_cgst_rules.py")
harvest_cgst_rules = importlib.util.module_from_spec(_cr_spec)
_cr_spec.loader.exec_module(harvest_cgst_rules)

_jc_spec = importlib.util.spec_from_file_location(
    "join_cbic_section_text",
    Path(__file__).parent.parent / "gst-aar" / "law" / "join_cbic_section_text.py")
join_cbic_section_text = importlib.util.module_from_spec(_jc_spec)
_jc_spec.loader.exec_module(join_cbic_section_text)

_nv_spec = importlib.util.spec_from_file_location(
    "normalize_vocab",
    Path(__file__).parent.parent / "gst-aar" / "law" / "normalize_vocab.py")
normalize_vocab = importlib.util.module_from_spec(_nv_spec)
_nv_spec.loader.exec_module(normalize_vocab)

_eo_spec = importlib.util.spec_from_file_location(
    "extract_ontology",
    Path(__file__).parent.parent / "gst-aar" / "extract_ontology.py")
extract_ontology = importlib.util.module_from_spec(_eo_spec)
_eo_spec.loader.exec_module(extract_ontology)

_eh_spec = importlib.util.spec_from_file_location(
    "eval_harness",
    Path(__file__).parent.parent / "gst-aar" / "law" / "eval_harness.py")
eval_harness = importlib.util.module_from_spec(_eh_spec)
_eh_spec.loader.exec_module(eval_harness)

_ss_spec = importlib.util.spec_from_file_location(
    "split_sgst_acts",
    Path(__file__).parent.parent / "gst-aar" / "law" / "split_sgst_acts.py")
split_sgst_acts = importlib.util.module_from_spec(_ss_spec)
_ss_spec.loader.exec_module(split_sgst_acts)

_ig_spec = importlib.util.spec_from_file_location(
    "industry_guide",
    Path(__file__).parent.parent / "gst-aar" / "law" / "industry_guide.py")
industry_guide = importlib.util.module_from_spec(_ig_spec)
_ig_spec.loader.exec_module(industry_guide)

_do_spec = importlib.util.spec_from_file_location(
    "diagnose_outcomes",
    Path(__file__).parent.parent / "gst-aar" / "law" / "diagnose_outcomes.py")
diagnose_outcomes = importlib.util.module_from_spec(_do_spec)
_do_spec.loader.exec_module(diagnose_outcomes)

_dc_spec = importlib.util.spec_from_file_location(
    "dispute_causes",
    Path(__file__).parent.parent / "gst-aar" / "law" / "dispute_causes.py")
dispute_causes = importlib.util.module_from_spec(_dc_spec)
_dc_spec.loader.exec_module(dispute_causes)

_ro_spec = importlib.util.spec_from_file_location(
    "review_order",
    Path(__file__).parent.parent / "gst-aar" / "law" / "review_order.py")
review_order = importlib.util.module_from_spec(_ro_spec)
_ro_spec.loader.exec_module(review_order)
