from __future__ import annotations

import json
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from ..schemas import ProgrammeEvaluation, CheckStatus
from .research import official, scoped
from .state import transition


class OpportunityVector(BaseModel):
    academic_fit: int | None = Field(default=None,ge=0,le=3)
    degree_compatibility: int | None = Field(default=None,ge=0,le=3)
    prerequisite_match: int | None = Field(default=None,ge=0,le=3)
    language_compatibility: int | None = Field(default=None,ge=0,le=3)
    historical_opportunity: int | None = Field(default=None,ge=0,le=3)
    candidate_position: int | None = Field(default=None,ge=0,le=3)
    application_simplicity: int | None = Field(default=None,ge=0,le=3)
    evidence_confidence: int | None = Field(default=None,ge=0,le=3)
    stability: int | None = Field(default=None,ge=0,le=3)
    regional_preference: int | None = Field(default=None,ge=0,le=3)
    financial_practicality: int | None = Field(default=None,ge=0,le=3)
    region: str = ''
    family: str = ''
    hard_fail: bool = False
    credible: bool = False
    unknowns: list[str] = Field(default_factory=list)


DIMENSIONS = tuple(k for k in OpportunityVector.model_fields if k not in {'region','family','hard_fail','credible','unknowns'})


def dominates(a,b):
    # Missing evidence never wins over known evidence.
    comparable=[k for k in DIMENSIONS if getattr(b,k) is not None]
    return bool(comparable) and all(getattr(a,k) is not None and getattr(a,k)>=getattr(b,k) for k in comparable) and any(getattr(a,k)>getattr(b,k) for k in comparable)


def compare(challenger,pool,deep=False):
    if challenger.hard_fail: return 'NOT_IMPROVE_POOL',None,'Evidence-backed hard incompatibility'
    if deep and not challenger.credible: return 'INSUFFICIENT_EVIDENCE',None,'Critical evidence remains unresolved or stale'
    if not pool:
        if challenger.academic_fit is None and challenger.degree_compatibility is None:
            return 'INSUFFICIENT_EVIDENCE',None,'No evidence of academic or degree compatibility yet'
        return 'COMPLEMENT_EXISTING',None,'Build a credible working pool'
    for pid,old in pool:
        if dominates(challenger,old): return 'OUTPERFORM_EXISTING',pid,'No worse on known dimensions; improves at least one evidence-backed dimension'
    # Do not let a region label rescue a clearly dominated programme.
    if any(dominates(old,challenger) for _,old in pool):
        return 'NOT_IMPROVE_POOL',None,'Dominated on known opportunity dimensions'
    fills_dimension=any(getattr(challenger,k) is not None and all(getattr(v,k) is None or getattr(challenger,k)>getattr(v,k) for _,v in pool) for k in DIMENSIONS)
    diverse=bool(challenger.region and all(v.region!=challenger.region for _,v in pool)) or bool(challenger.family and all(v.family!=challenger.family for _,v in pool))
    if fills_dimension or diverse: return 'COMPLEMENT_EXISTING',None,'Adds an opportunity dimension or regional/programme diversity'
    return 'NOT_IMPROVE_POOL',None,'No demonstrated improvement or diversification benefit'


def vector(conn,e):
    p=e.programme;elig=e.eligibility
    row=conn.execute('SELECT region FROM universities WHERE institution_id=?',(p.institution_id,)).fetchone()
    claims={x.claim:x for x in p.official_sources if x.source_url and x.evidence_text and scoped(p,str(x.source_url),x.evidence_text)}
    v=OpportunityVector(region=row['region'] if row else '',family='software/systems' if any(w in (p.track or '').casefold() for w in ('logiciel','software','systems','systèmes')) else 'informatics',hard_fail=e.rejected or elig.hard_fail)
    if elig.degree_field==CheckStatus.PASS and 'accepted_degree_fields' in claims:
        v.degree_compatibility=3;v.academic_fit=2
    if p.transcript_match_info.status==CheckStatus.PASS and 'explicit_prerequisites' in claims:
        v.prerequisite_match=3 if p.transcript_match_info.coverage>=.8 else 2
        v.academic_fit=v.prerequisite_match
    taught = str(claims['teaching_language'].value).casefold() if 'teaching_language' in claims else ''
    if elig.language==CheckStatus.PASS and taught in ('english','anglais'):
        v.language_compatibility=3
    elif elig.language==CheckStatus.FAIL: v.language_compatibility=0
    if elig.application_route==CheckStatus.PASS and 'application_route' in claims:
        v.application_simplicity=1 if ('+' in str(claims['application_route'].value) or 'both' in str(claims['application_route'].value).casefold()) else 2
    if v.region and v.region not in ('Unknown Region','Île-de-France'): v.regional_preference=3
    if 'programme_active' in claims and claims['programme_active'].value is True: v.stability=3
    v.evidence_confidence=min(3,len(claims)//2) if claims else 0
    if v.academic_fit is not None and v.prerequisite_match is not None: v.candidate_position=min(v.academic_fit,v.prerequisite_match)
    # Only audited historical rows with provenance may influence pressure.
    stats=conn.execute("SELECT * FROM admission_statistics WHERE programme_id=? AND verification_status IN ('VERIFIED_CURRENT','VERIFIED_HISTORICAL') ORDER BY academic_year DESC",(p.programme_id,)).fetchall()
    for s in stats:
        if s['academic_year'] and s['applicants'] and s['capacity'] and s['source_url'] and official(p,s['source_url']):
            ratio=s['applicants']/s['capacity'];v.historical_opportunity=3 if ratio<3 else (2 if ratio<8 else 1);break
    for key in DIMENSIONS:
        if getattr(v,key) is None: v.unknowns.append(key)
    fresh=True
    for claim in claims.values():
        try: fresh &= (datetime.now(timezone.utc)-datetime.fromisoformat(claim.retrieved_at).replace(tzinfo=timezone.utc)).days<=90
        except (TypeError,ValueError): fresh=False
    v.credible=bool(not v.hard_fail and fresh and v.degree_compatibility is not None and v.prerequisite_match is not None and v.language_compatibility==3 and v.application_simplicity is not None and ('level' in claims or 'programme_structure' in claims) and p.programme_structure.m1_entry==CheckStatus.PASS and not p.scope_mismatch_flags)
    return v


def current_pool(conn):
    rows=conn.execute("SELECT programme_id,vector_json FROM programme_workflow WHERE pool_status='POOL_RETAINED' AND needs_refresh=0 AND superseded_by IS NULL").fetchall()
    return [(r['programme_id'],OpportunityVector.model_validate_json(r['vector_json'])) for r in rows if r['vector_json']]


def review_pool(conn,limit=15):
    metrics=dict(pool_additions=0,pool_replacements=0,pool_unchanged_candidates=0)
    rows=conn.execute("SELECT * FROM programme_workflow WHERE state IN ('CYCLE2_VERIFIED','CYCLE2_REVIEW_REQUIRED') AND pool_status='NOT_REVIEWED'").fetchall()
    for row in rows:
        pid=row['programme_id'];v=OpportunityVector.model_validate_json(row['vector_json']) if row['vector_json'] else OpportunityVector()
        decision,old,reason=compare(v,current_pool(conn),deep=True)
        if decision in ('OUTPERFORM_EXISTING','COMPLEMENT_EXISTING') and (old or len(current_pool(conn))<limit):
            if old:
                transition(conn,old,'POOL_DROPPED',reason)
                conn.execute("UPDATE programme_workflow SET pool_status='POOL_DROPPED',superseded_by=?,supersession_reason=? WHERE programme_id=?",(pid,reason,old))
                metrics['pool_replacements']+=1
            else: metrics['pool_additions']+=1
            transition(conn,pid,'POOL_RETAINED',decision+': '+reason)
            conn.execute("UPDATE programme_workflow SET pool_status='POOL_RETAINED' WHERE programme_id=?",(pid,))
        else:
            transition(conn,pid,'POOL_DROPPED',decision+': '+reason)
            conn.execute('UPDATE programme_workflow SET pool_status=? WHERE programme_id=?',(decision if decision not in ('OUTPERFORM_EXISTING','COMPLEMENT_EXISTING') else 'NOT_IMPROVE_POOL',pid))
            metrics['pool_unchanged_candidates']+=1
        conn.commit()
    return metrics
