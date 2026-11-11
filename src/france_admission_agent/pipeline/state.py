from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

VERSION = 'incremental-2'

SCHEMA = """
CREATE TABLE IF NOT EXISTS programme_workflow (
 programme_id TEXT PRIMARY KEY REFERENCES programmes(programme_id),
 institution_id TEXT NOT NULL, track_id TEXT NOT NULL, identity_key TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'DISCOVERED_NEW', discovered_round INTEGER,
 cycle1_status TEXT NOT NULL DEFAULT 'NOT_PROCESSED', cycle1_version TEXT, cycle1_processed_at TEXT,
 cycle2_status TEXT NOT NULL DEFAULT 'NOT_PROCESSED', cycle2_version TEXT, cycle2_processed_at TEXT,
 pool_status TEXT NOT NULL DEFAULT 'NOT_REVIEWED', evidence_version INTEGER NOT NULL DEFAULT 0,
 evidence_last_updated TEXT, needs_refresh INTEGER NOT NULL DEFAULT 0, refresh_reason TEXT,
 refresh_fields TEXT NOT NULL DEFAULT '[]', resume_state TEXT,
 superseded_by TEXT, supersession_reason TEXT, target_intake TEXT,
 candidate_json TEXT, cycle1_json TEXT, cycle2_json TEXT, vector_json TEXT,
 last_error TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_workflow_state ON programme_workflow(state);
CREATE INDEX IF NOT EXISTS idx_workflow_identity ON programme_workflow(identity_key);
CREATE TABLE IF NOT EXISTS pipeline_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, programme_id TEXT NOT NULL,
 from_state TEXT, to_state TEXT NOT NULL, reason TEXT,
 round_number INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pipeline_rounds (
 round_number INTEGER PRIMARY KEY, metrics_json TEXT NOT NULL,
 actual_searches INTEGER NOT NULL, successful_searches INTEGER NOT NULL,
 distinct_frontiers INTEGER NOT NULL, pool_improvements INTEGER NOT NULL,
 stop_reason TEXT, completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS discovery_frontiers (
 frontier_key TEXT PRIMARY KEY, region TEXT, department TEXT, city TEXT,
 institution_id TEXT, programme_family TEXT, track TEXT, purpose TEXT,
 attempts INTEGER NOT NULL DEFAULT 0, last_round INTEGER, last_searched TEXT
);
"""

TRANSITIONS = {
 'DISCOVERED_NEW': {'CYCLE1_PENDING', 'DISCOVERY_REJECTED'},
 'CYCLE1_PENDING': {'CYCLE1_PROCESSING'},
 'CYCLE1_PROCESSING': {'CYCLE1_PASSED', 'CYCLE1_REJECTED', 'CYCLE1_PENDING', 'CYCLE1_REVIEW_REQUIRED'},
 'CYCLE1_REVIEW_REQUIRED': {'CYCLE1_PENDING'},
 'CYCLE1_PASSED': {'PROMOTION_REVIEW'},
 'PROMOTION_REVIEW': {'CYCLE2_PENDING', 'POOL_DROPPED', 'CYCLE1_REVIEW_REQUIRED'},
 'CYCLE2_PENDING': {'CYCLE2_PROCESSING'},
 'CYCLE2_PROCESSING': {'CYCLE2_VERIFIED', 'CYCLE2_REJECTED', 'CYCLE2_REVIEW_REQUIRED', 'CYCLE2_PENDING'},
 'CYCLE2_VERIFIED': {'POOL_RETAINED', 'POOL_DROPPED'},
 'CYCLE2_REVIEW_REQUIRED': {'POOL_DROPPED'},
 'POOL_RETAINED': {'POOL_DROPPED', 'FINAL_CANDIDATE'},
 'FINAL_CANDIDATE': {'POOL_DROPPED', 'POOL_RETAINED'},
 'REQUIRES_REFRESH': {'CYCLE1_PASSED', 'CYCLE1_REJECTED', 'CYCLE1_REVIEW_REQUIRED', 'CYCLE2_VERIFIED', 'CYCLE2_REVIEW_REQUIRED', 'CYCLE2_REJECTED'},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())


def identity(institution_id, programme, track, level='M1'):
    return hashlib.sha256('::'.join(normalized(v) for v in (institution_id, programme, track, level)).encode()).hexdigest()


def transition(conn, pid, state, reason='', round_number=None):
    row = conn.execute('SELECT state FROM programme_workflow WHERE programme_id=?', (pid,)).fetchone()
    old = row['state'] if row else None
    if old == state:
        return
    allowed = state == 'REQUIRES_REFRESH' and old is not None and not old.endswith('PROCESSING')
    if not allowed and state not in TRANSITIONS.get(old, set()):
        raise ValueError(f'INVALID_PIPELINE_STATE_TRANSITION: {pid}: {old} -> {state}')
    conn.execute('UPDATE programme_workflow SET state=?, updated_at=? WHERE programme_id=?', (state, now(), pid))
    for stage in ('cycle1','cycle2'):
        if state.startswith(stage.upper()+'_'):
            conn.execute(f'UPDATE programme_workflow SET {stage}_status=? WHERE programme_id=?', (state[len(stage)+1:],pid))
    conn.execute('INSERT INTO pipeline_events(programme_id,from_state,to_state,reason,round_number) VALUES (?,?,?,?,?)',
                 (pid, old, state, reason, round_number))


def migrate(conn, output_dir='output', intake='2027'):
    """One-time per-record migration; missing evidence never queues legacy work automatically."""
    conn.executescript(SCHEMA)
    existing={r[1] for r in conn.execute('PRAGMA table_info(programme_workflow)')}
    for name in ('cycle1_vector_json','cycle1_comparison_json'):
        if name not in existing:
            conn.execute(f'ALTER TABLE programme_workflow ADD COLUMN {name} TEXT')
    c1, c2 = {}, {}
    path = Path(output_dir) / 'cycle1_results.json'
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        c1 = {x['programme']['programme_id']: x for key in ('evaluations','rejected','final_shortlist') for x in data.get(key, [])}
    path = Path(output_dir) / 'cycle2_analysis.json'
    if path.exists():
        c2 = {x['programme']['programme_id']: x for x in json.loads(path.read_text(encoding='utf-8'))}
    rows = conn.execute('SELECT p.*, u.canonical_name FROM programmes p JOIN universities u USING(institution_id) LEFT JOIN programme_workflow w USING(programme_id) WHERE w.programme_id IS NULL').fetchall()
    for row in rows:
        pid = row['programme_id']; a = c1.get(pid); b = c2.get(pid)
        if b and not a:
            a = b.get('cycle1_evaluation')
        state = 'LEGACY_REVIEW'
        if a:
            state = 'CYCLE1_REJECTED' if a.get('rejected') else 'CYCLE1_PASSED'
        if b:
            # Analysis completed, but verification must pass current evidence gates.
            state = 'CYCLE2_REVIEW_REQUIRED'
        payload = (a or b or {}).get('programme')
        if not payload:
            payload = dict(programme_id=pid, institution_id=row['institution_id'],track_id=row['track_id'],
                university=row['canonical_name'], programme=row['programme_name'], track=row['track_name'],
                level=row['level'], city=row['city'] or 'Unknown', programme_url=row['official_url'], public=None)
        conn.execute('''INSERT INTO programme_workflow(programme_id,institution_id,track_id,identity_key,state,
           cycle1_status,cycle1_version,cycle1_processed_at,cycle2_status,cycle2_version,cycle2_processed_at,
           candidate_json,cycle1_json,cycle2_json,target_intake,refresh_reason)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
           (pid,row['institution_id'],row['track_id'] or '', identity(row['institution_id'],row['programme_name'],row['track_name'],row['level']),state,
            ('REJECTED' if a.get('rejected') else 'PASSED') if a else 'LEGACY_UNKNOWN', 'legacy' if a else None,row['last_verified'] if a else None,
            'ANALYZED_UNVERIFIED' if b else 'NOT_PROCESSED','legacy' if b else None,row['last_verified'] if b else None,
            json.dumps(payload),json.dumps(a) if a else None,json.dumps(b) if b else None,intake,
            'Legacy provenance retained; no automatic reprocessing' if not a else None))
        conn.execute('INSERT INTO pipeline_events(programme_id,to_state,reason) VALUES (?,?,?)', (pid,state,'Legacy migration; original records preserved'))
        conn.execute('UPDATE programme_workflow SET evidence_last_updated=(SELECT MAX(retrieved_at) FROM evidence WHERE programme_id=?) WHERE programme_id=?', (pid,pid))
    conn.commit()
    return len(rows)


def request_refresh(conn, pid, fields, reason):
    supported = {'language','calendar','historical','degree','structure','prerequisites','route','tuition','stability'}
    if not fields or set(fields) - supported:
        raise ValueError('Refresh requires explicit supported fields')
    row = conn.execute('SELECT * FROM programme_workflow WHERE programme_id=?', (pid,)).fetchone()
    if row is None:
        raise KeyError(pid)
    merged = sorted(set(json.loads(row['refresh_fields'])) | set(fields))
    transition(conn, pid, 'REQUIRES_REFRESH', reason)
    conn.execute('UPDATE programme_workflow SET needs_refresh=1,refresh_fields=?,refresh_reason=?,resume_state=COALESCE(resume_state,?) WHERE programme_id=?',
                 (json.dumps(merged),reason,row['state'],pid))
    conn.commit()


def recover(conn):
    # Called under the process-wide database lock, after any previous owner exited.
    for row in conn.execute("SELECT programme_id,state FROM programme_workflow WHERE state IN ('CYCLE1_PROCESSING','CYCLE2_PROCESSING')").fetchall():
        transition(conn,row['programme_id'],row['state'].replace('PROCESSING','PENDING'),'Recovered interrupted work')
    conn.commit()


from contextlib import contextmanager

@contextmanager
def pipeline_lock(db_path):
    """OS lock is automatically released on crash; no expired-lease guessing."""
    path = Path(str(db_path) + '.pipeline.lock'); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as f:
        f.seek(0); f.write(b'0'); f.flush(); f.seek(0)
        if __import__('os').name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            f.seek(0)
            if __import__('os').name == 'nt':
                msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(f,fcntl.LOCK_UN)
