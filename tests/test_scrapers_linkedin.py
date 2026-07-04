import scrapers

SAMPLE = """
<ul>
  <li>
    <div class="base-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/111?trk=abc"></a>
      <h3 class="base-search-card__title">Machine Learning Intern</h3>
      <h4 class="base-search-card__subtitle">OpenAI</h4>
      <span class="job-search-card__location">Bengaluru, India</span>
    </div>
  </li>
  <li>
    <div class="base-card">
      <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/222"></a>
      <h3 class="base-search-card__title">Data Analyst Intern</h3>
      <h4 class="base-search-card__subtitle">Google</h4>
      <span class="job-search-card__location">Remote</span>
    </div>
  </li>
  <li><div class="base-card"><h4 class="base-search-card__subtitle">NoTitle</h4></div></li>
</ul>
"""


def test_parse_linkedin_extracts_cards():
    jobs = scrapers.parse_linkedin(SAMPLE)
    assert len(jobs) == 2  # third card skipped (no title)
    assert jobs[0].role == "Machine Learning Intern"
    assert jobs[0].company == "OpenAI"
    assert jobs[0].location == "Bengaluru, India"
    assert jobs[0].source == "linkedin"
    assert jobs[0].url == "https://www.linkedin.com/jobs/view/111"  # query stripped
    assert jobs[0].description  # non-empty


def test_parse_linkedin_blanks_non_http_url():
    evil = """
    <ul><li><div class="base-card">
      <a class="base-card__full-link" href="javascript:alert(1)"></a>
      <h3 class="base-search-card__title">Intern</h3>
      <h4 class="base-search-card__subtitle">Corp</h4>
    </div></li></ul>
    """
    jobs = scrapers.parse_linkedin(evil)
    assert jobs[0].url == ""  # javascript: link rejected


def test_scrape_linkedin_guest_calls_get(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=20):
        captured["url"] = url
        captured["params"] = params
        return SAMPLE

    monkeypatch.setattr(scrapers, "_get", fake_get)
    jobs = scrapers.scrape_linkedin_guest("data analyst", location="India")
    assert len(jobs) == 2
    assert "jobs-guest" in captured["url"]
    assert captured["params"]["keywords"] == "data analyst"
