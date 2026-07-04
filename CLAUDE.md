# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Internbuddy is an AI internship-search agent (Streamlit app). A user submits
name, educational stream, field of interest, email, and a Google Drive resume
link. The app parses the resume, scrapes internship listings from Internshala
and LinkedIn (guest endpoint), ranks them against the user's profile with
Gemini, generates a report (PDF or CSV), and delivers it via download button
and email.

Full design spec: `docs/superpowers/plans/2026-07-02-internbuddy.md` (and
`docs/superpowers/specs/2026-07-02-internbuddy-design.md`) — this is the
authoritative task-by-task build plan (10 tasks). Check
`.superpowers/sdd/progress.md` for which tasks are complete.

## Commands

```bash
pip install -r requirements.txt   # install deps
pytest                             # run all tests
pytest tests/test_matcher.py       # run a single test file
pytest tests/test_matcher.py::test_match_jobs_parses_gemini_json  # single test
streamlit run internbuddy/app.py   # run the app (once app.py exists)
```

No lint/format tooling is configured. Copy `.env.example` to `.env` and fill
in `GOOGLE_API_KEY` and `SMTP_*` before running the app.

## Architecture

Each module in `internbuddy/` has a single responsibility:

- `config.py` — loads `.env`; `get_google_api_key()` / `get_smtp_config()`
  raise `ConfigError` with an actionable message when values are missing.
- `models.py` — `UserProfile`, `JobListing`, `MatchedJob` dataclasses, and
  `AgentState` (a `TypedDict` carrying the LangGraph pipeline state).
- `resume.py` — downloads a resume from a Google Drive share link and
  extracts text (PDF via `pdfplumber`, DOCX via `python-docx`).
- `scrapers.py` — `scrape_internshala()` and `scrape_linkedin_guest()`, each
  with a paired `parse_*(html)` function so scraping logic can be unit-tested
  against saved HTML fixtures instead of live network calls.
- `matcher.py` — `filter_candidates()` dedupes listings by `(company, role)`
  and ranks by keyword overlap with the profile, capping candidates (default
  25) to bound Gemini cost. Gemini-based ranking (`match_jobs()` /
  `fallback_matches()`) is appended here per the plan's Task 6 — pass a
  `client` object exposing `generate_content(prompt) -> obj.text` to avoid
  hitting the real API in tests.
- `report.py` (planned) — `build_csv()` / `build_pdf()` producing report
  bytes with exactly these columns: company, job role, job location, job
  description, why this role is for you.
- `mailer.py` (planned) — sends the report over SMTP via stdlib `smtplib`.
- `graph.py` (planned) — assembles the LangGraph pipeline and exposes
  `run(profile, report_format, top_n)`.
- `app.py` (planned) — Streamlit UI: collects the five inputs, calls
  `graph.run`, renders results, offers the download button, shows email
  status.

### Pipeline flow (LangGraph, one node per stage)

```
parse_resume → scrape → filter → match → generate_report → send_email
```

Nodes return partial `AgentState` updates rather than mutating state in
place. Every stage catches its own failures, appends to `state["errors"]`,
and degrades gracefully instead of crashing the UI (e.g., a bad resume link
falls back to stream/interest-only matching; a blocked scraper still returns
the other source's results; a failed Gemini call falls back to
keyword-ordered listings with template "why" text; a failed SMTP send still
leaves the download working).

### Testing conventions

- Scrapers are tested against saved HTML fixtures — never make live network
  calls in tests.
- Gemini calls are tested via a fake `client` with a `generate_content`
  method returning an object with a `.text` attribute (see
  `tests/test_matcher.py` pattern in the plan for `match_jobs`).
- One end-to-end graph smoke test is expected once `graph.py` exists, with
  all external calls (network, Gemini, SMTP) mocked.
