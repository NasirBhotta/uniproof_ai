from france_admission_agent.research.source_policy import (
    is_discovery_only_source,
    is_trusted_national_source,
    source_is_eligible_for_final_claim,
)


def test_campus_france_is_trusted():
    assert is_trusted_national_source("https://www.campusfrance.org/fr/test")


def test_monmaster_is_trusted():
    assert is_trusted_national_source("https://www.monmaster.gouv.fr/formation/test")


def test_reddit_is_discovery_only():
    assert is_discovery_only_source("https://www.reddit.com/r/france/test")
    assert not source_is_eligible_for_final_claim("https://www.reddit.com/r/france/test")


def test_explicit_official_domain_is_allowed():
    assert source_is_eligible_for_final_claim(
        "https://formations.univ-example.fr/master/info",
        official_university_domains={"univ-example.fr"},
    )
