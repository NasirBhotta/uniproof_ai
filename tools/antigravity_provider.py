"""
Re-export from root antigravity_provider.py safely without circular shadowing.
"""
from pathlib import Path
import importlib.util

_root_file = Path(__file__).resolve().parents[1] / "antigravity_provider.py"
_spec = importlib.util.spec_from_file_location("_root_antigravity_provider", _root_file)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

AntigravityLLMProvider = _mod.AntigravityLLMProvider
AntigravityStructuredLLM = _mod.AntigravityStructuredLLM
extract_json_text = _mod.extract_json_text

__all__ = ["AntigravityLLMProvider", "AntigravityStructuredLLM", "extract_json_text"]
