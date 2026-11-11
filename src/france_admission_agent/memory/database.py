"""
SQLite Persistent Research Memory Database Manager
Author: Nasir Bhutta
Description: Manages local SQLite connection, WAL mode, foreign keys,
             and table creation for France Master's research memory.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/france_research.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 1. Universities / Institutions
CREATE TABLE IF NOT EXISTS universities (
    institution_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    aliases TEXT,                 -- JSON array of strings
    city TEXT,
    region TEXT,
    is_public BOOLEAN DEFAULT 1,
    official_domains TEXT,        -- JSON array of domain strings
    international_admission_rules TEXT,
    etudes_en_france_policy TEXT,
    pakistan_route TEXT,
    foreign_degree_policy TEXT,
    tuition_policy TEXT,
    application_platforms TEXT,   -- JSON array
    official_admissions_url TEXT,
    coverage_status TEXT DEFAULT 'NOT_RESEARCHED', -- NOT_RESEARCHED, PARTIALLY_RESEARCHED, SUBSTANTIALLY_RESEARCHED, EXHAUSTED_FOR_CURRENT_PROFILE
    institution_discovery_complete BOOLEAN DEFAULT 0,
    official_inventory_confirmed BOOLEAN DEFAULT 0,
    last_verified TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 2. Programmes / Tracks
CREATE TABLE IF NOT EXISTS programmes (
    programme_id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    track_id TEXT DEFAULT 'core',
    programme_name TEXT NOT NULL,
    track_name TEXT,
    level TEXT DEFAULT 'M1',
    m1_m2_structure TEXT,
    campus TEXT,
    city TEXT,
    official_url TEXT,
    admissions_url TEXT,
    academic_strictness TEXT DEFAULT 'UNKNOWN',
    degree_strictness TEXT DEFAULT 'UNKNOWN',
    prerequisite_strictness TEXT DEFAULT 'UNKNOWN',
    selectivity_pressure TEXT DEFAULT 'UNKNOWN',
    international_complexity TEXT DEFAULT 'UNKNOWN',
    language_risk TEXT DEFAULT 'UNKNOWN',
    candidate_fit_strength TEXT DEFAULT 'UNKNOWN',
    candidate_strengths TEXT,     -- JSON array
    candidate_weaknesses TEXT,    -- JSON array
    reasons_competitive TEXT,     -- JSON array
    reasons_fail TEXT,            -- JSON array
    unresolved_fields TEXT,       -- JSON array
    profile_fit_score REAL DEFAULT 0.0,
    evidence_confidence_score REAL DEFAULT 0.0,
    score_status TEXT DEFAULT 'PROVISIONAL',
    cycle1_group TEXT,            -- A_FULLY_VERIFIED, B_CALENDAR_PENDING, C_LANGUAGE_VERIFICATION_REQUIRED, D_NEEDS_OTHER_VERIFICATION, E_REJECTED
    is_viable BOOLEAN DEFAULT 0,
    is_rejected BOOLEAN DEFAULT 0,
    rejection_reasons TEXT,       -- JSON array
    last_verified TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES universities(institution_id) ON DELETE CASCADE
);

-- 3. Programme Intake Cycles
CREATE TABLE IF NOT EXISTS programme_cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id TEXT NOT NULL,
    target_intake TEXT DEFAULT '2027',
    status TEXT NOT NULL,         -- OPEN, PENDING_PUBLICATION, VERIFIED_NOT_OPEN, CLOSED, UNVERIFIED
    opening_date TEXT,
    deadline TEXT,
    source_cycle TEXT,
    source_url TEXT,
    last_verified TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 4. Programme Academic Requirements
CREATE TABLE IF NOT EXISTS programme_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id TEXT NOT NULL,
    accepted_degree_fields TEXT,  -- JSON array
    explicit_prerequisites TEXT,  -- JSON array
    degree_status TEXT DEFAULT 'UNVERIFIED', -- PASS, FAIL, UNVERIFIED
    transcript_match_coverage REAL DEFAULT 0.0,
    transcript_match_status TEXT DEFAULT 'UNVERIFIED',
    matched_courses TEXT,         -- JSON array
    unmatched_topics TEXT,        -- JSON array
    last_verified TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 5. Programme Language Requirements
CREATE TABLE IF NOT EXISTS programme_languages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id TEXT NOT NULL,
    teaching_language_status TEXT DEFAULT 'LANGUAGE_UNVERIFIED', -- VERIFIED_ENGLISH, VERIFIED_FRENCH, VERIFIED_MIXED, LANGUAGE_UNVERIFIED
    teaching_languages TEXT,      -- JSON array
    english_cefr_required TEXT,
    ielts_overall_min REAL,
    ielts_speaking_min REAL,
    french_level_required TEXT,
    moi_accepted TEXT DEFAULT 'UNVERIFIED',
    evidence_text TEXT,
    last_verified TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 6. Programme Application Routes
CREATE TABLE IF NOT EXISTS programme_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id TEXT NOT NULL,
    route_platform TEXT,          -- Études en France, Mon Master, eCandidat, Direct Email
    candidate_country_rule TEXT,  -- Pakistan EEF rule
    status TEXT DEFAULT 'UNVERIFIED',
    evidence_text TEXT,
    source_url TEXT,
    last_verified TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 7. Programme Structure
CREATE TABLE IF NOT EXISTS programme_structures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id TEXT NOT NULL,
    m1_entry_status TEXT DEFAULT 'UNVERIFIED', -- PASS, FAIL, UNVERIFIED
    specialization_starts_in TEXT DEFAULT 'UNVERIFIED',
    structure_description TEXT,
    evidence_text TEXT,
    source_url TEXT,
    last_verified TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 8. Admission Statistics (By Academic Year)
CREATE TABLE IF NOT EXISTS admission_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id TEXT NOT NULL,
    academic_year TEXT NOT NULL,  -- e.g. 2024-2025
    applicants INTEGER,
    admitted INTEGER,
    capacity INTEGER,
    derived_ratio REAL,           -- admitted / applicants
    ratio_definition TEXT,
    population TEXT,
    source_url TEXT,
    source_name TEXT,
    verification_status TEXT DEFAULT 'UNVERIFIED_STATISTIC', -- VERIFIED_CURRENT, VERIFIED_HISTORICAL, UNVERIFIED_STATISTIC
    last_verified TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 9. Programme Capacity
CREATE TABLE IF NOT EXISTS programme_capacity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    seats INTEGER NOT NULL,
    source_url TEXT,
    verification_status TEXT DEFAULT 'UNVERIFIED',
    last_verified TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 10. Historical Demand Records
CREATE TABLE IF NOT EXISTS historical_demand (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    applicants INTEGER,
    offers INTEGER,
    enrolled INTEGER,
    source_url TEXT,
    verification_status TEXT DEFAULT 'UNVERIFIED',
    last_verified TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 11. Candidate-Programme Matches & Forecasting
CREATE TABLE IF NOT EXISTS candidate_programme_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    programme_id TEXT NOT NULL,
    academic_fit TEXT,
    risk_band TEXT DEFAULT 'UNKNOWN', -- LOWER, LOWER_MODERATE, MODERATE, MODERATE_HIGH, HIGH, UNKNOWN
    competition_pressure TEXT DEFAULT 'UNKNOWN',
    forecast_pressure TEXT DEFAULT 'UNKNOWN', -- LOW, LOW_MODERATE, MODERATE, HIGH, VERY_HIGH, UNKNOWN
    forecast_trend TEXT DEFAULT 'UNKNOWN',    -- INCREASING, STABLE, DECREASING, UNKNOWN
    forecast_confidence TEXT DEFAULT 'LOW',   -- LOW, MODERATE, HIGH
    candidate_position TEXT,
    evidence_confidence REAL DEFAULT 0.0,
    evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 12. Evidence Ledger
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL,
    programme_id TEXT,
    track_id TEXT,
    claim_type TEXT NOT NULL,
    claim_value TEXT,
    source_url TEXT,
    source_title TEXT,
    source_type TEXT DEFAULT 'official_university',
    source_year TEXT,
    target_cycle TEXT,
    retrieved_at TEXT,
    verification_status TEXT DEFAULT 'UNVERIFIED' -- VERIFIED_CURRENT, VERIFIED_HISTORICAL, UNVERIFIED, CONTRADICTORY, STALE, SUPPLEMENTARY_ONLY
);

-- 13. Source Documents Cache
CREATE TABLE IF NOT EXISTS source_documents (
    url TEXT PRIMARY KEY,
    institution_id TEXT,
    content_hash TEXT,
    page_title TEXT,
    extracted_text TEXT,
    retrieved_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_modified TEXT
);

-- 14. Search History
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    normalized_query TEXT NOT NULL,
    provider TEXT DEFAULT 'tavily',
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    target_institution TEXT,
    target_programme TEXT,
    target_field TEXT,
    search_purpose TEXT,
    region TEXT,
    city TEXT,
    institution_id TEXT,
    programme_id TEXT,
    discovery_round INTEGER DEFAULT 1,
    results_count INTEGER DEFAULT 0,
    useful_results INTEGER DEFAULT 0,
    official_results INTEGER DEFAULT 0,
    fields_resolved INTEGER DEFAULT 0,
    evidence_gain REAL DEFAULT 0.0,
    duplicate_of TEXT,
    cost REAL DEFAULT 0.0
);

-- 15. Query Effectiveness Learning
CREATE TABLE IF NOT EXISTS query_effectiveness (
    pattern TEXT PRIMARY KEY,
    times_used INTEGER DEFAULT 0,
    times_successful INTEGER DEFAULT 0,
    fields_resolved_count INTEGER DEFAULT 0,
    avg_evidence_gain REAL DEFAULT 0.0,
    effectiveness_rating TEXT DEFAULT 'MODERATE', -- HIGH, MODERATE, LOW
    last_used TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 16. Verification Failures
CREATE TABLE IF NOT EXISTS verification_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    institution_id TEXT NOT NULL,
    programme_id TEXT,
    failure_type TEXT NOT NULL,   -- LANGUAGE_INCOMPATIBLE, M2_ONLY, SCOPE_MISMATCH, PREREQUISITE_FAIL
    evidence_summary TEXT,
    source_url TEXT,
    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 17. Research Runs
CREATE TABLE IF NOT EXISTS research_runs (
    run_id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,       -- CYCLE1, CYCLE2, DISCOVERY_ROUND
    started_at TEXT,
    finished_at TEXT,
    programmes_evaluated INTEGER DEFAULT 0,
    viable_count INTEGER DEFAULT 0,
    external_searches INTEGER DEFAULT 0,
    memory_hits INTEGER DEFAULT 0,
    cache_hits INTEGER DEFAULT 0,
    duplicate_searches_blocked INTEGER DEFAULT 0,
    searches_saved_by_memory INTEGER DEFAULT 0,
    fields_resolved INTEGER DEFAULT 0,
    evidence_gain REAL DEFAULT 0.0,
    llm_calls INTEGER DEFAULT 0,
    tokens_used TEXT,
    summary_markdown TEXT,
    distinct_frontiers INTEGER DEFAULT 0,
    distinct_regions INTEGER DEFAULT 0,
    distinct_cities INTEGER DEFAULT 0,
    stop_reason TEXT
);

-- 18. Regional Coverage Map
CREATE TABLE IF NOT EXISTS regional_coverage (
    region TEXT PRIMARY KEY,
    universities_known INTEGER DEFAULT 0,
    universities_checked INTEGER DEFAULT 0,
    programmes_known INTEGER DEFAULT 0,
    programmes_viable INTEGER DEFAULT 0,
    saturation_estimate TEXT DEFAULT 'LOW', -- LOW, MODERATE, HIGH, EXHAUSTED
    coverage_level TEXT DEFAULT 'LOW',     -- LOW, MODERATE, HIGH, INTENTIONALLY_DEPRIORITIZED
    exhaustion_status TEXT DEFAULT 'NOT_TESTED', -- NOT_TESTED, PARTIAL, LIKELY_EXHAUSTED, EXHAUSTED
    strategies_tested TEXT DEFAULT '[]',   -- JSON array of strategies attempted
    last_searched TEXT
);

-- 19. Programme Outcomes (For Future Calibration)
CREATE TABLE IF NOT EXISTS programme_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_year TEXT NOT NULL,
    programme_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    date_applied TEXT,
    outcome TEXT DEFAULT 'UNKNOWN', -- ACCEPTED, REJECTED, WAITLISTED, INTERVIEWED, WITHDRAWN, UNKNOWN
    interview_received BOOLEAN DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- 20. Manual Verification Action Items
CREATE TABLE IF NOT EXISTS manual_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id TEXT NOT NULL,
    check_item TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',  -- PENDING, RESOLVED
    resolution_notes TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (programme_id) REFERENCES programmes(programme_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_programmes_inst ON programmes(institution_id);
CREATE INDEX IF NOT EXISTS idx_programmes_viable ON programmes(is_viable);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(institution_id, claim_type);
CREATE INDEX IF NOT EXISTS idx_search_norm ON search_history(normalized_query);
CREATE INDEX IF NOT EXISTS idx_adm_stats_year ON admission_statistics(programme_id, academic_year);
"""


def migrate_database_schema(conn: sqlite3.Connection) -> None:
    """Safely adds missing columns to existing SQLite database tables without data loss."""
    tables_columns = {
        "search_history": [
            ("search_purpose", "TEXT"),
            ("region", "TEXT"),
            ("city", "TEXT"),
            ("institution_id", "TEXT"),
            ("programme_id", "TEXT"),
            ("discovery_round", "INTEGER DEFAULT 1"),
        ],
        "regional_coverage": [
            ("coverage_level", "TEXT DEFAULT 'LOW'"),
            ("exhaustion_status", "TEXT DEFAULT 'NOT_TESTED'"),
            ("strategies_tested", "TEXT DEFAULT '[]'"),
        ],
        "universities": [
            ("institution_discovery_complete", "BOOLEAN DEFAULT 0"),
            ("official_inventory_confirmed", "BOOLEAN DEFAULT 0"),
        ],
        "research_runs": [
            ("distinct_frontiers", "INTEGER DEFAULT 0"),
            ("distinct_regions", "INTEGER DEFAULT 0"),
            ("distinct_cities", "INTEGER DEFAULT 0"),
            ("stop_reason", "TEXT"),
        ],
    }

    for table, columns in tables_columns.items():
        try:
            existing_cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for col_name, col_def in columns:
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def};")
            conn.commit()
        except sqlite3.Error as e:
            logger.debug(f"Migration note for table {table}: {e}")


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Connects to SQLite database, ensuring parent directory exists, foreign keys are enabled, and schema is migrated."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    migrate_database_schema(conn)
    return conn


def init_database(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initializes schema, migrates columns, and returns connection."""
    conn = get_connection(db_path)
    logger.info(f"Initialized and migrated SQLite research database at {db_path}")
    return conn
