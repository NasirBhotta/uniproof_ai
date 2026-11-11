from france_admission_agent.pipeline.research import parse_claims
from france_admission_agent.pipeline.research import TargetedResearch
from france_admission_agent.validators import validate_teaching_language
from france_admission_agent.schemas import ProgrammeCandidate, LanguageStatus
from france_admission_agent.pipeline.state import now
from france_admission_agent.pipeline.state import migrate
from france_admission_agent.pipeline.service import enqueue
from france_admission_agent.pipeline.backlog import pending_priority
from france_admission_agent.memory.database import init_database


def test_programme_specific_b2_and_eef_language_phrasing():
    text = ('Master DS - M1. Applicants must demonstrate proficiency in English at the CEFR level B2 or above. '
            'Applicants currently living in one of the countries listed under the Campus France procedure '
            'Études en France must follow that procedure.')
    assert parse_claims('language', text)['english_cefr_required'] == 'B2'
    assert parse_claims('route', text)['application_route'] == 'Études en France'


def test_dual_application_route_is_preserved():
    text='Pakistan applicants must apply on both Études en France and FSA applications.'
    assert parse_claims('route',text)['application_route']=='Études en France + FSA'


def test_french_claim_not_overridden_by_english_course_on_same_page():
    p = ProgrammeCandidate(programme_id='p', university='Université de Lille',
                           programme='Master Informatique', track='General', level='M1', city='Lille',
                           official_university_domain='univ-lille.fr')
    TargetedResearch.apply(p,'teaching_language','French','https://www.univ-lille.fr/master',
                           "Langue d'enseignement : Français. UE Anglais: Optional English course.",now())
    assert validate_teaching_language(p).status == LanguageStatus.VERIFIED_FRENCH


def test_official_english_page_precedes_international_name(tmp_path):
    db=tmp_path/'memory.db';conn=init_database(db);migrate(conn,tmp_path)
    base=dict(institution_id='strasbourg',university='Université de Strasbourg',
              programme='Master Informatique',city='Strasbourg',region='Grand Est',level='M1')
    french=dict(base,track='International',programme_url='https://www.unistra.fr/master/parcours-international')
    english=dict(base,track='Software Engineering',programme_url='https://www.unistra.fr/master/parcours-software-engineering')
    assert enqueue(conn,french,1)
    assert enqueue(conn,english,2)
    for cat,language in ((french,'French'),(english,'English')):
        conn.execute('INSERT INTO source_documents(url,institution_id,extracted_text,retrieved_at,content_hash) VALUES (?,?,?,?,?)',
                     (cat['programme_url'],'strasbourg','Language of instruction: '+language,now(),'test'))
    conn.commit();conn.close()
    leads=pending_priority(db)
    assert [lead['track'] for lead in leads]==['Software Engineering','International']
    assert leads[0]['teaching_language_hint']=='English'
