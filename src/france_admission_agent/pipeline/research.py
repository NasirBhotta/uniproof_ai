from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote
import unicodedata

from ..graph import build_graph
from ..schemas import ProgrammeCandidate, EvidenceItem, SkepticReview, CheckStatus
from ..transcript_matcher import match_transcript_structured
from ..research.queries import build_targeted_field_query
from ..research.source_policy import domain_matches, hostname
from ..governor.efficiency_governor import EfficiencyGovernor
from .state import now

FIELDS = {
 'language': {'teaching_language','ielts_overall_min','ielts_speaking_min','english_cefr_required','french_level_required'},
 'degree': {'accepted_degree_fields'}, 'prerequisites': {'explicit_prerequisites'},
 'structure': {'level','programme_structure'}, 'route': {'application_route'},
 'calendar': {'deadline','deadline_cycle'}, 'historical': {'capacity','applicant_count','admitted_count'},
 'tuition': {'tuition'}, 'stability': {'programme_active'},
}


def official(p, url):
    domain = p.official_university_domain
    return bool(domain and domain_matches(hostname(url),domain))


def scoped(p, url, text):
    if not official(p,url):
        return False
    # University homepages cannot establish programme scope.
    parsed=urlparse(url)
    path=parsed.path.strip('/').casefold()
    specific_page=bool(re.search(r'(?:^|&)page_id=\d+(?:&|$)',parsed.query))
    if path in ('','en','fr','en/home','fr/accueil','index.html') and not specific_page:
        return False
    # Discovery previously invented these labels from broad search snippets.
    # A faculty catalogue or general language list is not evidence for them.
    invented = ('science des données et ia', 'tronc commun / parcours informatique générale',
                'systèmes distribués et réseaux')
    if (p.track or '').casefold() in invented:
        return False
    if 'masters-degrees-taught-in-english' in path:
        return False
    same_page = str(p.programme_url or '').rstrip('/') == url.rstrip('/')
    track = (p.track or '').casefold()
    slug = '-'.join(re.findall(r'[a-z0-9]+',unicodedata.normalize('NFKD',track).encode('ascii','ignore').decode().casefold()))
    path_slug=unquote(parsed.path).casefold()
    track_in_path=bool(slug and len(slug)>=3 and slug in path_slug)
    programme_query=bool(re.search(r'(?:^|&)(?:dipl|sem)=[^&]+',parsed.query))
    if same_page and (specific_page or track_in_path or programme_query):
        return True
    # A full catalogue may mention several tracks and languages. A claim from
    # it is usable only as a short, track-local excerpt, never as whole-page text.
    return bool(track and len(track)>4 and len(text)<=600 and track in text.casefold())


def parse_claims(field, text):
    """Conservative explicit phrases only; no equivalencies or inferred statistics."""
    result = {}; lower = text.casefold()
    if field == 'language':
        for label, phrase in [('English',r'(?:language of instruction\s*:?\s*english|(?:programme|program|master.{0,15})\s+is taught entirely in english)'),
                              ('French',r"(?:langue(?:\(s\))? d.enseignement\s*:?\s*fran[çc]ais|language of instruction\s*:?\s*french)")]:
            if re.search(phrase,lower): result['teaching_language'] = label
        m=re.search(r'ielts(?: academic)?(?: overall)?\s*(?:minimum|at least|:)?\s*([4-9](?:\.[05])?)',lower)
        if m: result['ielts_overall_min']=float(m[1])
        m=re.search(r'(?:speaking|oral)\s*(?:minimum|at least|:)?\s*([4-9](?:\.[05])?)',lower)
        if m: result['ielts_speaking_min']=float(m[1])
        m=re.search(r'(?:french|fran[çc]ais|delf|dalf)\s*(?:level|niveau)?\s*(?:required|requis)?\s*:?\s*(b2|c1|c2)',lower)
        if m: result['french_level_required']=m[1].upper()
        m=re.search(r'(?:english\s+level\s+(?:required\s*)?:?\s*|proficiency\s+in\s+english\s+at\s+(?:the\s+)?cefr\s+level\s*)(b2|c1|c2)',lower)
        if m: result['english_cefr_required']=m[1].upper()
    elif field == 'structure':
        if re.search(r'uniquement en m2|m2 only',lower): result['programme_structure']='M2_ONLY'
        elif re.search(r'(?:admission|entr[ée]e|entry|acc[èe]s).{0,35}\bm1\b|\bmaster 1\b',lower): result['level']='M1'
    elif field == 'degree':
        if re.search(r'(?:admission|admissible|pr[ée]requis|titulaire|bachelor|licence).{0,70}(?:computer science|informatique)',lower):
            result['accepted_degree_fields']=['Licence Informatique / Bachelor Computer Science']
        elif re.search(r'graduates of a three-year training\s*\(bac\+3\)\s*with computer science and management',lower):
            result['accepted_degree_fields']=['BAC+3 with computer science and management']
        elif re.search(r'admission en master 1\s*:\s*licence dans le m[êe]me domaine\s*\(180 cr[ée]dits\)',lower):
            result['accepted_degree_fields']=['Licence in the same field (180 ECTS)']
    elif field == 'prerequisites':
        m=re.search(r'(?:pr[ée]requis|prerequisites|required background)\s*[:\-]\s*([^.;]{10,300})',text,re.I)
        if m: result['explicit_prerequisites']=[m[1]]
    elif field == 'route':
        if re.search(r'pakistan|pays.{0,15}proc[ée]dure|eef countr|countries listed under.{0,40}campus france procedure',lower) and re.search(r'[ée]tudes en france',lower):
            dual=bool(re.search(r'(?:both|deux applications|two applications).{0,100}(?:fsa|[ée]tudes en france)',lower)
                      or re.search(r'[ée]tudes en france.{0,350}\bfsa\b',lower))
            result['application_route']='Études en France + FSA' if dual else 'Études en France'
    elif field == 'calendar':
        m=re.search(r'(?:deadline|date limite)\s*:?\s*(20\d\d-\d\d-\d\d)',lower)
        if m:
            result['deadline']=m[1];result['deadline_cycle']=m[1][:4]
    elif field == 'stability':
        if re.search(r'programme discontinued|formation ferm[ée]e d[ée]finitivement',lower): result['programme_active']=False
    elif field == 'historical':
        years=set(re.findall(r'20\d\d[-/]20\d\d',text))
        # Require an explicit cohort, unique year and metric labels. Ambiguous
        # offers/admitted/enrolled counts are deliberately left unresolved.
        if len(years)==1 and re.search(r'\bM1\b',text):
            for key,pattern in [('capacity',r'capacit[ée] d.accueil\s*:\s*(\d+)'),
                                ('applicant_count',r'(?:candidatures re[çc]ues|total applications)\s*:\s*(\d+)'),
                                ('admitted_count',r'(?:candidats admis|admitted applicants)\s*:\s*(\d+)')]:
                m=re.search(pattern,lower)
                if m: result[key]=int(m[1])
    return result


class TargetedResearch:
    """Provider-neutral, bounded resolver; persists compact evidence and failures."""
    def __init__(self, conn, search=None, budget=6):
        self.conn=conn;self.search=search;self.budget=budget
        self.metrics=dict(external_searches=0,cache_hits=0,searches_saved_by_memory=0,
                          llm_calls=0,input_tokens=0,output_tokens=0,provider_failures=0,page_fetches=0)
        self.governor=EfficiencyGovernor(conn)
        self.deferred_fields={}
        self.attempted_pages=set()
        self.page_diagnostics=[]

    def resolve(self, candidate, p, fields, force=False):
        # A known official programme page must not depend on being rediscovered
        # in a search snippet. Read it once and reuse its full text across fields.
        primary=str(p.programme_url or '')
        if fields and self.search is not None and self.budget>0 and scoped(p,primary,''):
            content=self.fetch_compact(p,primary,fields[0],force=force)
            if content:
                for field in fields:
                    self.consume(p,field,primary,content,candidate.target.intake)
        for field in fields:
            keys=FIELDS[field]
            rows=self.conn.execute('''SELECT * FROM evidence WHERE programme_id=?
                AND verification_status='VERIFIED_CURRENT' ORDER BY retrieved_at DESC''',(p.programme_id,)).fetchall()
            applied=False
            for row in rows:
                if row['claim_type'] not in keys or not scoped(p,row['source_url'] or '',row['source_title'] or ''): continue
                if row['track_id'] and row['track_id'] != p.track_id: continue
                if row['target_cycle'] and row['target_cycle'] != candidate.target.intake: continue
                try:
                    age=(datetime.now(timezone.utc)-datetime.fromisoformat(row['retrieved_at']).replace(tzinfo=timezone.utc)).days
                except (TypeError,ValueError): continue
                if age>30 or force: continue
                try: value=json.loads(row['claim_value'])
                except (ValueError,TypeError): value=row['claim_value']
                self.apply(p,row['claim_type'],value,row['source_url'],row['source_title'] or row['claim_value'],row['retrieved_at'])
                applied=True
            if applied:
                self.metrics['searches_saved_by_memory']+=1
                continue
            # Parse an existing page only if its retrieval timestamp is fresh.
            page=self.conn.execute("SELECT extracted_text FROM source_documents WHERE url=? AND content_hash IS NOT NULL AND julianday('now')-julianday(retrieved_at)<=30",(str(p.programme_url or ''),)).fetchone()
            if page and not force and self.consume(p,field,str(p.programme_url),page['extracted_text'],candidate.target.intake):
                self.metrics['searches_saved_by_memory']+=1
                continue
            if self.search is None or self.metrics['external_searches']>=self.budget:
                if force:
                    raise RuntimeError('Field refresh deferred: provider unavailable or budget exhausted')
                self.deferred_fields.setdefault(p.programme_id,set()).add(field)
                continue
            lookup={'language':'teaching_language','historical':'selectivity','route':'application_route'}.get(field,field)
            query=build_targeted_field_query(p.university,f'{p.programme} {p.track or ""}',lookup,p.official_university_domain).query
            if field=='calendar': query+=f' {candidate.target.intake} calendrier candidature deadline'
            if field=='tuition': query+=' frais inscription tuition non EU'
            if field=='stability': query+=' formation ouverte fermeture'
            if self.governor.is_exact_duplicate(query,target_institution=p.institution_id or '',search_purpose=f'incremental_{field}')[0] and not force:
                self.metrics['searches_saved_by_memory']+=1;continue
            # Explicit/stale-field refresh may bypass only this wrapper's cached
            # response; other fields retain normal cache and memory reuse.
            client = getattr(self.search, 'inner', self.search) if force else self.search
            batch=client.search(query,max_results=3,search_depth='basic',include_raw_content=False)
            if batch.cache_hit: self.metrics['cache_hits']+=1
            else: self.metrics['external_searches']+=1
            if batch.error:
                self.metrics['provider_failures']+=1
                raise RuntimeError(f'Targeted provider failure: {batch.error}')
            if not batch.cache_hit:
                self.governor.record_search_result(query,p.institution_id or '',p.programme_id,field,len(batch.results),
                    provider=type(getattr(self.search,'inner',self.search)).__name__,search_purpose=f'incremental_{field}',
                    institution_id=p.institution_id or '',programme_id=p.programme_id)
            for result in batch.results:
                text=(result.title+' '+result.snippet)[:2000];url=str(result.url)
                if not official(p,url): continue
                # Fetch before testing full programme scope: snippets can omit
                # the track name. Never promote a search snippet into evidence.
                content=self.fetch_compact(p,url,field,force=force)
                if content:
                    if not scoped(p,url,content):
                        self.page_diagnostics.append(dict(url=url,status='SCOPE_MISMATCH'))
                        continue
                    self.consume(p,field,url,content,candidate.target.intake)
            self.conn.commit()
        return p

    def fetch_compact(self,p,url,field,force=False):
        """Fetch promising official URLs only; cache locally, never send raw HTML to a model."""
        if not official(p,url): return ''
        row=self.conn.execute("SELECT extracted_text FROM source_documents WHERE url=? AND content_hash IS NOT NULL AND julianday('now')-julianday(retrieved_at)<=30",(url,)).fetchone()
        if row and not force:
            self.metrics['cache_hits']+=1
            return row['extracted_text']
        if url in self.attempted_pages or self.metrics['page_fetches']>=self.budget: return ''
        self.attempted_pages.add(url)
        import httpx
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        self.metrics['page_fetches']+=1
        try:
            # Follow at most two redirects, checking each destination against
            # the institution domain before sending another request.
            with httpx.Client(timeout=10,follow_redirects=False) as client:
                current=url
                for hop in range(3):
                    with client.stream('GET',current) as response:
                        if response.status_code in (301,302,303,307,308):
                            destination=urljoin(current,response.headers.get('location',''))
                            if hop==2 or not official(p,destination):
                                self.page_diagnostics.append(dict(url=current,status='UNSAFE_OR_EXCESS_REDIRECT'))
                                return ''
                            self.page_diagnostics.append(dict(url=current,status='OFFICIAL_REDIRECT',destination=destination))
                            current=destination
                            continue
                        if response.status_code!=200:
                            self.page_diagnostics.append(dict(url=current,status='HTTP_'+str(response.status_code)))
                            return ''
                        content_type=response.headers.get('content-type','').casefold()
                        document_encoding=response.encoding or 'utf-8'
                        is_pdf='application/pdf' in content_type or urlparse(current).path.casefold().endswith('.pdf')
                        if 'text/html' not in content_type and not is_pdf:
                            self.page_diagnostics.append(dict(url=current,status='UNSUPPORTED_CONTENT_TYPE'))
                            return ''
                        raw=b''
                        for chunk in response.iter_bytes():
                            raw+=chunk
                            if len(raw)>5000000:
                                self.page_diagnostics.append(dict(url=current,status='DOCUMENT_TOO_LARGE'))
                                return ''
                        break
            if is_pdf:
                from io import BytesIO
                import logging
                from pypdf import PdfReader
                try:
                    # Some official PDFs contain thousands of duplicate image-key
                    # warnings. Keep parser errors visible without flooding the loop.
                    logging.getLogger('pypdf').setLevel(logging.ERROR)
                    reader=PdfReader(BytesIO(raw))
                    text=' '.join((page.extract_text() or '') for page in reader.pages[:25])[:30000]
                except Exception:
                    self.page_diagnostics.append(dict(url=current,status='PDF_PARSE_ERROR'))
                    return ''
            else:
                soup=BeautifulSoup(raw.decode(document_encoding,errors='replace'),'html.parser')
                for element in soup(['script','style','nav','footer','header','form']): element.decompose()
                body=soup.select_one('main') or soup.select_one('#content-wrap') or soup
                text=' '.join(body.stripped_strings)[:30000]
            self.conn.execute('INSERT OR REPLACE INTO source_documents(url,institution_id,extracted_text,retrieved_at,content_hash) VALUES (?,?,?,?,?)',
                              (url,p.institution_id,text,now(),hashlib.sha256(text.encode()).hexdigest()));self.conn.commit()
            self.page_diagnostics.append(dict(url=url,status='FETCHED',characters=len(text)))
            return text
        except httpx.HTTPError as exc:
            self.page_diagnostics.append(dict(url=url,status=type(exc).__name__))
            return ''

    def consume(self,p,field,url,text,intake):
        if not scoped(p,url,text): return False
        claims=parse_claims(field,text)
        for key,value in claims.items():
            self.apply(p,key,value,url,text,now())
            eid=hashlib.sha256(f'{p.programme_id}|{key}|{url}|{value}'.encode()).hexdigest()
            self.conn.execute('''INSERT OR REPLACE INTO evidence(evidence_id,institution_id,programme_id,track_id,
                claim_type,claim_value,source_url,source_title,source_type,target_cycle,retrieved_at,verification_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,'VERIFIED_CURRENT')''',
                (eid,p.institution_id,p.programme_id,p.track_id,key,json.dumps(value),url,text[:30000],'official_university',intake,now()))
        if field=='historical' and claims:
            year=next(iter(set(re.findall(r'20\d\d[-/]20\d\d',text))))
            exists=self.conn.execute('SELECT id FROM admission_statistics WHERE programme_id=? AND academic_year=? AND source_url=?',
                                     (p.programme_id,year,url)).fetchone()
            if not exists:
                self.conn.execute('''INSERT INTO admission_statistics(programme_id,academic_year,applicants,admitted,capacity,
                    ratio_definition,population,source_url,source_name,verification_status,last_verified)
                    VALUES (?,?,?,?,?,'Applicants / published capacity','M1 cohort',?,'Explicit official cohort labels','VERIFIED_HISTORICAL',?)''',
                    (p.programme_id,year,claims.get('applicant_count'),claims.get('admitted_count'),claims.get('capacity'),url,now()))
        self.conn.commit()
        return bool(claims)

    @staticmethod
    def apply(p,key,value,url,text,retrieved_at):
        ev=EvidenceItem(claim=key,claim_type=key,value=value if not isinstance(value,list) else json.dumps(value),
            source_url=url,evidence_text=text[:30000],institution_id=p.institution_id,programme_id=p.programme_id,
            track_id=p.track_id,retrieved_at=retrieved_at)
        p.official_sources=[e for e in p.official_sources if e.claim!=key]+[ev]
        if key=='teaching_language': p.language.teaching_language=value if isinstance(value,list) else [value]
        elif key in ('ielts_overall_min','ielts_speaking_min','french_level_required','english_cefr_required'):
            setattr(p.language,key,value)
        elif key in ('accepted_degree_fields','explicit_prerequisites'):
            setattr(p,key,value if isinstance(value,list) else [str(value)])
        elif key in ('application_route','deadline','deadline_cycle','level'): setattr(p,key,value)


def evaluate(candidate,p,resolver=None,fields=()):
    """Feed exactly one explicit programme to the existing LangGraph evaluator."""
    class DeltaBackend:
        def discover_programmes(self,c,limit,seen): return [p] if p.programme_id not in seen else []
        def enrich_and_verify(self,c,programme):
            return resolver.resolve(c,programme,fields) if resolver else programme
        def transcript_coverage(self,c,programme): return match_transcript_structured(c,programme).coverage
        def skeptic_review(self,c,e): return SkepticReview(unresolved_questions=e.programme.unresolved_questions)
    result=build_graph(DeltaBackend()).invoke(dict(candidate=candidate,target_count=1,discovery_batch_size=1,
        max_discovery_rounds=1,discovery_round=0,programmes=[],evaluations=[],rejected=[]))
    e=(result['evaluations']+result['rejected'])[0]
    # Existing validators accept some identity defaults as evidence. The pipeline
    # requires explicit scoped claims for M1 and all hard failures.
    claims={ev.claim for ev in p.official_sources if ev.source_url and ev.evidence_text and scoped(p,str(ev.source_url),ev.evidence_text)}
    if 'accepted_degree_fields' not in claims:
        e.eligibility.degree_field=CheckStatus.UNVERIFIED
    if not claims.intersection(FIELDS['language']):
        e.eligibility.language=CheckStatus.UNVERIFIED
    if 'level' not in claims and 'programme_structure' not in claims:
        e.eligibility.level=CheckStatus.UNVERIFIED
        e.programme.programme_structure.m1_entry=CheckStatus.UNVERIFIED
    gates={'degree_field':{'accepted_degree_fields'},'language':FIELDS['language'],
           'french':{'french_level_required','french_cefr_required'},'level':FIELDS['structure']}
    for attr,keys in gates.items():
        if getattr(e.eligibility,attr)==CheckStatus.FAIL and not claims.intersection(keys):
            setattr(e.eligibility,attr,CheckStatus.UNVERIFIED)
    discontinued=any(ev.claim=='programme_active' and ev.value is False for ev in p.official_sources)
    e.eligibility.hard_fail=discontinued or any(getattr(e.eligibility,k)==CheckStatus.FAIL for k in gates)
    e.rejected=e.eligibility.hard_fail
    if not e.rejected:
        e.rejection_reasons=[]
        from ..scoring import calculate_score, assign_evaluation_group
        from ..validators import is_final_ready
        e.final_ready=is_final_ready(e.eligibility,e.skeptic.unresolved_questions) and e.validation_status==CheckStatus.PASS
        e.score=calculate_score(e);e.group=assign_evaluation_group(e)
    return e
