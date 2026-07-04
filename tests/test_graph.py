import graph, resume, scrapers, matcher, report, mailer
from models import JobListing, MatchedJob, UserProfile

PROFILE = UserProfile("Asha", "B.Tech", "machine learning", "a@x.com",
                      "https://drive.google.com/file/d/ID/view")


def _patch_all(monkeypatch, listings, matched):
    monkeypatch.setattr(resume, "get_resume_text", lambda link: "resume text")
    monkeypatch.setattr(scrapers, "scrape_internshala", lambda foi, max_pages=1: listings)
    monkeypatch.setattr(scrapers, "scrape_linkedin_guest",
                        lambda foi, location="India", start=0: [])
    monkeypatch.setattr(matcher, "match_jobs",
                        lambda p, r, l, top_n=10, client=None, api_key=None: matched)
    monkeypatch.setattr(mailer, "send_report",
                        lambda p, b, f, m, smtp=None: "sent")


def test_run_happy_path(monkeypatch):
    listings = [JobListing("Acme", "ML Intern", "Remote", "dl", "http://a", "internshala")]
    matched = [MatchedJob("Acme", "ML Intern", "Remote", "dl", "http://a",
                          "internshala", "http://a", "fit", 1)]
    _patch_all(monkeypatch, listings, matched)
    state = graph.run(PROFILE, report_format="csv", top_n=5)
    assert len(state["matched_jobs"]) == 1
    assert state["report_bytes"][:7] == b"Company"
    assert state["email_status"] == "sent"
    assert state["errors"] == []


def test_run_scraper_error_is_captured(monkeypatch):
    def boom(foi, max_pages=1):
        raise RuntimeError("blocked")

    matched = [MatchedJob("Beta", "Data Intern", "Pune", "sql", "http://b",
                          "linkedin", "http://b", "fit", 1)]
    monkeypatch.setattr(resume, "get_resume_text", lambda link: "")
    monkeypatch.setattr(scrapers, "scrape_internshala", boom)
    monkeypatch.setattr(scrapers, "scrape_linkedin_guest",
                        lambda foi, location="India", start=0:
                        [JobListing("Beta", "Data Intern", "Pune", "sql", "http://b", "linkedin")])
    monkeypatch.setattr(matcher, "match_jobs",
                        lambda p, r, l, top_n=10, client=None, api_key=None: matched)
    monkeypatch.setattr(mailer, "send_report", lambda p, b, f, m, smtp=None: "sent")
    state = graph.run(PROFILE, report_format="csv")
    assert any("Internshala" in e for e in state["errors"])
    assert len(state["matched_jobs"]) == 1  # LinkedIn still produced results


def test_run_no_results_skips_email(monkeypatch):
    monkeypatch.setattr(resume, "get_resume_text", lambda link: "")
    monkeypatch.setattr(scrapers, "scrape_internshala", lambda foi, max_pages=1: [])
    monkeypatch.setattr(scrapers, "scrape_linkedin_guest",
                        lambda foi, location="India", start=0: [])
    state = graph.run(PROFILE, report_format="csv")
    assert state["matched_jobs"] == []
    assert "skipped" in state["email_status"]
