from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from france_admission_agent.search.tavily import TavilySearchClient

client = TavilySearchClient()
batch = client.search(
    "site:monmaster.gouv.fr master informatique M1",
    max_results=5,
    include_raw_content=False,
)
for r in batch.results:
    print(r.title)
    print(r.url)
    print(r.snippet[:300])
    print("-")
