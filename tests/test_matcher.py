from internbuddy import matcher
from internbuddy.models import JobListing, UserProfile

PROFILE = UserProfile("A", "B.Tech", "machine learning", "a@x.com", "link")
LISTINGS = [
    JobListing("Acme", "ML Intern", "Remote", "deep learning", "http://a", "internshala"),
    JobListing("Beta", "Data Intern", "Pune", "sql etl", "http://b", "linkedin"),
]


class FakeResp:
    def __init__(self, text):
        self.text = text


class FakeClient:
    def __init__(self, text):
        self._text = text

    def generate_content(self, prompt):
        return FakeResp(self._text)


def test_match_jobs_parses_gemini_json():
    client = FakeClient('```json\n{"matches":[{"index":1,"why":"great fit"},'
                        '{"index":0,"why":"also good"}]}\n```')
    out = matcher.match_jobs(PROFILE, "resume", LISTINGS, top_n=2, client=client)
    assert len(out) == 2
    assert out[0].company == "Beta"       # index 1 first
    assert out[0].why == "great fit"
    assert out[0].rank == 1
    assert out[1].rank == 2


def test_match_jobs_empty_listings_returns_empty():
    assert matcher.match_jobs(PROFILE, "", [], client=FakeClient("{}")) == []


def test_match_jobs_falls_back_on_bad_json():
    client = FakeClient("not json at all")
    out = matcher.match_jobs(PROFILE, "resume", LISTINGS, top_n=2, client=client)
    assert len(out) == 2  # fallback returns listings with template why
    assert all(m.why for m in out)


def test_fallback_matches_ranks_sequentially():
    out = matcher.fallback_matches(LISTINGS, PROFILE, top_n=2)
    assert [m.rank for m in out] == [1, 2]
    assert out[0].company == "Acme"
