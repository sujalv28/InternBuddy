from internbuddy.models import UserProfile, JobListing, MatchedJob


def test_userprofile_validate_ok():
    p = UserProfile("Asha", "B.Tech CSE", "data science", "asha@example.com",
                    "https://drive.google.com/file/d/ABC/view")
    assert p.validate() == []


def test_userprofile_validate_collects_errors():
    p = UserProfile("", "B.Tech", "ml", "not-an-email", "")
    errs = p.validate()
    assert any("name" in e.lower() for e in errs)
    assert any("email" in e.lower() for e in errs)
    assert any("resume" in e.lower() for e in errs)


def test_dataclasses_construct():
    j = JobListing("Acme", "ML Intern", "Remote", "desc", "http://x", "linkedin")
    m = MatchedJob(j.company, j.role, j.location, j.description, j.url, j.source, "because", 1)
    assert m.rank == 1 and m.why == "because"
