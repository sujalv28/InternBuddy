# Internbuddy — Design Spec

**Date:** 2026-07-02
**Status:** Approved

## Overview

Internbuddy is an AI internship-search agent. A user submits their name,
educational stream, field of interest, email, and a Google Drive link to their
resume. Internbuddy parses the resume, scrapes internship listings from
Internshala and LinkedIn (guest endpoint), filters and ranks them against the
user's profile using Google Gemini, generates a report (PDF or CSV) containing
`company`, `job role`, `job location`, `job description`, and a personalized
`why this role is for you`, then delivers the report via a download button and
by email.

## Goals

- Collect five inputs: name, educational stream, field of interest, email,
  Google Drive resume link.
- Parse the resume and use its content to improve matching.
- Scrape internships from Internshala and the LinkedIn guest jobs endpoint.
- Filter/dedupe listings and rank the best matches with Gemini.
- Produce a report (user chooses PDF or CSV at runtime) with exactly these
  columns: company name, job role, job location, job description, why this role
  is for you.
- Deliver the report via a Streamlit download button **and** email it to the
  user.
- Never crash the UI; degrade gracefully when a source, the resume, the LLM, or
  SMTP fails.

## Non-Goals

- Indeed scraping (aggressively bot-blocked; excluded by decision).
- LinkedIn authenticated scraping (guest endpoint only).
- Persisting user data or runs to a database.
- User accounts / authentication.
- Hosting the report on external cloud storage (delivery is download button +
  email only).

## Tech Stack

- **UI:** Streamlit
- **Orchestration:** LangGraph (linear state graph, one node per stage)
- **LLM:** Google Gemini via `google-genai`, model `gemini-2.5-flash`
- **Scraping:** `requests` + `beautifulsoup4`
- **Resume parsing:** `pdfplumber` (PDF), `python-docx` (DOCX)
- **Report:** `fpdf2` (PDF), stdlib `csv` (CSV)
- **Email:** stdlib `smtplib` + `email`
- **Config:** `python-dotenv`
- **Python:** 3.11+

## Module Layout

```
internbuddy/
  app.py            # Streamlit UI — collects input, runs graph, renders output
  config.py         # loads .env: GOOGLE_API_KEY, SMTP_* ; validates presence
  models.py         # UserProfile, JobListing, MatchedJob, AgentState (TypedDict)
  resume.py         # download Drive file -> extract text
  scrapers.py       # scrape_internshala(), scrape_linkedin_guest()
  matcher.py        # Gemini: rank candidates + write "why this role" text
  report.py         # build_csv(), build_pdf() -> bytes
  mailer.py         # send_report() over SMTP
  graph.py          # assembles the LangGraph and exposes run(profile, ...)
  requirements.txt
  .env.example
  README.md
  tests/            # fixtures + unit tests
```

Each module has a single responsibility and a well-defined interface so it can
be understood and tested independently.

## Data Models (`models.py`)

- **UserProfile** — `name`, `stream`, `field_of_interest`, `email`,
  `resume_link`.
- **JobListing** — `company`, `role`, `location`, `description`, `url`,
  `source` ("internshala" | "linkedin").
- **MatchedJob** — `JobListing` fields + `why` (the "why this role is for you"
  text) + `rank`.
- **AgentState** — a `TypedDict` carrying: `profile`, `resume_text`,
  `raw_listings`, `filtered_listings`, `matched_jobs`, `report_bytes`,
  `report_format`, `top_n`, `email_status`, `errors: list[str]`.

Nodes return partial state updates; state is not mutated in place.

## LangGraph Flow

```
START
 → parse_resume     download + extract text; on failure warn and continue
 → scrape           Internshala + LinkedIn guest; each source degrades independently
 → filter           dedupe + keyword relevance → keep top ~25 candidates
 → match            ONE Gemini call: rank + write why-text → top N
 → generate_report  PDF or CSV per user choice → bytes
 → send_email       attach report, send to user's email
 → END
```

## Data Flow

Streamlit form → build `UserProfile` → `graph.run(profile, report_format, top_n)`
→ final `AgentState` → UI renders results table, a download button serving
`report_bytes`, and the email status. The same bytes are attached to the email.

## Filtering + Matching Detail

- **filter:** normalize whitespace/case; dedupe by `(company, role)`; score each
  listing by keyword overlap with `field_of_interest` and `stream`; keep the top
  ~25 candidates to bound Gemini cost.
- **match:** a single structured Gemini call receives the resume text + profile +
  the ~25 candidates and returns JSON — a ranked top-N list, each item with a
  2–3 sentence "why this role is for you" grounded in the resume and stated
  interests. One batched call is cheaper, faster, and yields consistent ranking.

## Error Handling (never crash the UI)

Every failure is caught, appended to `state.errors`, and surfaced as a Streamlit
warning:

- Resume link private/invalid → fall back to stream+interest matching.
- A scraper blocked/errored → keep the other source's results.
- Zero results after filter → friendly "no matches" message; skip report/email.
- Gemini call fails → fallback template "why" text + relevance-ordered list.
- SMTP send fails → download still works; show the email error.

## Config / Secrets

`.env` holds:

- `GOOGLE_API_KEY` — required for matching.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL` —
  required for email delivery (e.g. a Gmail app password).

`.env.example` is shipped. On a missing required key the app shows a clear,
actionable error instead of a stack trace. `.env` is git-ignored.

## Scraping Notes

- Internshala: parse public internship listing pages.
- LinkedIn: use the guest jobs endpoint
  (`/jobs-guest/jobs/api/seeMoreJobPostings`) which returns parseable HTML
  without login.
- Politeness: custom `User-Agent` header and a small delay between requests to
  reduce blocking. README documents the ToS/rate-limit caveat.

## Confirmed Defaults

1. **Result count:** default top 10, UI slider range 5–20.
2. **Gemini model:** `gemini-2.5-flash`.
3. **Batched Gemini call:** one call ranks and writes all why-texts.
4. **Sequential scraping:** Internshala then LinkedIn.
5. **Politeness:** custom User-Agent + inter-request delay.

## Testing Strategy

- Scrapers tested against saved HTML fixtures (no live network).
- `filter` dedupe/relevance unit tests.
- `report` tests assert valid non-empty CSV (correct headers) and PDF bytes.
- `matcher` tested with a mocked Gemini client.
- `resume` parser tested with sample PDF/DOCX fixtures.
- One graph smoke test with all external calls mocked.

## Success Criteria

- User can submit the five inputs in Streamlit and receive a report.
- Report contains exactly the five required columns.
- Report downloads via button and arrives by email (when SMTP configured).
- Each external failure degrades gracefully with a visible warning; the app
  never crashes.
- All unit tests and the graph smoke test pass with external calls mocked.
