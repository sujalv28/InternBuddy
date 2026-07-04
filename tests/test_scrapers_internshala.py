import scrapers

SAMPLE = """
<div id="internship_list_container">
  <div class="individual_internship">
    <h3 class="job-internship-name"><a href="/internship/detail/web-1">Web Development</a></h3>
    <p class="company-name">Acme Corp</p>
    <div class="location_link">Mumbai</div>
    <div class="item_body">Stipend 10000 /month</div>
    <div class="item_body">Duration 3 Months</div>
  </div>
  <div class="individual_internship">
    <h3 class="job-internship-name"><a href="https://internshala.com/x/data-2">Data Science</a></h3>
    <p class="company-name">DataWorks</p>
    <div class="location_link">Remote</div>
    <div class="item_body">Stipend 15000 /month</div>
  </div>
  <div class="individual_internship">
    <p class="company-name">MissingRole Inc</p>
  </div>
</div>
"""


def test_parse_internshala_extracts_cards():
    jobs = scrapers.parse_internshala(SAMPLE)
    assert len(jobs) == 2  # third card skipped (no role)
    first = jobs[0]
    assert first.company == "Acme Corp"
    assert first.role == "Web Development"
    assert first.location == "Mumbai"
    assert first.source == "internshala"
    assert first.url == "https://internshala.com/internship/detail/web-1"
    assert "Stipend 10000 /month" in first.description


def test_parse_internshala_absolute_url_kept():
    jobs = scrapers.parse_internshala(SAMPLE)
    assert jobs[1].url == "https://internshala.com/x/data-2"


def test_scrape_internshala_calls_get(monkeypatch):
    monkeypatch.setattr(scrapers, "_get", lambda url, params=None, timeout=20: SAMPLE)
    monkeypatch.setattr(scrapers.time, "sleep", lambda s: None)
    jobs = scrapers.scrape_internshala("web development", max_pages=1)
    assert len(jobs) == 2
