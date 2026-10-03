import json
from pathlib import Path

for path in ['output/evaluations.json', 'output/rejected.json']:
    data = json.load(open(path, encoding='utf-8'))
    print(f"=== {path} ({len(data)} items) ===")
    for e in data:
        p = e['programme']
        lang = p.get('language', {})
        t_lang = lang.get('teaching_language')
        eng = lang.get('english_cefr_required')
        fr = lang.get('french_level_required') or lang.get('french_cefr_required')
        print(f"Univ: {p['university']}")
        print(f"  Prog: {p['programme']} | Track: {p.get('track')} | Level: {p.get('level')}")
        print(f"  Teaching Lang: {t_lang} | Eng req: {eng} | Fr req: {fr}")
        print(f"  Group: {e.get('group')} | Fit: {e.get('score', {}).get('profile_fit_score')} | Conf: {e.get('score', {}).get('evidence_confidence_score')}")
        print(f"  Cycle: {e.get('cycle_readiness')} | Route: {p.get('application_route')}")
        print(f"  Prereqs: {p.get('explicit_prerequisites')}")
        sources = [s.get('source_url') for s in p.get('official_sources', [])]
        print(f"  Sources count: {len(sources)}: {sources[:2]}")
        print("-" * 50)
