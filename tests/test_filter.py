from internbuddy import matcher
from internbuddy.models import JobListing, UserProfile

PROFILE = UserProfile("A", "B.Tech CSE", "machine learning", "a@x.com", "link")


def _job(company, role, desc="", loc="Remote"):
    return JobListing(company, role, loc, desc, "http://x", "internshala")


def test_filter_dedupes_by_company_and_role():
    listings = [
        _job("Acme", "ML Intern"),
        _job("acme", "ml intern"),  # duplicate (case-insensitive)
        _job("Beta", "ML Intern"),
    ]
    out = matcher.filter_candidates(listings, PROFILE)
    assert len(out) == 2


def test_filter_ranks_relevant_first():
    listings = [
        _job("X", "Sales Intern", "cold calling"),
        _job("Y", "Machine Learning Intern", "deep learning models"),
    ]
    out = matcher.filter_candidates(listings, PROFILE)
    assert out[0].company == "Y"


def test_filter_respects_limit():
    listings = [_job(f"C{i}", f"Role {i}") for i in range(30)]
    out = matcher.filter_candidates(listings, PROFILE, limit=10)
    assert len(out) == 10
