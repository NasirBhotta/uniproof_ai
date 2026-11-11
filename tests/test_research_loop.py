from france_admission_agent.pipeline import loop


def test_loop_stops_at_seven_without_discovery(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(loop, 'get_default_search_client', lambda: object())
    monkeypatch.setattr(loop, 'run_pending', lambda *a, **k: calls.append('pending'))
    monkeypatch.setattr(loop, 'quarantine_discovery_noise', lambda db: [])
    monkeypatch.setattr(loop, 'pending_priority', lambda db: [])
    monkeypatch.setattr(loop, 'verified_count', lambda db: 7)
    monkeypatch.setattr(loop, 'execute_discovery_round', lambda **k: calls.append('discovery'))
    monkeypatch.setattr(loop, 'final_selection', lambda db, out: {'finalists': 7, 'report': str(tmp_path / 'Final-Selection.md')})
    result = loop.run_research_loop(output_dir=tmp_path)
    assert result['stop_reason'] == 'SEVEN_VERIFIED'
    assert result['rounds_completed'] == 0
    assert calls == ['pending']


def test_loop_stops_on_repeated_zero_yield(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(loop, 'get_default_search_client', lambda: object())
    monkeypatch.setattr(loop, 'run_pending', lambda *a, **k: None)
    monkeypatch.setattr(loop, 'quarantine_discovery_noise', lambda db: [])
    monkeypatch.setattr(loop, 'pending_priority', lambda db: [])
    monkeypatch.setattr(loop, 'verified_count', lambda db: 0)
    monkeypatch.setattr(loop, 'pending_priority', lambda db: [])
    def discovery(**kwargs):
        calls.append(kwargs)
        return {'round_number': len(calls), 'stop_reason': 'BOUNDED_LOW_YIELD', 'programmes_discovered': 0,
                'provider_calls_successful': 2, 'pipeline': {}}
    monkeypatch.setattr(loop, 'execute_discovery_round', discovery)
    monkeypatch.setattr(loop, 'final_selection', lambda db, out: {'finalists': 0, 'report': str(tmp_path / 'Final-Selection.md')})
    result = loop.run_research_loop(output_dir=tmp_path, max_rounds=6, stop_after_empty_rounds=2)
    assert result['stop_reason'] == 'REPEATED_ZERO_YIELD'
    assert result['rounds_completed'] == 2
    assert all(call['incremental'] for call in calls)


def test_loop_without_provider_preserves_final_report(monkeypatch, tmp_path):
    monkeypatch.setattr(loop, 'get_default_search_client', lambda: None)
    monkeypatch.setattr(loop, 'quarantine_discovery_noise', lambda db: [])
    monkeypatch.setattr(loop, 'verified_count', lambda db: 0)
    monkeypatch.setattr(loop, 'execute_discovery_round', lambda **k: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(loop, 'final_selection', lambda db, out: {'finalists': 0, 'report': str(tmp_path / 'Final-Selection.md')})
    result = loop.run_research_loop(output_dir=tmp_path)
    assert result['stop_reason'] == 'SEARCH_PROVIDER_UNAVAILABLE'
    assert result['rounds_completed'] == 0


def test_backlog_is_researched_before_more_discovery(monkeypatch, tmp_path):
    monkeypatch.setattr(loop, 'get_default_search_client', lambda: object())
    monkeypatch.setattr(loop, 'run_pending', lambda *a, **k: None)
    monkeypatch.setattr(loop, 'quarantine_discovery_noise', lambda db: [])
    monkeypatch.setattr(loop, 'pending_priority', lambda db: [{'programme_id': 'one'}])
    monkeypatch.setattr(loop, 'research_backlog', lambda *a, **k: [{'state': 'CYCLE1_REVIEW_REQUIRED', 'searches': 2}])
    monkeypatch.setattr(loop, 'verified_count', lambda db: 0)
    monkeypatch.setattr(loop, 'execute_discovery_round', lambda **k: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(loop, 'final_selection', lambda db, out: {'finalists': 0, 'report': str(tmp_path / 'Final-Selection.md')})
    result = loop.run_research_loop(output_dir=tmp_path, max_rounds=1)
    assert result['rounds'][0]['stage'] == 'TARGETED_BACKLOG'
    assert result['rounds'][0]['provider_calls_successful'] == 2
