"""
Example: Running France Admission Agent with Antigravity Language Server Adapter
Author: Nasir Bhutta
Description: Connects the agentic workflow to the local Antigravity Language Server
             via AntigravityStructuredLLM without needing an external Gemini API key.
"""

import os
import sys
from pathlib import Path

# Add project root and src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from antigravity_provider import AntigravityStructuredLLM
from france_admission_agent.research.backend import EvidenceFirstResearchBackend
from france_admission_agent.runner import run_research
from france_admission_agent.search.cache import CachedSearchClient
from france_admission_agent.search.tavily import TavilySearchClient


def main():
    print("=" * 65)
    print(" [*] FRANCE ADMISSION AGENT - ANTIGRAVITY ENGINE RUNNER")
    print("=" * 65)

    # 1. Initialize Antigravity Structured LLM Adapter (No external Gemini API key needed!)
    print("\n[+] Connecting to Antigravity Language Server...")
    llm = AntigravityStructuredLLM()

    # 2. Configure Search Provider (e.g. Tavily or custom search client)
    # Search client handles web discovery and official document retrieval
    search_api_key = os.getenv("TAVILY_API_KEY")
    if not search_api_key:
        print("[!] Note: TAVILY_API_KEY not set. Ensure search provider is configured")
        print("    or inject your custom search client implementation.")
        return

    search_client = CachedSearchClient(
        TavilySearchClient(api_key=search_api_key, timeout=60.0),
        cache_dir=str(PROJECT_ROOT / ".cache" / "search"),
    )

    # 3. Mount Backend and Execute LangGraph Research Engine with Token-Efficient Config
    print("[+] Initializing EvidenceFirstResearchBackend with Token-Efficient Config...")
    backend = EvidenceFirstResearchBackend(
        llm=llm,
        search=search_client,
        discovery_max_queries=12,
        discovery_per_query=7,
        verification_per_query=3,
    )

    print("[*] Launching admissions research workflow (Target: Best 7 Options)...")
    result, paths = run_research(
        backend,
        target_count=7,
        discovery_batch_size=20,
        max_discovery_rounds=3,
    )

    print("\n" + "=" * 65)
    print(f"[+] Workflow Completed! Stop Reason: {result.get('stop_reason')}")
    print(f"[+] Final Admission Report : {paths.get('report')}")
    print("=" * 65)


if __name__ == "__main__":
    main()
