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
