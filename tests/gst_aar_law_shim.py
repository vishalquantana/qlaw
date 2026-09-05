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
