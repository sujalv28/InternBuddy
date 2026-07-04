import scrapers

PAYLOAD = {
    "results": [
        {
            "name": "Machine Learning Intern",
            "company": {"name": "Example Corp"},
            "locations": [{"name": "Remote"}],
            "refs": {"landing_page": "https://example.com/jobs/ml-intern"},
            "contents": "<p>Work on <b>deep learning</b> models and apply now.</p>",
        },
        {
            "name": "Marketing Intern",
            "company": {"name": "BrandCo"},
            "locations": [{"name": "New York, NY"}],
            "refs": {"landing_page": "https://brandco.com/careers/mkt"},
            "contents": "<p>Social media campaigns.</p>",
        },
        {  # dropped: no landing page (apply link)
            "name": "Ghost Intern",
            "company": {"name": "Nowhere"},
            "locations": [],
            "refs": {"landing_page": ""},
            "contents": "",
        },
    ]
}


def test_parse_jobs_api_extracts_apply_link_and_strips_html():
    jobs = scrapers.parse_jobs_api(PAYLOAD)
    assert len(jobs) == 2  # entry with no landing page dropped
    ml = jobs[0]
    assert ml.role == "Machine Learning Intern"
    assert ml.company == "Example Corp"
    assert ml.url == "https://example.com/jobs/ml-intern"  # apply link
    assert ml.source == "web"
    assert "deep learning" in ml.description
    assert "<" not in ml.description  # HTML stripped


def test_scrape_web_search_filters_by_interest(monkeypatch):
    monkeypatch.setattr(scrapers, "_get_json", lambda url, params=None, timeout=20: PAYLOAD)
    monkeypatch.setattr(scrapers.time, "sleep", lambda s: None)
    jobs = scrapers.scrape_web_search("machine learning", pages=1)
    roles = [j.role for j in jobs]
    assert "Machine Learning Intern" in roles
    assert "Marketing Intern" not in roles  # filtered out by interest
