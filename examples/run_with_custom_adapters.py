"""Wire your own Gemini/search adapters here, then run the full LangGraph workflow."""

from france_admission_agent.research.backend import EvidenceFirstResearchBackend
from france_admission_agent.runner import run_research
from france_admission_agent.search.cache import CachedSearchClient

# Replace these imports with your implementations from gemini_adapter_contract.py.
# from my_adapters import MyGeminiStructuredLLM, MySearchClient


def main():
    # llm = MyGeminiStructuredLLM(...)
    # search = CachedSearchClient(MySearchClient(...), cache_dir=".cache/search")
    # backend = EvidenceFirstResearchBackend(llm=llm, search=search)
    # result, paths = run_research(backend)
    # print(result["stop_reason"])
    # print(paths["report"])
    raise RuntimeError("Connect your Gemini StructuredLLM + SearchClient first.")


if __name__ == "__main__":
    main()
