# France Master's Safe-Fit Research Agent
## Model-Agnostic Architecture & Candidate Specification

**Purpose:** Build an evidence-first research agent that finds **7 French Master's programmes** for the candidate where the profile is a strong academic and procedural fit, with an explicit preference for **public universities, locations outside Paris/Île-de-France, smaller or less internationally visible cities/campuses, and lower-competition programmes**.

> The agent must **not** claim a "90% admission probability" unless an official source publishes enough applicant/admission data to justify it.  
> Instead it produces a **Safe-Fit Confidence Score (0–100)** that measures evidence-backed fit, not statistical admission probability.

---

# 1. Candidate Profile — Canonical Research Input

## 1.1 Identity / application context
- Nationality: Pakistani
- Target country: France
- Target level: Master's / M1
- Primary field: Computer Science / Informatique
- Preferred application route: Campus France / Études en France where applicable
- Location preference:
  - Prefer outside Paris and Île-de-France
  - Prefer regional public universities
  - Prefer small or medium-sized cities / town campuses
  - Prefer programmes with lower international visibility
- Admission strategy:
  - Avoid prestige-first selection
  - Prioritize eligibility, transcript fit, realistic selectivity and evidence
  - Final output: 7 primary programmes
  - Maintain a separate research reserve list of 3–5 alternatives

## 1.2 Bachelor's degree
- Degree: Bachelor of Science in Computer Science
- Institution: COMSATS University Islamabad, Islamabad Campus
- Duration: 4 years / 8 semesters
- Completion: January 2026
- Total credits: 133
- CGPA: **3.23 / 4.00**
- Medium of instruction: English

### Important GPA rule
Never mechanically convert `3.23 / 4.00` into:
- a French `/20` mark,
- a percentage,
- ECTS grades,
- or an admission percentile.

Use the official transcript and university-specific evaluation rules. If the target university does not publish a conversion rule, describe the CGPA exactly as `3.23/4.00`.

## 1.3 English
Current documented profile information:
- IELTS Academic overall: **6.5**
- Listening: **7.5**
- Reading: **6.0**
- Writing: **6.5**
- Speaking: **5.5**
- CEFR representation in CV: B2
- Bachelor's medium of instruction: English

### English-rule constraint
For every programme, verify:
1. overall IELTS minimum;
2. minimum per component, if any;
3. whether IELTS is mandatory;
4. whether a university-issued English-medium certificate is accepted;
5. whether a separate interview/test is required.

Never assume that English-medium prior education automatically waives IELTS.

## 1.4 French
Transcript includes a university course in **French** with a strong grade.

This is a useful supporting signal, but it is **not equivalent to DELF/TCF/TEF certification** and must never be treated as proof of B1/B2/C1 unless an official university rule explicitly accepts the transcript/course as evidence.

---

# 2. Transcript-Based Academic Profile

The agent must assess programmes against actual coursework rather than only the degree title.

## 2.1 Core CS foundation
The transcript contains coursework in:
- Programming Fundamentals
- Object-Oriented Programming
- Data Structures and Algorithms
- Design and Analysis of Algorithms
- Discrete Structures
- Database Systems
- Operating Systems
- Computer Networks
- Computer Organization and Assembly Language
- Theory of Automata
- Graph Theory
- Software Engineering
- Web Technologies
- Advanced Web Technologies
- Mobile Application Development
- Parallel and Distributed Computing
- Compiler Construction
- Information Security
- Artificial Intelligence
- Machine Learning
- Topics in Computer Science
- Senior Design Project I & II

## 2.2 Mathematics / quantitative foundation
Relevant coursework includes:
- Calculus and Analytical Geometry
- Linear Algebra
- Differential Equations
- Statistics and Probability Theory
- Numerical Computations
- Discrete Structures
- Graph Theory

## 2.3 Applied AI / software evidence
Final Year Project:
- AI-powered learning platform
- Flutter-based application
- RAG / retrieval-augmented chatbot
- AI-generated summaries, quizzes and flashcards
- Personalized/adaptive learning features

Professional/project profile also includes:
- Flutter/Dart
- Firebase
- Supabase/PostgreSQL
- Node.js / Express.js
- MongoDB / MySQL
- Python
- REST APIs
- Offline-first architecture
- Maps/navigation
- Agentic AI / RAG prototypes

## 2.4 Academic-fit interpretation

### Stronger target families
Prioritize discovery in:
- Master Informatique
- Computer Science
- Software Engineering / Génie Logiciel
- Distributed Systems
- Information Systems
- Web / Software / Application Engineering
- Applied Computer Science
- General Computer Science tracks with later specialization
- Selected applied AI programmes where prerequisites are satisfied

### Moderate target families
Evaluate carefully:
- Artificial Intelligence
- Applied Machine Learning
- Data-oriented Computer Science
- Cybersecurity

These can be viable, but the agent must verify mathematical prerequisites, cohort selectivity, and whether the programme expects stronger specialized undergraduate depth.

### Higher-risk target families
Penalize unless evidence is unusually favorable:
- Pure Data Science / Statistics-heavy programmes
- Highly mathematical Machine Learning
- Theoretical Computer Science
- Elite research-intensive AI tracks
- Programmes explicitly demanding an "excellent academic record"
- Programmes with very small cohorts and strong international competition

The practical AI portfolio is a positive factor, but it must **not override weak or missing academic prerequisites**.

---

# 3. Supporting Application Evidence

## 3.1 Professional experience
The strongest current CV version presents:
- 1+ year professional Flutter/full-stack experience
- Part-time Full-Stack Flutter Developer experience
- Earlier Flutter internship
- Multiple production-style projects
- Independent multi-tenant MobileShop SaaS / ERP-POS product
- Backend, database, cloud, RLS and offline-sync experience
- AI/RAG/agentic projects

Use professional work as:
- motivation evidence,
- specialization evidence,
- project-fit evidence,
- SOP evidence.

Do **not** use professional work as a substitute for mandatory academic prerequisites.

## 3.2 Recommendation letters
Available academic recommendations support:
- analytical/problem-solving ability;
- Design and Analysis of Algorithms background;
- Advanced Web Technologies background;
- motivation and discipline;
- ability to apply technical concepts.

For programme-specific SOP/recommendation mapping:
- Algorithms/theory-oriented programme → emphasize the algorithms recommender.
- Web/software/application programme → emphasize the Advanced Web Technologies recommender.

## 3.3 Secondary education
- HSSC / Pre-Engineering: 1071 / 1100, Grade A+
- SSC / Science: 1012 / 1100, Grade A+

These are positive historical academic signals but should receive **low weight** in Master's admission matching compared with the Bachelor's transcript.

---

# 4. Document Consistency Rules

The uploaded documents include multiple CV versions. Dates and wording are not perfectly identical across all versions.

The research agent must use this evidence priority:

1. Official degree/transcript
2. Official university certificate
3. Official IELTS certificate, when supplied
4. Employer-issued certificates
5. Latest approved CV
6. Older CV versions
7. Self-description

### Canonical rule
When two CVs conflict, do not silently choose one. Mark:

`DOCUMENT_CONSISTENCY_REVIEW_REQUIRED`

before generating application documents.

The university-search stage may still proceed if the inconsistency does not affect academic eligibility.

### Privacy rule
Do not copy national ID numbers, passport numbers, home addresses or other unnecessary identifiers into:
- model prompts,
- logs,
- search queries,
- web searches,
- final university comparisons.

Nationality and country of residence may be used only where application-route eligibility requires them.

---

# 5. Agent Architecture

```text
┌───────────────────────────────┐
│ A. DOCUMENT INGESTION         │
│ transcript / degree / CV      │
│ IELTS / certificates / LORs   │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ B. PROFILE NORMALIZER         │
│ canonical academic JSON       │
│ prerequisites + languages     │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ C. PROGRAM DISCOVERY          │
│ official French sources       │
│ broad candidate pool          │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ D. HARD ELIGIBILITY GATE      │
│ reject definite mismatches    │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ E. TRANSCRIPT MATCHER         │
│ course-by-course mapping      │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ F. COMPETITION / LOCATION     │
│ selectivity proxies           │
│ regional visibility signals  │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ G. SKEPTIC / REJECTION PASS   │
│ actively search for reasons   │
│ candidate may be rejected     │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ H. EVIDENCE VALIDATOR         │
│ official source cross-check   │
│ latest intake / deadline      │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ I. SAFE-FIT RANKER            │
│ evidence-backed score         │
└───────────────┬───────────────┘
                ↓
┌───────────────────────────────┐
│ J. FINAL 7 + RESERVE LIST     │
│ application-ready report      │
└───────────────────────────────┘
```

---

# 6. Module A — Document Ingestion

Input types:
- transcript;
- degree;
- medium-of-instruction / bonafide certificate;
- IELTS;
- CV;
- experience certificate;
- recommendation letters;
- passport nationality page only when application-route checking requires it.

Extract into structured fields and attach provenance:

```json
{
  "field": "cgpa",
  "value": "3.23/4.00",
  "source": "Transcript",
  "source_type": "official_academic",
  "confidence": "verified"
}
```

Never let a CV override an official transcript.

---

# 7. Module B — Canonical Profile Object

Recommended schema:

```yaml
candidate:
  degree:
    title: "Bachelor of Science in Computer Science"
    institution: "COMSATS University Islamabad"
    duration_years: 4
    credits: 133
    cgpa: 3.23
    scale: 4.00
    completion: "2026-01"
    medium: "English"

  languages:
    english:
      ielts:
        overall: 6.5
        listening: 7.5
        reading: 6.0
        writing: 6.5
        speaking: 5.5
        status: "CV-supported; official TRF should be verified"
    french:
      university_course: true
      certification: null

  academic_domains:
    programming: strong
    algorithms_data_structures: strong
    software_engineering: good
    databases: good
    operating_systems_networks: good
    web_application_development: strong
    ai_ml: relevant
    mathematics: adequate_to_good
    information_security: relevant
    distributed_systems: relevant

  experience:
    software_development: true
    full_stack: true
    ai_projects: true
    production_projects: true

  preferences:
    public_university: preferred
    outside_paris: strongly_preferred
    smaller_city: preferred
    lower_visibility: preferred
    english_taught: strongly_preferred
    target_level: "M1"
```

---

# 8. Module C — Programme Discovery

The agent must search **programmes, not university names**.

Correct research object:

```text
University
→ Faculty / School
→ Master's degree
→ Track / parcours
→ M1 or M2
→ Campus
→ Teaching language
→ Application route
```

A university cannot be labelled "safe" as a whole.

## Discovery query families

Search in both English and French:

```text
site:<official-domain> Master Informatique M1 admission international
site:<official-domain> Master informatique candidature M1
site:<official-domain> Master informatique étudiants internationaux
site:<official-domain> Master génie logiciel M1
site:<official-domain> Master systèmes distribués M1
site:<official-domain> Master intelligence artificielle M1
site:<official-domain> Master informatique enseigné en anglais
```

Also discover through official French catalogues/platforms, then return to the university's own page for verification.

## Geographic strategy
Strongly prefer:
- regional public universities;
- non-Paris campuses;
- smaller/medium cities;
- programmes marketed primarily in French;
- general CS programmes with appropriate specialization pathways.

Do not assume:
`small city = easy admission`.

A small programme may have few seats and high selectivity.

---

# 9. Official Source Hierarchy

Use evidence in this order:

1. Official university programme page
2. Official university admissions page
3. Official programme regulations / PDF
4. Campus France / Études en France official source
5. French government / official national Master's catalogue
6. Official faculty/school page

Supplementary only:
- Mastersportal
- Study portals
- ranking sites
- Reddit/forums
- blogs
- consultants
- scholarship aggregators

### Hard rule
`NO OFFICIAL SOURCE → NO FINAL SHORTLIST`

Third-party sources may generate leads but cannot establish final eligibility.

---

# 10. Module D — Hard Eligibility Gate

Each programme receives PASS / FAIL / UNCERTAIN for:

```yaml
hard_checks:
  degree_field_accepted:
  bachelor_duration_accepted:
  M1_entry_possible:
  required_credits_met:
  mandatory_course_prerequisites_met:
  english_overall_met:
  english_subscores_met:
  french_requirement_met:
  nationality_route_valid:
  international_applicants_allowed:
  application_route_verified:
  intake_verified:
  deadline_verified:
```

## Automatic reject examples
Reject if an official source shows:
- mandatory French B2/C1 and no acceptable proof;
- IELTS component minimum higher than candidate score;
- M2-only entry when candidate is applying to M1;
- degree prerequisite clearly incompatible;
- mandatory advanced math/statistics credits not present;
- application closed for the target intake;
- programme not available to the candidate through any valid route;
- programme taught primarily in French with required proof candidate does not hold.

## Uncertainty rule
If a requirement is unclear:
- mark `UNCERTAIN`;
- search another official source;
- if unresolved, do **not** classify as safe.

---

# 11. Module E — Transcript Matcher

For each programme, create a prerequisite-to-transcript matrix:

| Programme prerequisite | Candidate evidence | Match |
|---|---|---|
| Programming | Programming Fundamentals, OOP | Strong |
| Algorithms | DSA, Design & Analysis of Algorithms | Strong |
| Databases | Database Systems | Strong |
| OS | Operating Systems | Strong |
| Networks | Computer Networks | Strong |
| Mathematics | Calculus, Linear Algebra, Probability/Statistics, Numerical Computing | Moderate–Strong |
| AI | Artificial Intelligence | Relevant |
| ML | Machine Learning | Relevant |
| Distributed systems | Parallel & Distributed Computing | Relevant |

Calculate:

`Curriculum Coverage = matched_required_topics / total_explicit_required_topics`

This is a **matching metric**, not admission probability.

### Suggested thresholds
- `>= 85%`: strong curricular fit
- `75–84%`: acceptable but inspect gaps
- `< 75%`: risky unless missing items are clearly optional

For highly specialized programmes, matching must include **depth**, not only course-name overlap.

---

# 12. Module F — Competition and Visibility Analyzer

The agent should seek official selectivity evidence where available.

Possible signals:
- published capacity / number of seats;
- published applicant numbers;
- published historical admission/access data;
- explicit "highly selective" wording;
- special entrance examination;
- interview requirement;
- honours/excellence requirements;
- programme international visibility;
- university/campus geographic popularity;
- English-only international marketing;
- unusually small cohort.

### Important
Absence of selectivity data is **not evidence of low selectivity**.

## Location / visibility preference score
Use only as a secondary factor:

```text
Paris / Île-de-France                     strong penalty
major internationally popular city       moderate penalty
regional medium city                      small positive
small city / regional campus              positive
low international marketing visibility   positive
```

Do not equate city population with admission probability.

---

# 13. Module G — Skeptic / Rejection Reviewer

Every programme surviving the first pass is sent to a second reviewer with the opposite objective:

> Try to prove that this programme should NOT be classified as a safe fit for this candidate.

Check specifically:
- hidden French requirement;
- IELTS subscore problem;
- mathematical prerequisite gap;
- grade/excellence wording;
- very small capacity;
- M1/M2 confusion;
- international applicant restrictions;
- wrong application platform;
- outdated intake information;
- different requirements for Études en France countries;
- programme-language ambiguity;
- prerequisite credits/ECTS;
- selective interview/exam;
- professional-experience requirement;
- inconsistent programme pages.

Output:

```yaml
skeptic_review:
  fatal_issue: false
  serious_risks: []
  unresolved_questions: []
  downgrade_recommended: false
```

Any fatal issue removes the programme.

---

# 14. Module H — Evidence Validator

Before final ranking, every surviving programme must have:

```yaml
evidence_bundle:
  programme_page:
  admissions_page:
  language_requirement_source:
  application_route_source:
  deadline_source:
  curriculum_source:
  latest_update_date:
```

Minimum final-shortlist requirement:
- official programme evidence;
- official admissions/application evidence;
- current or target-intake deadline evidence;
- language evidence;
- curriculum/prerequisite evidence.

If evidence is stale or target-year information is not yet published, label:

`TARGET_YEAR_PENDING — verified using latest available official cycle`

Never present an older deadline as the new intake deadline.

---

# 15. Safe-Fit Scoring Model

This score represents **quality of fit + quality of evidence**, not acceptance probability.

| Component | Weight |
|---|---:|
| Hard eligibility | 25 |
| Transcript/curriculum match | 20 |
| Academic competitiveness | 15 |
| Language compatibility | 10 |
| Selectivity evidence | 10 |
| Regional / lower-visibility fit | 8 |
| Application-route simplicity | 5 |
| SOP/project alignment | 4 |
| Evidence freshness/completeness | 3 |
| **Total** | **100** |

## Classification
- **90–100:** Exceptional evidence-backed safe fit
- **85–89:** Strong safe fit
- **78–84:** Good target
- **70–77:** Moderate / needs caution
- **<70:** Do not use as a "safe" choice

### Critical override
A programme with a hard requirement failure cannot be rescued by a high weighted score.

---

# 16. Academic Competitiveness Logic

Because universities rarely publish a direct GPA threshold comparable to a Pakistani 4.0 scale, estimate competitiveness from evidence rather than fake conversion.

Consider:
- candidate CGPA 3.23/4.00;
- grades in directly relevant prerequisite subjects;
- breadth of CS foundation;
- final-year project;
- recommendation alignment;
- professional relevance;
- explicit programme wording such as "excellent academic record";
- published cohort/selectivity data where available.

### Grade-sensitive rule
For specialized programmes, inspect **relevant subject grades**, not only overall CGPA.

For example:
- AI/ML programme → AI, ML, linear algebra, statistics/probability, algorithms;
- Software programme → software engineering, OOP, databases, web, distributed systems;
- Systems programme → OS, networks, distributed computing, computer organization;
- Security programme → information security, networks, systems, programming.

---

# 17. Search Strategy: Falsify Before Recommending

For each candidate programme:

## Pass 1 — Find reasons it fits
- appropriate degree;
- programme field;
- language;
- M1 entry;
- curriculum overlap;
- valid route;
- favorable location.

## Pass 2 — Find reasons it may fail
Search official sources for:
- `admission requirements`
- `prérequis`
- `niveau de français`
- `niveau d'anglais`
- `capacité`
- `sélection`
- `candidature`
- `étudiants internationaux`
- `Études en France`
- `M1`
- `calendrier`
- `pièces justificatives`

## Pass 3 — Cross-check
Final shortlist only after the negative-search pass.

---

# 18. Application-Route Resolver

Do **not** assume all French Master's programmes use the same platform.

For each programme determine the candidate-specific route from current official sources, e.g.:
- Études en France / Campus France;
- national Master's platform where applicable;
- eCandidat;
- direct university portal;
- another official route.

Store:

```yaml
application_route:
  platform:
  candidate_country_rule:
  university_instruction:
  opening_date:
  deadline:
  source:
  verified_for_target_cycle: true/false
```

If Campus France and university instructions conflict, flag the programme for manual review rather than guessing.

---

# 19. Final 7 Selection Logic

The final seven should not simply be the seven highest raw scores.

Use portfolio construction:

- 4–5 genuinely strong safe-fit programmes
- 2–3 additional strong targets with slightly different specialization/geography
- avoid seven programmes with the same hidden risk
- avoid clustering all seven in one highly competitive subject such as AI
- prefer programme diversity while staying inside candidate's real academic background

The reserve research list can contain 3–5 additional programmes, but keep it separate from the final seven choices.

---

# 20. Required Final Report Format

```markdown
# France Master's Shortlist — Candidate Report
Research date:
Target intake:

## Candidate snapshot
- BSCS, COMSATS University Islamabad
- CGPA: 3.23/4.00
- 133 credits
- IELTS Academic: 6.5
- Major strengths:
- Main constraints:

## 1. [University]
**Programme:**  
**Track / Parcours:**  
**Degree level:** M1  
**Campus:**  
**City:**  
**Public/private:**  
**Teaching language:**  
**Application route:**  
**Application opening:**  
**Deadline:**  

### Official requirements
...

### Transcript match
...

### Language check
...

### Why it fits
...

### Why it might still fail
...

### Competition / selectivity evidence
...

### Location / visibility
...

### Safe-Fit Confidence
**XX/100 — Strong Safe Fit / Good Target / Moderate**

> This is a fit-confidence score, not an admission probability.

### Evidence
1. Official programme page
2. Official admissions page
3. Official application/deadline page
4. Official curriculum/prerequisite source

---

[Repeat for all 7]

# Comparison Table
| # | University | Programme | City | Language | Route | Curriculum Fit | Main Risk | Safe-Fit |
|---|---|---|---|---|---|---|---|---|

# Reserve Research List
...

# Rejected Programmes
List promising programmes rejected during research and the exact reason:
- language failure
- prerequisite gap
- excessive selectivity
- wrong level
- route incompatibility
- deadline
- insufficient official evidence
```

---

# 21. Agent System Prompt

Use the following as the core model instruction.

```text
You are an evidence-first French Master's admissions research agent.

Your job is to identify seven French Master's programmes that are unusually strong
fits for the supplied candidate profile. The candidate prefers public universities,
locations outside Paris/Île-de-France, smaller or less internationally visible cities,
and programmes where the academic profile is realistically competitive.

Your objective is NOT prestige maximization. Your objective is to reduce avoidable
admission risk while maintaining academic relevance.

Candidate:
- Pakistani applicant
- BS Computer Science, COMSATS University Islamabad
- 4-year degree, 133 credits
- CGPA 3.23/4.00
- IELTS Academic 6.5 overall:
  L 7.5, R 6.0, W 6.5, S 5.5
- strong broad CS foundation
- relevant AI/ML, software, algorithms, systems, database, web and math coursework
- final-year AI/RAG project
- 1+ year software-development experience
- English-medium Bachelor's degree
- university French course exists, but no DELF/TCF/TEF should be assumed

NON-NEGOTIABLE RULES

1. Research PROGRAMMES, not universities in the abstract.
2. Prefer M1 unless explicitly instructed otherwise.
3. Use official sources for every final eligibility claim.
4. Third-party sites may generate leads only.
5. Never invent admission rates.
6. Never convert 3.23/4.00 into a French /20 grade without an official conversion rule.
7. Never call a programme "90% admission chance" without defensible official statistical data.
8. Use a Safe-Fit Confidence score instead.
9. A hard eligibility failure overrides every positive factor.
10. Verify IELTS subsection requirements.
11. Verify French-language requirements.
12. Verify the application route specifically for the candidate's nationality/residence.
13. Verify current/target-cycle opening and deadline.
14. If target-cycle information is not published, clearly say so and use the latest official
    cycle only as provisional evidence.
15. Prefer outside Paris and Île-de-France, but never assume a regional university is easy.
16. Actively search for reasons each candidate programme may reject this applicant.
17. If a requirement remains ambiguous after official-source research, do not label the
    programme safe.
18. Keep personal identity numbers out of prompts, logs and searches.

SEARCH PROCESS

A. Build a broad pool of relevant French public-university programmes.
B. Apply hard eligibility filters.
C. Map programme prerequisites to the candidate's transcript.
D. Evaluate language compatibility.
E. Verify candidate-specific application route.
F. Investigate selectivity/capacity evidence.
G. Give preference to regional and lower-visibility programmes.
H. Run a skeptic/rejection pass.
I. Validate all evidence.
J. Rank surviving programmes by Safe-Fit Confidence.
K. Select seven with sensible diversification.

TARGET PROGRAMME FAMILIES

Prioritize:
- Informatique / Computer Science
- Software Engineering / Génie Logiciel
- Distributed Systems
- Applied Computer Science
- Information Systems
- Web/Application Engineering
- general CS programmes with suitable specialization
- selected applied AI programmes

Treat with greater caution:
- highly mathematical AI/ML
- pure Data Science/statistics
- elite research tracks
- programmes explicitly requiring excellent academic records
- programmes with very small cohorts

OUTPUT

For each selected programme report:
- university;
- exact programme;
- track/parcours;
- M1/M2;
- city/campus;
- public/private;
- teaching language;
- official academic prerequisites;
- transcript match;
- IELTS/French check;
- application route;
- opening/deadline;
- capacity/selectivity evidence if available;
- reasons it is a strong fit;
- reasons admission could still fail;
- Safe-Fit Confidence /100;
- official sources.

Conclude with:
- final comparison table;
- 3–5 reserve programmes;
- rejected-programme log with reasons;
- unresolved items requiring manual confirmation.

Do not optimize for optimism. Falsify the "safe" hypothesis before recommending a programme.
```

---

# 22. Recommended Technical Agent Components

Model choice is intentionally left open.

Suggested components:

```text
Orchestrator
 ├── DocumentParser
 ├── CandidateProfileBuilder
 ├── SearchPlanner
 ├── OfficialSourceRetriever
 ├── ProgrammeExtractor
 ├── EligibilityChecker
 ├── TranscriptMatcher
 ├── LanguageChecker
 ├── ApplicationRouteResolver
 ├── SelectivityAnalyzer
 ├── GeographicVisibilityAnalyzer
 ├── SkepticReviewer
 ├── EvidenceValidator
 └── ReportWriter
```

## Useful internal data structures

### ProgrammeCandidate
```json
{
  "university": "",
  "programme": "",
  "track": "",
  "level": "M1",
  "city": "",
  "public": true,
  "language": [],
  "requirements": [],
  "application_route": {},
  "deadlines": {},
  "curriculum": [],
  "capacity": null,
  "selectivity_evidence": [],
  "official_sources": []
}
```

### Evaluation
```json
{
  "hard_eligibility": "PASS",
  "curriculum_coverage": 0,
  "language_status": "PASS",
  "route_status": "PASS",
  "academic_competitiveness": 0,
  "selectivity_score": 0,
  "regional_visibility_score": 0,
  "evidence_score": 0,
  "skeptic_issues": [],
  "safe_fit_score": 0,
  "classification": ""
}
```

---

# 23. Stop Conditions

The agent must stop and flag manual review when:
- official sources contradict each other;
- application route is unclear;
- language of instruction is unclear;
- IELTS subscore policy is missing but likely important;
- programme page is outdated;
- only third-party information can be found;
- required undergraduate ECTS cannot be mapped confidently;
- admission is based on an exam/interview whose requirements cannot be verified.

---

# 24. Evidence That Would Change the Assessment

A programme can move upward if official evidence shows:
- no strict GPA threshold;
- broad CS Bachelor's accepted;
- candidate satisfies all named prerequisites;
- IELTS 6.5 / current subscores accepted;
- English-medium degree accepted;
- reasonable cohort capacity;
- low historical applicant pressure;
- no entrance exam;
- direct M1 eligibility;
- clear Études en France route;
- regional campus with lower demand.

A programme should move downward if evidence shows:
- "excellent academic record" or top-rank expectation;
- strong advanced mathematics requirement;
- IELTS 6.0 minimum in every component;
- French B2/C1 proof required;
- very small capacity;
- high applicant-to-seat pressure;
- mandatory exam;
- only M2 entry;
- highly specialized prior-degree requirement;
- unclear or conflicting official requirements.

---

# 25. Candidate-Specific Strategy Summary

The candidate is **not a weak applicant**, but the 3.23/4.00 CGPA means the search should not be built around elite-name universities or highly selective AI/Data Science programmes.

The strongest strategy is:

1. Use the full BSCS foundation as the main academic asset.
2. Favor general/applied Computer Science and software/systems programmes.
3. Use AI/RAG work to strengthen applied-AI options, not to pretend the transcript is a pure AI degree.
4. Prefer regional public universities outside Paris.
5. Require exact language compatibility because the IELTS Speaking score is 5.5.
6. Use professional work and the shipped SaaS/product portfolio as supporting evidence.
7. Use course-level transcript matching rather than overall CGPA alone.
8. Treat "less famous" only as a discovery preference, never as proof of easy admission.
9. Keep seven final choices diversified by specialization and geography.
10. Reject any choice that cannot survive the skeptic pass.

---

# 26. Remaining Input Before Production Research

Before running the final university search, ideally add:
- official IELTS Test Report Form / certificate;
- optionally course descriptions/syllabi if a programme has precise prerequisite-credit requirements.

The search can still begin using the score recorded in the latest CV, but final application eligibility should be verified against the official IELTS document.

