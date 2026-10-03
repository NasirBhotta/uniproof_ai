"""Contract-only example — intentionally does NOT contain Gemini SDK code.

You said you will connect Gemini yourself. Implement the two methods below using
whatever Gemini SDK/version you choose, then pass the adapters into
EvidenceFirstResearchBackend.
"""

from france_admission_agent.llm import StructuredLLM
from france_admission_agent.search.base import SearchClient


class MyGeminiStructuredLLM:
    def generate_structured(self, *, system, prompt, response_model):
        # 1. Call Gemini with system + prompt.
        # 2. Ask for JSON matching response_model.model_json_schema().
        # 3. Parse/validate with:
        #    return response_model.model_validate_json(json_text)
        raise NotImplementedError


class MySearchClient:
    def search(
        self,
        query,
        *,
        max_results=10,
        search_depth="advanced",
        include_domains=None,
        exclude_domains=None,
        include_raw_content=True,
    ):
        # Option A: Gemini/Google Search grounding adapter.
        # Option B: TavilySearchClient already included in this project.
        # Must return france_admission_agent.search.models.SearchBatch.
        raise NotImplementedError
