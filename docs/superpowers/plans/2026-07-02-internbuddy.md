# Internbuddy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Internbuddy — a Streamlit + LangGraph agent that takes a user's profile and Google Drive resume, scrapes internships from Internshala and LinkedIn (guest), ranks them with Gemini, and delivers a PDF/CSV report by download and email.

**Architecture:** A linear LangGraph state graph (`parse_resume → scrape → filter → match → generate_report → send_email`) drives flat single-responsibility modules. Streamlit collects inputs and renders the results table, download button, and email status. Every external failure is caught into `state.errors` and surfaced as a warning — the UI never crashes.

**Tech Stack:** Python 3.11+, Streamlit, LangGraph, google-generativeai (Gemini `gemini-2.5-flash`), requests + BeautifulSoup4, pdfplumber, python-docx, fpdf2, python-dotenv, pytest.

## Global Constraints

- Python 3.11+.
- Package name is `internbuddy`; all modules live under `internbuddy/`.
- Report columns are EXACTLY, in order: `Company`, `Job Role`, `Job Location`, `Job Description`, `Why This Role Is For You`.
- LLM model is `gemini-2.5-flash`.
- Job sources are Internshala and the LinkedIn guest jobs endpoint only. NO Indeed.
- Every node catches its own exceptions and appends a human-readable string to `state["errors"]`; nodes never raise.
- Scrapers send a custom `User-Agent` and sleep `REQUEST_DELAY` (1.0s) between requests.
- Tests never hit the live network; scraping/LLM/SMTP/HTTP are exercised via inline fixtures or fakes.
- Run all commands from the repo root: `E:\Workspace\Internbuddy - AI Internship seeker`.

---

### Task 1: Project scaffold, config, and data models

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `pyproject.toml`
- Create: `internbuddy/__init__.py`
- Create: `internbuddy/config.py`
- Create: `internbuddy/models.py`
- Test: `tests/test_config.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `config.ConfigError` (Exception)
  - `config.get_google_api_key() -> str`
  - `config.get_smtp_config() -> dict` with keys `host, port(int), user, password, from_email`
  - `models.UserProfile(name, stream, field_of_interest, email, resume_link)` dataclass; method `validate() -> list[str]`
  - `models.JobListing(company, role, location, description, url, source)` dataclass
  - `models.MatchedJob(company, role, location, description, url, source, why, rank)` dataclass
  - `models.AgentState` (TypedDict, total=False) with keys: `profile, resume_text, raw_listings, filtered_listings, matched_jobs, report_bytes, report_mime, report_filename, report_format, top_n, email_status, errors`

- [ ] **Step 1: Create dependency and config scaffold files**

`requirements.txt`:
```
streamlit>=1.30
langgraph>=0.2
google-generativeai>=0.8
requests>=2.31
beautifulsoup4>=4.12
pdfplumber>=0.11
python-docx>=1.1
fpdf2>=2.7
python-dotenv>=1.0
pytest>=8.0
```

`.env.example`:
```
GOOGLE_API_KEY=your-gemini-api-key
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-16-char-app-password
FROM_EMAIL=you@gmail.com
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`internbuddy/__init__.py`:
```python
"""Internbuddy — AI internship search agent."""
```

- [ ] **Step 2: Write failing tests for config and models**

`tests/test_config.py`:
```python
import pytest
from internbuddy import config


def test_get_google_api_key_present(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "abc123")
    assert config.get_google_api_key() == "abc123"


def test_get_google_api_key_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(config.ConfigError):
        config.get_google_api_key()


def test_get_smtp_config_present(monkeypatch):
    for k, v in {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "u@example.com",
        "SMTP_PASSWORD": "pw",
        "FROM_EMAIL": "u@example.com",
    }.items():
        monkeypatch.setenv(k, v)
    cfg = config.get_smtp_config()
    assert cfg["host"] == "smtp.example.com"
    assert cfg["port"] == 587
    assert cfg["from_email"] == "u@example.com"


def test_get_smtp_config_missing(monkeypatch):
    for k in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"]:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(config.ConfigError):
        config.get_smtp_config()
```

`tests/test_models.py`:
```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py tests/test_models.py -v`
Expected: FAIL (ModuleNotFoundError: internbuddy.config / internbuddy.models)

- [ ] **Step 4: Implement config.py and models.py**

`internbuddy/config.py`:
```python
import os

from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    """Raised when required configuration is missing."""


def get_google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ConfigError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your Gemini key."
        )
    return key


def get_smtp_config() -> dict:
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "FROM_EMAIL"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise ConfigError(f"Missing SMTP configuration: {', '.join(missing)}")
    return {
        "host": os.getenv("SMTP_HOST"),
        "port": int(os.getenv("SMTP_PORT")),
        "user": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASSWORD"),
        "from_email": os.getenv("FROM_EMAIL"),
    }
```

`internbuddy/models.py`:
```python
from dataclasses import dataclass
from typing import TypedDict


@dataclass
class UserProfile:
    name: str
    stream: str
    field_of_interest: str
    email: str
    resume_link: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("Name is required.")
        if not self.stream.strip():
            errors.append("Educational stream is required.")
        if not self.field_of_interest.strip():
            errors.append("Field of interest is required.")
        if "@" not in self.email or "." not in self.email:
            errors.append("A valid email is required.")
        if not self.resume_link.strip():
            errors.append("Resume link is required.")
        return errors


@dataclass
class JobListing:
    company: str
    role: str
    location: str
    description: str
    url: str
    source: str


@dataclass
class MatchedJob:
    company: str
    role: str
    location: str
    description: str
    url: str
    source: str
    why: str
    rank: int


class AgentState(TypedDict, total=False):
    profile: UserProfile
    resume_text: str
    raw_listings: list
    filtered_listings: list
    matched_jobs: list
    report_bytes: bytes
    report_mime: str
    report_filename: str
    report_format: str
    top_n: int
    email_status: str
    errors: list
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py tests/test_models.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example pyproject.toml internbuddy/__init__.py internbuddy/config.py internbuddy/models.py tests/test_config.py tests/test_models.py
git commit -m "feat: scaffold internbuddy with config and data models"
```

---

### Task 2: Resume download and text extraction

**Files:**
- Create: `internbuddy/resume.py`
- Test: `tests/test_resume.py`

**Interfaces:**
- Consumes: nothing from prior tasks.
- Produces:
  - `resume.ResumeError` (Exception)
  - `resume.extract_drive_id(link: str) -> str`
  - `resume.download_resume(link: str, timeout: int = 30) -> bytes`
  - `resume.extract_text(data: bytes) -> str`
  - `resume.get_resume_text(link: str) -> str` (download + extract)

- [ ] **Step 1: Write failing tests**

`tests/test_resume.py`:
```python
import io

import pytest
from docx import Document
from fpdf import FPDF

from internbuddy import resume


def test_extract_drive_id_file_form():
    link = "https://drive.google.com/file/d/1A2B3C_dEF/view?usp=sharing"
    assert resume.extract_drive_id(link) == "1A2B3C_dEF"


def test_extract_drive_id_open_form():
    link = "https://drive.google.com/open?id=XyZ-123"
    assert resume.extract_drive_id(link) == "XyZ-123"


def test_extract_drive_id_invalid():
    with pytest.raises(resume.ResumeError):
        resume.extract_drive_id("https://example.com/nope")


def test_extract_text_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Skilled in Python and machine learning")
    data = bytes(pdf.output())
    text = resume.extract_text(data)
    assert "Python" in text


def test_extract_text_docx():
    doc = Document()
    doc.add_paragraph("Experienced in data science and SQL")
    buf = io.BytesIO()
    doc.save(buf)
    text = resume.extract_text(buf.getvalue())
    assert "data science" in text


def test_get_resume_text_uses_download(monkeypatch):
    doc = Document()
    doc.add_paragraph("hello resume")
    buf = io.BytesIO()
    doc.save(buf)
    monkeypatch.setattr(resume, "download_resume", lambda link, timeout=30: buf.getvalue())
    assert "hello resume" in resume.get_resume_text("https://drive.google.com/file/d/ID/view")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_resume.py -v`
Expected: FAIL (ModuleNotFoundError: internbuddy.resume)

- [ ] **Step 3: Implement resume.py**

`internbuddy/resume.py`:
```python
import io
import re

import pdfplumber
import requests
from docx import Document

_DRIVE_ID_RE = re.compile(r"/d/([A-Za-z0-9_-]+)|[?&]id=([A-Za-z0-9_-]+)")


class ResumeError(Exception):
    """Raised when a resume cannot be fetched or parsed."""


def extract_drive_id(link: str) -> str:
    match = _DRIVE_ID_RE.search(link or "")
    if not match:
        raise ResumeError(f"Could not find a Google Drive file id in: {link!r}")
    return match.group(1) or match.group(2)


def download_resume(link: str, timeout: int = 30) -> bytes:
    file_id = extract_drive_id(link)
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def extract_text(data: bytes) -> str:
    if data[:4] == b"%PDF":
        parts = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    if data[:2] == b"PK":  # DOCX files are ZIP archives
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    return data.decode("utf-8", errors="ignore").strip()


def get_resume_text(link: str) -> str:
    return extract_text(download_resume(link))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_resume.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add internbuddy/resume.py tests/test_resume.py
git commit -m "feat: add Google Drive resume download and text extraction"
```

---

### Task 3: Internshala scraper

**Files:**
- Create: `internbuddy/scrapers.py`
- Test: `tests/test_scrapers_internshala.py`

**Interfaces:**
- Consumes: `models.JobListing`.
- Produces:
  - `scrapers.HEADERS` (dict), `scrapers.REQUEST_DELAY` (float)
  - `scrapers._get(url, params=None, timeout=20) -> str`
  - `scrapers.parse_internshala(html: str) -> list[JobListing]`
  - `scrapers.scrape_internshala(field_of_interest: str, max_pages: int = 1) -> list[JobListing]`

- [ ] **Step 1: Write failing test with an inline HTML fixture**

`tests/test_scrapers_internshala.py`:
```python
from internbuddy import scrapers

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scrapers_internshala.py -v`
Expected: FAIL (ModuleNotFoundError: internbuddy.scrapers)

- [ ] **Step 3: Implement scrapers.py (shared helpers + Internshala)**

`internbuddy/scrapers.py`:
```python
import time

import requests
from bs4 import BeautifulSoup

from .models import JobListing

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InternbuddyBot/1.0; +https://example.com/bot)"
}
REQUEST_DELAY = 1.0


def _get(url, params=None, timeout=20) -> str:
    resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_internshala(html: str) -> list[JobListing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[JobListing] = []
    for card in soup.select("div.individual_internship"):
        role_el = card.select_one(".job-internship-name") or card.select_one(".profile")
        company_el = card.select_one(".company-name") or card.select_one(".company_name")
        if not role_el or not company_el:
            continue
        role = role_el.get_text(strip=True)
        company = company_el.get_text(strip=True)
        loc_el = card.select_one(".location_link") or card.select_one(".locations")
        location = loc_el.get_text(strip=True) if loc_el else "Not specified"

        link_el = role_el if role_el.name == "a" else role_el.select_one("a")
        href = link_el["href"] if link_el and link_el.has_attr("href") else ""
        url = href if href.startswith("http") else f"https://internshala.com{href}"

        meta = []
        for chip in card.select(".item_body, .stipend, .status-success"):
            text = chip.get_text(strip=True)
            if text:
                meta.append(text)
        description = " | ".join(dict.fromkeys(meta)) or f"{role} at {company}"

        listings.append(JobListing(company, role, location, description, url, "internshala"))
    return listings


def scrape_internshala(field_of_interest: str, max_pages: int = 1) -> list[JobListing]:
    keyword = field_of_interest.strip().lower().replace(" ", "-")
    results: list[JobListing] = []
    for page in range(1, max_pages + 1):
        url = f"https://internshala.com/internships/keywords-{keyword}/page-{page}/"
        html = _get(url)
        results.extend(parse_internshala(html))
        time.sleep(REQUEST_DELAY)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scrapers_internshala.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add internbuddy/scrapers.py tests/test_scrapers_internshala.py
git commit -m "feat: add Internshala scraper"
```

---

### Task 4: LinkedIn guest scraper

**Files:**
- Modify: `internbuddy/scrapers.py` (append two functions)
- Test: `tests/test_scrapers_linkedin.py`

**Interfaces:**
- Consumes: `scrapers._get`, `scrapers.REQUEST_DELAY`, `models.JobListing`.
- Produces:
  - `scrapers.parse_linkedin(html: str) -> list[JobListing]`
  - `scrapers.scrape_linkedin_guest(field_of_interest: str, location: str = "India", start: int = 0) -> list[JobListing]`

- [ ] **Step 1: Write failing test with inline fixture**

`tests/test_scrapers_linkedin.py`:
```python
from internbuddy import scrapers

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scrapers_linkedin.py -v`
Expected: FAIL (AttributeError: module has no attribute 'parse_linkedin')

- [ ] **Step 3: Append LinkedIn functions to scrapers.py**

Add to the end of `internbuddy/scrapers.py`:
```python
def parse_linkedin(html: str) -> list[JobListing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[JobListing] = []
    for card in soup.select("li"):
        role_el = card.select_one("h3.base-search-card__title")
        company_el = card.select_one("h4.base-search-card__subtitle")
        if not role_el or not company_el:
            continue
        role = role_el.get_text(strip=True)
        company = company_el.get_text(strip=True)
        loc_el = card.select_one(".job-search-card__location")
        location = loc_el.get_text(strip=True) if loc_el else "Not specified"
        link_el = card.select_one("a.base-card__full-link") or card.select_one("a")
        url = ""
        if link_el and link_el.has_attr("href"):
            url = link_el["href"].split("?")[0]
        description = (
            f"{role} at {company} in {location}. "
            f"View the full description on LinkedIn: {url}"
        )
        listings.append(JobListing(company, role, location, description, url, "linkedin"))
    return listings


def scrape_linkedin_guest(field_of_interest: str, location: str = "India",
                          start: int = 0) -> list[JobListing]:
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {"keywords": field_of_interest, "location": location, "start": start}
    html = _get(url, params=params)
    time.sleep(REQUEST_DELAY)
    return parse_linkedin(html)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scrapers_linkedin.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add internbuddy/scrapers.py tests/test_scrapers_linkedin.py
git commit -m "feat: add LinkedIn guest scraper"
```

---

### Task 5: Candidate filtering (dedupe + relevance)

**Files:**
- Create: `internbuddy/matcher.py`
- Test: `tests/test_filter.py`

**Interfaces:**
- Consumes: `models.JobListing`, `models.UserProfile`.
- Produces:
  - `matcher.filter_candidates(listings: list[JobListing], profile: UserProfile, limit: int = 25) -> list[JobListing]`

- [ ] **Step 1: Write failing test**

`tests/test_filter.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filter.py -v`
Expected: FAIL (ModuleNotFoundError: internbuddy.matcher)

- [ ] **Step 3: Implement filter_candidates in matcher.py**

Create `internbuddy/matcher.py`:
```python
import re

from .models import JobListing, UserProfile


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def filter_candidates(listings: list, profile: UserProfile, limit: int = 25) -> list:
    seen = set()
    deduped: list = []
    for job in listings:
        key = (job.company.strip().lower(), job.role.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    interest = _tokens(f"{profile.field_of_interest} {profile.stream}")

    def score(job: JobListing) -> int:
        return len(interest & _tokens(f"{job.role} {job.description}"))

    ranked = sorted(deduped, key=score, reverse=True)
    return ranked[:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filter.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add internbuddy/matcher.py tests/test_filter.py
git commit -m "feat: add candidate dedupe and relevance filtering"
```

---

### Task 6: Gemini matching + why-text (with fallback)

**Files:**
- Modify: `internbuddy/matcher.py` (append matching functions)
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `matcher.filter_candidates`, `models.MatchedJob`, `config.get_google_api_key`.
- Produces:
  - `matcher.fallback_matches(listings: list, profile: UserProfile, top_n: int = 10) -> list[MatchedJob]`
  - `matcher.match_jobs(profile, resume_text: str, listings: list, top_n: int = 10, client=None) -> list[MatchedJob]`
  - Note: `client` is any object with `generate_content(prompt: str)` returning an object with a `.text` attribute; when `None`, a real Gemini model is created.

- [ ] **Step 1: Write failing test with a fake Gemini client**

`tests/test_matcher.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_matcher.py -v`
Expected: FAIL (AttributeError: module has no attribute 'match_jobs')

- [ ] **Step 3: Append matching logic to matcher.py**

Add to the top of `internbuddy/matcher.py` (imports) and the bottom (functions):

Add these imports below the existing `import re`:
```python
import json

from .models import MatchedJob
```

Append at the end of `internbuddy/matcher.py`:
```python
_MODEL_NAME = "gemini-2.5-flash"

_PROMPT_TEMPLATE = """You are an expert internship matching assistant.

Candidate profile:
- Name: {name}
- Educational stream: {stream}
- Field of interest: {interest}

Candidate resume (may be empty):
\"\"\"{resume}\"\"\"

Below are internship listings as a numbered list (index: role @ company - description).
Pick the best matches for this candidate, ranked best first, at most {top_n} items.
For each, write a 2-3 sentence "why this role is for you" grounded in the
candidate's stream, interest, and resume.

Listings:
{listings}

Return ONLY valid JSON, no prose, in exactly this shape:
{{"matches": [{{"index": <int>, "why": "<text>"}}]}}
"""


def _default_client():
    import google.generativeai as genai

    from .config import get_google_api_key

    genai.configure(api_key=get_google_api_key())
    return genai.GenerativeModel(_MODEL_NAME)


def _format_listings(listings: list) -> str:
    lines = []
    for i, job in enumerate(listings):
        lines.append(f"{i}: {job.role} @ {job.company} - {job.description[:200]}")
    return "\n".join(lines)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start:end + 1])


def fallback_matches(listings: list, profile: UserProfile, top_n: int = 10) -> list:
    out = []
    for rank, job in enumerate(listings[:top_n], start=1):
        why = (
            f"This {job.role} position aligns with your interest in "
            f"{profile.field_of_interest} and your {profile.stream} background, "
            f"offering hands-on experience at {job.company}."
        )
        out.append(MatchedJob(job.company, job.role, job.location, job.description,
                              job.url, job.source, why, rank))
    return out


def match_jobs(profile: UserProfile, resume_text: str, listings: list,
               top_n: int = 10, client=None) -> list:
    if not listings:
        return []
    model = client or _default_client()
    prompt = _PROMPT_TEMPLATE.format(
        name=profile.name,
        stream=profile.stream,
        interest=profile.field_of_interest,
        resume=(resume_text or "")[:4000],
        top_n=top_n,
        listings=_format_listings(listings),
    )
    try:
        resp = model.generate_content(prompt)
        data = _parse_json(resp.text)
        matches = []
        for rank, item in enumerate(data.get("matches", [])[:top_n], start=1):
            idx = int(item["index"])
            if 0 <= idx < len(listings):
                job = listings[idx]
                matches.append(MatchedJob(job.company, job.role, job.location,
                                          job.description, job.url, job.source,
                                          str(item.get("why", "")), rank))
        if not matches:
            raise ValueError("Model returned no valid matches")
        return matches
    except Exception:
        return fallback_matches(listings, profile, top_n)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_matcher.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add internbuddy/matcher.py tests/test_matcher.py
git commit -m "feat: add Gemini matching with why-text and fallback"
```

---

### Task 7: Report generation (CSV + PDF)

**Files:**
- Create: `internbuddy/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `models.MatchedJob`, `models.UserProfile`.
- Produces:
  - `report.COLUMNS` (list[str])
  - `report.build_csv(matched: list) -> bytes`
  - `report.build_pdf(matched: list, profile: UserProfile) -> bytes`
  - `report.build_report(fmt: str, matched: list, profile: UserProfile) -> tuple[bytes, str, str]` returning `(data, mime, filename)`; `fmt` is `"csv"` or `"pdf"`.

- [ ] **Step 1: Write failing test**

`tests/test_report.py`:
```python
import csv
import io

from internbuddy import report
from internbuddy.models import MatchedJob, UserProfile

PROFILE = UserProfile("Asha", "B.Tech", "ML", "a@x.com", "link")
MATCHED = [
    MatchedJob("Acme", "ML Intern", "Remote", "deep learning role",
               "http://a", "internshala", "You love ML.", 1),
    MatchedJob("Beta", "Data Intern", "Pune", "sql work",
               "http://b", "linkedin", "Great growth.", 2),
]


def test_build_csv_headers_and_rows():
    data = report.build_csv(MATCHED)
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    assert rows[0] == ["Company", "Job Role", "Job Location",
                       "Job Description", "Why This Role Is For You"]
    assert rows[1][0] == "Acme"
    assert rows[1][4] == "You love ML."
    assert len(rows) == 3  # header + 2


def test_build_pdf_returns_pdf_bytes():
    data = report.build_pdf(MATCHED, PROFILE)
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"


def test_build_report_csv_dispatch():
    data, mime, filename = report.build_report("csv", MATCHED, PROFILE)
    assert mime == "text/csv"
    assert filename.endswith(".csv")
    assert data[:7] == b"Company"


def test_build_report_pdf_dispatch():
    data, mime, filename = report.build_report("pdf", MATCHED, PROFILE)
    assert mime == "application/pdf"
    assert filename.endswith(".pdf")
    assert data[:4] == b"%PDF"


def test_build_pdf_handles_non_latin_text():
    matched = [MatchedJob("Café", "Rôle", "Zürich", "naïve résumé",
                          "http://c", "linkedin", "Perfect — go for it! ★", 1)]
    data = report.build_pdf(matched, PROFILE)
    assert data[:4] == b"%PDF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py -v`
Expected: FAIL (ModuleNotFoundError: internbuddy.report)

- [ ] **Step 3: Implement report.py**

`internbuddy/report.py`:
```python
import csv
import io

from fpdf import FPDF

from .models import UserProfile

COLUMNS = ["Company", "Job Role", "Job Location", "Job Description",
           "Why This Role Is For You"]


def _latin1(text: str) -> str:
    """fpdf2 core fonts are latin-1 only; drop unencodable characters."""
    return (text or "").encode("latin-1", errors="replace").decode("latin-1")


def build_csv(matched: list) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(COLUMNS)
    for job in matched:
        writer.writerow([job.company, job.role, job.location, job.description, job.why])
    return buf.getvalue().encode("utf-8")


def build_pdf(matched: list, profile: UserProfile) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Internbuddy - Internship Matches", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, _latin1(f"Prepared for {profile.name}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    for job in matched:
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 7, _latin1(f"{job.rank}. {job.role} - {job.company}"))
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, _latin1(f"Location: {job.location}"))
        pdf.multi_cell(0, 6, _latin1(f"Description: {job.description}"))
        pdf.multi_cell(0, 6, _latin1(f"Why this role is for you: {job.why}"))
        pdf.ln(3)
    out = pdf.output()
    return bytes(out)


def build_report(fmt: str, matched: list, profile: UserProfile) -> tuple:
    if fmt == "pdf":
        return build_pdf(matched, profile), "application/pdf", "internbuddy_report.pdf"
    return build_csv(matched), "text/csv", "internbuddy_report.csv"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add internbuddy/report.py tests/test_report.py
git commit -m "feat: add CSV and PDF report generation"
```

---

### Task 8: Email delivery over SMTP

**Files:**
- Create: `internbuddy/mailer.py`
- Test: `tests/test_mailer.py`

**Interfaces:**
- Consumes: `models.UserProfile`, `config.get_smtp_config`.
- Produces:
  - `mailer.send_report(profile: UserProfile, report_bytes: bytes, filename: str, mime: str, smtp: dict = None) -> str` returns `"sent"`. `mime` is a `"maintype/subtype"` string. When `smtp` is None, config is loaded from env.

- [ ] **Step 1: Write failing test with a fake SMTP server**

`tests/test_mailer.py`:
```python
from internbuddy import mailer
from internbuddy.models import UserProfile

PROFILE = UserProfile("Asha", "B.Tech", "ML", "asha@example.com", "link")
SMTP_CFG = {
    "host": "smtp.example.com", "port": 587, "user": "u@example.com",
    "password": "pw", "from_email": "u@example.com",
}


class FakeSMTP:
    instances = []

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.started_tls = False
        self.logged_in = None
        self.sent = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        self.sent = msg


def test_send_report_sends_message(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    status = mailer.send_report(PROFILE, b"col1,col2\n", "r.csv", "text/csv", smtp=SMTP_CFG)
    assert status == "sent"
    server = FakeSMTP.instances[0]
    assert server.started_tls is True
    assert server.logged_in == ("u@example.com", "pw")
    assert server.sent["To"] == "asha@example.com"
    assert server.sent["From"] == "u@example.com"
    # attachment present
    attachments = [p for p in server.sent.iter_attachments()]
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "r.csv"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mailer.py -v`
Expected: FAIL (ModuleNotFoundError: internbuddy.mailer)

- [ ] **Step 3: Implement mailer.py**

`internbuddy/mailer.py`:
```python
import smtplib
from email.message import EmailMessage

from .config import get_smtp_config
from .models import UserProfile


def send_report(profile: UserProfile, report_bytes: bytes, filename: str,
                mime: str, smtp: dict = None) -> str:
    cfg = smtp or get_smtp_config()

    msg = EmailMessage()
    msg["Subject"] = "Your Internbuddy internship matches"
    msg["From"] = cfg["from_email"]
    msg["To"] = profile.email
    msg.set_content(
        f"Hi {profile.name},\n\n"
        "Attached are your personalized internship matches from Internbuddy.\n\n"
        "Good luck!\n- Internbuddy"
    )

    maintype, subtype = mime.split("/", 1)
    msg.add_attachment(report_bytes, maintype=maintype, subtype=subtype,
                       filename=filename)

    with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
    return "sent"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_mailer.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add internbuddy/mailer.py tests/test_mailer.py
git commit -m "feat: add SMTP report email delivery"
```

---

### Task 9: LangGraph assembly

**Files:**
- Create: `internbuddy/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `resume.get_resume_text`, `scrapers.scrape_internshala`, `scrapers.scrape_linkedin_guest`, `matcher.filter_candidates`, `matcher.match_jobs`, `matcher.fallback_matches`, `report.build_report`, `mailer.send_report`, `models.*`.
- Produces:
  - `graph.build_graph()` -> compiled LangGraph app
  - `graph.run(profile: UserProfile, report_format: str = "csv", top_n: int = 10) -> AgentState`
  - Node functions (module-level, so tests can monkeypatch dependencies): `node_parse_resume`, `node_scrape`, `node_filter`, `node_match`, `node_report`, `node_email`.

- [ ] **Step 1: Write failing smoke test with all externals monkeypatched**

`tests/test_graph.py`:
```python
from internbuddy import graph, resume, scrapers, matcher, report, mailer
from internbuddy.models import JobListing, MatchedJob, UserProfile

PROFILE = UserProfile("Asha", "B.Tech", "machine learning", "a@x.com",
                      "https://drive.google.com/file/d/ID/view")


def _patch_all(monkeypatch, listings, matched):
    monkeypatch.setattr(resume, "get_resume_text", lambda link: "resume text")
    monkeypatch.setattr(scrapers, "scrape_internshala", lambda foi, max_pages=1: listings)
    monkeypatch.setattr(scrapers, "scrape_linkedin_guest",
                        lambda foi, location="India", start=0: [])
    monkeypatch.setattr(matcher, "match_jobs",
                        lambda p, r, l, top_n=10, client=None: matched)
    monkeypatch.setattr(mailer, "send_report",
                        lambda p, b, f, m, smtp=None: "sent")


def test_run_happy_path(monkeypatch):
    listings = [JobListing("Acme", "ML Intern", "Remote", "dl", "http://a", "internshala")]
    matched = [MatchedJob("Acme", "ML Intern", "Remote", "dl", "http://a",
                          "internshala", "fit", 1)]
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
                          "linkedin", "fit", 1)]
    monkeypatch.setattr(resume, "get_resume_text", lambda link: "")
    monkeypatch.setattr(scrapers, "scrape_internshala", boom)
    monkeypatch.setattr(scrapers, "scrape_linkedin_guest",
                        lambda foi, location="India", start=0:
                        [JobListing("Beta", "Data Intern", "Pune", "sql", "http://b", "linkedin")])
    monkeypatch.setattr(matcher, "match_jobs",
                        lambda p, r, l, top_n=10, client=None: matched)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_graph.py -v`
Expected: FAIL (ModuleNotFoundError: internbuddy.graph)

- [ ] **Step 3: Implement graph.py**

`internbuddy/graph.py`:
```python
from langgraph.graph import StateGraph, START, END

from . import matcher, mailer, report, resume, scrapers
from .models import AgentState, UserProfile


def node_parse_resume(state: AgentState) -> dict:
    errors = list(state.get("errors", []))
    try:
        text = resume.get_resume_text(state["profile"].resume_link)
    except Exception as exc:
        text = ""
        errors.append(f"Resume could not be read ({exc}); using stream/interest only.")
    return {"resume_text": text, "errors": errors}


def node_scrape(state: AgentState) -> dict:
    profile: UserProfile = state["profile"]
    errors = list(state.get("errors", []))
    listings = []
    try:
        listings += scrapers.scrape_internshala(profile.field_of_interest)
    except Exception as exc:
        errors.append(f"Internshala scrape failed: {exc}")
    try:
        listings += scrapers.scrape_linkedin_guest(profile.field_of_interest)
    except Exception as exc:
        errors.append(f"LinkedIn scrape failed: {exc}")
    return {"raw_listings": listings, "errors": errors}


def node_filter(state: AgentState) -> dict:
    filtered = matcher.filter_candidates(
        state.get("raw_listings", []), state["profile"]
    )
    return {"filtered_listings": filtered}


def node_match(state: AgentState) -> dict:
    errors = list(state.get("errors", []))
    filtered = state.get("filtered_listings", [])
    if not filtered:
        return {"matched_jobs": [], "errors": errors}
    try:
        matched = matcher.match_jobs(
            state["profile"], state.get("resume_text", ""),
            filtered, state.get("top_n", 10),
        )
    except Exception as exc:
        errors.append(f"Matching failed: {exc}")
        matched = matcher.fallback_matches(filtered, state["profile"],
                                           state.get("top_n", 10))
    return {"matched_jobs": matched, "errors": errors}


def node_report(state: AgentState) -> dict:
    matched = state.get("matched_jobs", [])
    if not matched:
        return {"report_bytes": b""}
    data, mime, filename = report.build_report(
        state.get("report_format", "csv"), matched, state["profile"]
    )
    return {"report_bytes": data, "report_mime": mime, "report_filename": filename}


def node_email(state: AgentState) -> dict:
    errors = list(state.get("errors", []))
    if not state.get("report_bytes"):
        return {"email_status": "skipped (no matches to send)", "errors": errors}
    try:
        mailer.send_report(
            state["profile"], state["report_bytes"],
            state["report_filename"], state["report_mime"],
        )
        status = "sent"
    except Exception as exc:
        status = f"failed: {exc}"
        errors.append(f"Email delivery failed: {exc}")
    return {"email_status": status, "errors": errors}


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("parse_resume", node_parse_resume)
    builder.add_node("scrape", node_scrape)
    builder.add_node("filter", node_filter)
    builder.add_node("match", node_match)
    builder.add_node("generate_report", node_report)
    builder.add_node("send_email", node_email)

    builder.add_edge(START, "parse_resume")
    builder.add_edge("parse_resume", "scrape")
    builder.add_edge("scrape", "filter")
    builder.add_edge("filter", "match")
    builder.add_edge("match", "generate_report")
    builder.add_edge("generate_report", "send_email")
    builder.add_edge("send_email", END)
    return builder.compile()


def run(profile: UserProfile, report_format: str = "csv", top_n: int = 10) -> AgentState:
    app = build_graph()
    initial: AgentState = {
        "profile": profile,
        "report_format": report_format,
        "top_n": top_n,
        "errors": [],
    }
    return app.invoke(initial)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_graph.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v`
Expected: PASS (all tests from Tasks 1-9)

- [ ] **Step 6: Commit**

```bash
git add internbuddy/graph.py tests/test_graph.py
git commit -m "feat: assemble LangGraph pipeline with graceful degradation"
```

---

### Task 10: Streamlit UI + README

**Files:**
- Create: `internbuddy/app.py`
- Create: `README.md`

**Interfaces:**
- Consumes: `graph.run`, `models.UserProfile`, `config.ConfigError`.
- Produces: a runnable Streamlit app (`streamlit run internbuddy/app.py`). No automated test — verified manually (Streamlit UIs are integration-verified; the pipeline is already covered by `test_graph.py`).

- [ ] **Step 1: Implement app.py**

`internbuddy/app.py`:
```python
import streamlit as st

from internbuddy.graph import run
from internbuddy.models import UserProfile

st.set_page_config(page_title="Internbuddy", page_icon="🎓")
st.title("🎓 Internbuddy — AI Internship Finder")
st.caption("Find internships matched to your profile, delivered as a report.")

with st.form("profile_form"):
    name = st.text_input("Name")
    stream = st.text_input("Educational stream", placeholder="e.g. B.Tech Computer Science")
    interest = st.text_input("Field of interest", placeholder="e.g. machine learning")
    email = st.text_input("Email")
    resume_link = st.text_input(
        "Google Drive resume link",
        placeholder="https://drive.google.com/file/d/.../view (shared: anyone with the link)",
    )
    report_format = st.radio("Report format", ["csv", "pdf"], horizontal=True)
    top_n = st.slider("Number of matches", min_value=5, max_value=20, value=10)
    submitted = st.form_submit_button("Find internships")

if submitted:
    profile = UserProfile(name, stream, interest, email, resume_link)
    problems = profile.validate()
    if problems:
        for p in problems:
            st.error(p)
        st.stop()

    with st.spinner("Searching Internshala and LinkedIn, ranking with Gemini..."):
        try:
            state = run(profile, report_format=report_format, top_n=top_n)
        except Exception as exc:  # config errors, unexpected failures
            st.error(f"Something went wrong: {exc}")
            st.stop()

    for warning in state.get("errors", []):
        st.warning(warning)

    matched = state.get("matched_jobs", [])
    if not matched:
        st.info("No internships matched your profile. Try a broader field of interest.")
        st.stop()

    st.success(f"Found {len(matched)} matches for {profile.name}.")
    st.dataframe(
        [
            {
                "Company": m.company,
                "Job Role": m.role,
                "Job Location": m.location,
                "Why This Role Is For You": m.why,
            }
            for m in matched
        ],
        use_container_width=True,
    )

    report_bytes = state.get("report_bytes", b"")
    if report_bytes:
        st.download_button(
            "⬇️ Download report",
            data=report_bytes,
            file_name=state.get("report_filename", "internbuddy_report"),
            mime=state.get("report_mime", "text/csv"),
        )

    email_status = state.get("email_status", "")
    if email_status == "sent":
        st.success(f"Report emailed to {profile.email}.")
    else:
        st.info(f"Email status: {email_status}")
```

- [ ] **Step 2: Write README.md**

`README.md`:
```markdown
# Internbuddy 🎓

An AI internship-search agent. Give it your profile and a Google Drive resume
link; it scrapes Internshala and LinkedIn, ranks matches with Google Gemini,
and delivers a PDF/CSV report by download and email.

## Setup

1. Python 3.11+
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in:
   - `GOOGLE_API_KEY` — a Google Gemini API key
   - `SMTP_*` and `FROM_EMAIL` — e.g. Gmail SMTP with a 16-char app password
4. Make sure the Google Drive resume is shared as **"Anyone with the link"**.

## Run

```bash
streamlit run internbuddy/app.py
```

## Test

```bash
python -m pytest -v
```

## Notes

- Only Internshala and the LinkedIn guest endpoint are scraped (Indeed blocks
  bots). Scraping is best-effort and polite (custom User-Agent + delay); a
  blocked source degrades gracefully and the run continues.
- Site HTML changes over time; if a scraper returns nothing, the CSS selectors
  in `internbuddy/scrapers.py` may need updating against the live page.
- Respect each site's Terms of Service and rate limits.
```

- [ ] **Step 3: Verify the app imports and the suite still passes**

Run: `python -c "import ast; ast.parse(open('internbuddy/app.py').read()); print('app.py parses')"`
Expected: `app.py parses`

Run: `python -m pytest -v`
Expected: PASS (all tests)

- [ ] **Step 4: Manual verification (requires real .env)**

Run: `streamlit run internbuddy/app.py`
Expected: browser opens the form; submitting a valid profile shows a results
table, a working download button, and an email-sent (or clearly-reported
failure) status. If keys are missing, a clear error is shown — not a stack trace.

- [ ] **Step 5: Commit**

```bash
git add internbuddy/app.py README.md
git commit -m "feat: add Streamlit UI and README"
```

---

## Self-Review

**Spec coverage:**
- Five inputs → Task 1 (`UserProfile`) + Task 10 (form). ✓
- Resume download + parse feeds matching → Task 2 + Task 6 prompt + Task 9 wiring. ✓
- Internshala + LinkedIn guest, no Indeed → Tasks 3, 4. ✓
- Filter/dedupe → Task 5. ✓
- Gemini ranking + why-text → Task 6. ✓
- Report with the five exact columns, runtime PDF/CSV choice → Task 7 + Task 10 radio. ✓
- Download button + email delivery → Task 8 + Task 10. ✓
- Graceful degradation, never crash → Task 9 nodes + Task 10 warnings; tested in `test_graph.py`. ✓
- LangGraph orchestration → Task 9. ✓

**Placeholder scan:** No TBD/TODO; every code step contains complete code. The
scrapers note in the README ("selectors may need updating") is a genuine
operational reality of scraping, not a deferred implementation task. ✓

**Type consistency:** `JobListing`, `MatchedJob`, `UserProfile`, `AgentState`
field names are used identically across Tasks 1–10. `build_report` returns
`(bytes, mime, filename)`; `mailer.send_report(profile, report_bytes, filename,
mime, smtp=None)` and `node_report`/`node_email` consume them with matching
names. `match_jobs(profile, resume_text, listings, top_n, client)` signature is
consistent between Task 6 and its call in Task 9. ✓
